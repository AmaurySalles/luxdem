"""
Parse-only worker for the rented parse box (#71, #77): manifest + PDFs in, parse cache
out. No Postgres or Chroma.

A supervisor runs restarting worker subprocesses in two lanes:
- normal: `--workers` workers. A worker exits once its RSS after a doc is over 10 GB, or
  after 20 docs, and is replaced.
- long: 1 worker for docs over 250 pages, restarted after every doc.

A stdlib pool isn't used: an OOM kill breaks `ProcessPoolExecutor` and hangs
`multiprocessing.Pool`. Models load once per worker, not once per doc.

Workers write cache entries only on success (atomically, see `parse_cache`). The
supervisor keeps `failed.jsonl` in the cache dir. A doc whose normal-lane worker was
SIGKILLed (the OOM killer's signal) gets one retry in the long lane. Exceptions are not
retried. A rerun skips docs already cached with a matching fingerprint, so failed docs
are retried, and a success clears their failure.

Protocol: the supervisor writes one manifest row per line to a worker's stdin. The worker
answers each with one JSON line on a dedicated reply pipe, whose fd it gets in
`REPLY_FD_ENV` (stdout isn't used: libraries print to it, even at import time).

Run on the box: `python -m app.methodo.parse_worker supervise --manifest ... --data-dir ...`
"""
import json
import os
import queue
import select
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from pathlib import Path
from typing import Any

import psutil
import typer
from ecodev_core import logger_get

from app.methodo.parse_cache import load_cached_chunks
from app.methodo.parse_cache import load_failures
from app.methodo.parse_cache import PARSE_CACHE_DIR
from app.methodo.parse_cache import ParseFailure
from app.methodo.parse_cache import ParseJob
from app.methodo.parse_cache import save_cached_chunks
from app.methodo.parse_cache import save_failures
from app.methodo.parse_manifest import ManifestRow
from app.methodo.parse_manifest import read_manifest

log = logger_get(__name__)

LONG_DOC_PAGES = 250
NORMAL_RSS_LIMIT_MB = 10 * 1024
NORMAL_MAX_DOCS = 20
_RSS_SAMPLE_S = 1.0
_BYTES_PER_MB = 1024 * 1024
REPLY_FD_ENV = "PARSE_WORKER_REPLY_FD"


class LaneName(str, Enum):
    NORMAL = "normal"
    LONG = "long"


@dataclass(frozen=True)
class Lane:
    """Worker settings for one lane; `rss_limit_mb=None` means no RSS-based restart."""
    name: LaneName
    workers: int
    rss_limit_mb: int | None
    max_docs: int


def _rss_mb(process: psutil.Process) -> int:
    return process.memory_info().rss // _BYTES_PER_MB


# --- worker side ------------------------------------------------------------------------

def serve_worker(reply_fd: int,
                 data_dir: Path,
                 cache_dir: Path,
                 rss_limit_mb: int | None,
                 max_docs: int,
                 parse: Callable[[ParseJob], list[dict[str, Any]]] = ParseJob.parse) -> None:
    """
    Parse docs read from stdin until EOF, the RSS limit or `max_docs`.

    Purpose: body of the worker subprocess. `parse` is injectable so tests can run the
    real loop with a fake parse.

    NOTE: an exception is reported and the worker carries on with the next doc. A crash
    (e.g. OOM kill) is detected by the supervisor from the closed pipe.
    """
    replies = os.fdopen(reply_fd, "w", buffering=1)
    me = psutil.Process()
    for done, line in enumerate(sys.stdin, 1):
        job = ManifestRow(**json.loads(line)).to_job(data_dir)
        reply: dict[str, Any] = {"source_url": job.source_url}
        try:
            chunks = parse(job)
        except Exception as e:  # reported to the supervisor, which records it in failed.jsonl
            reply.update(status="error", error_type=type(e).__name__, error=str(e))
        else:
            save_cached_chunks(cache_dir, job.source_url, job.label, job.fingerprint(), chunks)
            reply.update(status="ok", chunks=len(chunks))
        rss_mb = _rss_mb(me)
        exiting = done >= max_docs or (rss_limit_mb is not None and rss_mb > rss_limit_mb)
        reply.update(rss_mb=rss_mb, exiting=exiting)
        replies.write(json.dumps(reply) + "\n")
        if exiting:
            return


# --- supervisor side --------------------------------------------------------------------

@dataclass
class SupervisorReport:
    skipped_cached: int = 0
    parsed: list[str] = field(default_factory=list)
    retried_in_long_lane: list[str] = field(default_factory=list)
    failed: list[ParseFailure] = field(default_factory=list)


class _WorkerDiedError(Exception):
    """The worker exited without answering for its doc (killed, or crashed)."""

    def __init__(self, returncode: int, last_rss_mb: int | None) -> None:
        self.returncode = returncode
        self.last_rss_mb = last_rss_mb
        super().__init__(f"worker exited with {returncode}")

    @property
    def exit_signal(self) -> int | None:
        return -self.returncode if self.returncode < 0 else None

    @property
    def reason(self) -> str:
        if self.exit_signal == signal.SIGKILL:
            return "oom_killed"
        return "signal" if self.exit_signal else f"exit:{self.returncode}"


class _Worker:
    """One worker subprocess, fed one doc at a time."""

    def __init__(self, cmd: list[str]) -> None:
        read_fd, write_fd = os.pipe()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True, bufsize=1,
                                     pass_fds=(write_fd,),
                                     env={**os.environ, REPLY_FD_ENV: str(write_fd)})
        os.close(write_fd)  # the worker holds the only write end: EOF means it exited
        self.replies = os.fdopen(read_fd)
        self.psutil_proc = psutil.Process(self.proc.pid)

    def run(self, row: ManifestRow) -> dict[str, Any]:
        """
        Send one doc and wait for its reply, sampling RSS while it parses.

        Raises:
            _WorkerDiedError: the worker exited before answering.
        """
        assert self.proc.stdin
        last_rss_mb: int | None = None
        try:
            self.proc.stdin.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            pass  # already dead: reported below from the closed stdout
        while True:
            ready, _, _ = select.select([self.replies], [], [], _RSS_SAMPLE_S)
            if ready:
                line = self.replies.readline()
                if line:
                    return json.loads(line)
                raise _WorkerDiedError(self.proc.wait(), last_rss_mb)
            try:
                last_rss_mb = _rss_mb(self.psutil_proc)
            except psutil.NoSuchProcess:
                pass  # exited between select calls: readline gets EOF next round

    def close(self) -> None:
        if self.proc.stdin:
            try:
                self.proc.stdin.close()
            except BrokenPipeError:
                pass  # worker already gone; nothing left to tell it
        self.proc.wait()
        self.replies.close()


class Supervisor:
    """
    Route manifest rows to lanes and run each lane's workers until every doc is parsed or
    failed.

    Purpose: entry point of the parse box run (#81).
    """

    def __init__(self,
                 rows: list[ManifestRow],
                 data_dir: Path,
                 cache_dir: Path,
                 lanes: dict[LaneName, Lane],
                 worker_cmd: Callable[[Lane], list[str]],
                 long_doc_pages: int = LONG_DOC_PAGES) -> None:
        self.data_dir = data_dir
        self.cache_dir = cache_dir
        self.lanes = lanes
        self.worker_cmd = worker_cmd
        self.long_doc_pages = long_doc_pages
        self.rows = rows
        self.report = SupervisorReport()
        self.failures = load_failures(cache_dir)
        self.queues: dict[LaneName, queue.Queue[ManifestRow]] = {
            name: queue.Queue() for name in lanes}
        self.outstanding = 0
        self.lock = threading.Lock()
        self.abort = threading.Event()
        self.slot_errors: list[BaseException] = []

    def run(self) -> SupervisorReport:
        for row in self.rows:
            if load_cached_chunks(self.cache_dir, row.source_url,
                                  row.to_job(self.data_dir).fingerprint()) is not None:
                self.report.skipped_cached += 1
                continue
            lane = LaneName.LONG if row.page_count > self.long_doc_pages else LaneName.NORMAL
            self.queues[lane].put(row)
            self.outstanding += 1
        log.info(f"{self.outstanding} docs to parse, {self.report.skipped_cached} cached; "
                 + ", ".join(f"{n.value}: {q.qsize()}" for n, q in self.queues.items()))
        threads = [threading.Thread(target=self._run_slot_guarded, args=(lane,), daemon=True)
                   for lane in self.lanes.values() for _ in range(lane.workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if self.slot_errors:
            raise RuntimeError("a supervisor slot crashed, run stopped") from self.slot_errors[0]
        return self.report

    def _run_slot_guarded(self, lane: Lane) -> None:
        """A bug in one slot stops all slots (re-raised by `run`) instead of hanging them."""
        try:
            self._run_slot(lane)
        except BaseException as e:
            with self.lock:
                self.slot_errors.append(e)
            self.abort.set()

    def _next_row(self, lane: Lane) -> ManifestRow | None:
        """Next doc for this lane, or None once nothing is left that could reach it."""
        while not self.abort.is_set():
            try:
                return self.queues[lane.name].get(timeout=_RSS_SAMPLE_S)
            except queue.Empty:
                with self.lock:
                    if self.outstanding == 0:
                        return None
        return None

    def _run_slot(self, lane: Lane) -> None:
        worker: _Worker | None = None
        try:
            while (row := self._next_row(lane)) is not None:
                worker = worker or _Worker(self.worker_cmd(lane))
                log.info(f"[{lane.name.value}] {row.label} ({row.page_count} p)")
                try:
                    reply = worker.run(row)
                except _WorkerDiedError as died:
                    worker.close()
                    worker = None
                    self._on_died(lane, row, died)
                    continue
                if reply["exiting"]:
                    worker.close()
                    worker = None
                if reply["status"] == "ok":
                    self._finish(row, failure=None)
                else:
                    self._finish(row, self._failure(row, f"exception:{reply['error_type']}",
                                                    reply["error"], None, reply["rss_mb"]))
        finally:
            if worker:
                worker.close()

    def _on_died(self, lane: Lane, row: ManifestRow, died: _WorkerDiedError) -> None:
        log.error(f"[{lane.name.value}] worker died on {row.label}: {died.reason}, "
                  f"last RSS {died.last_rss_mb} MB")
        if died.reason == "oom_killed" and lane.name == LaneName.NORMAL:
            with self.lock:
                self.report.retried_in_long_lane.append(row.source_url)
            self.queues[LaneName.LONG].put(row)  # still outstanding
            return
        self._finish(row, self._failure(row, died.reason, str(died), died.exit_signal,
                                        died.last_rss_mb))

    def _failure(self, row: ManifestRow, reason: str, detail: str,
                 exit_signal: int | None, last_rss_mb: int | None) -> ParseFailure:
        return ParseFailure(source_url=row.source_url, label=row.label, reason=reason,
                            detail=detail, exit_signal=exit_signal, last_rss_mb=last_rss_mb,
                            fingerprint=row.to_job(self.data_dir).fingerprint())

    def _finish(self, row: ManifestRow, failure: ParseFailure | None) -> None:
        with self.lock:
            if failure is None:
                self.report.parsed.append(row.source_url)
                self.failures.pop(row.source_url, None)
            else:
                log.error(f"   → failed: {row.label}: {failure.reason} {failure.detail}")
                self.report.failed.append(failure)
                self.failures[row.source_url] = failure
            save_failures(self.cache_dir, self.failures)
            self.outstanding -= 1


def default_lanes(workers: int) -> dict[LaneName, Lane]:
    return {
        LaneName.NORMAL: Lane(LaneName.NORMAL, workers, NORMAL_RSS_LIMIT_MB, NORMAL_MAX_DOCS),
        LaneName.LONG: Lane(LaneName.LONG, 1, None, 1),
    }


def worker_command(data_dir: Path, cache_dir: Path) -> Callable[[Lane], list[str]]:
    """Command line of a real worker subprocess for a lane."""
    def command(lane: Lane) -> list[str]:
        cmd = [sys.executable, "-m", "app.methodo.parse_worker", "worker",
               "--data-dir", str(data_dir), "--cache-dir", str(cache_dir),
               "--max-docs", str(lane.max_docs)]
        if lane.rss_limit_mb is not None:
            cmd += ["--rss-limit-mb", str(lane.rss_limit_mb)]
        return cmd
    return command


# --- CLI (the box has no Postgres, so this isn't in typer_app) --------------------------

cli = typer.Typer()


@cli.command()
def supervise(manifest: Path = typer.Option(..., help="Manifest from export-parse-manifest"),
              data_dir: Path = typer.Option(..., help="Dir the manifest's files are under"),
              cache_dir: Path = typer.Option(PARSE_CACHE_DIR, help="Parse cache dir"),
              workers: int = typer.Option(3, help="Normal-lane workers"),
              only: list[str] = typer.Option(None, help="Only these file stems (e.g. 8080)"),
              ) -> None:
    """Parse every manifest doc not already cached; failures go to failed.jsonl."""
    rows = read_manifest(manifest)
    if only:
        rows = [r for r in rows if Path(r.file).stem in set(only)]
    report = Supervisor(rows, data_dir, cache_dir, default_lanes(workers),
                        worker_command(data_dir, cache_dir)).run()
    typer.echo(f"\nparsed: {len(report.parsed)}  already cached: {report.skipped_cached}  "
               f"retried in long lane: {len(report.retried_in_long_lane)}  "
               f"failed: {len(report.failed)}")
    for f in report.failed:
        typer.echo(f"  FAILED {f.label}: {f.reason} (last RSS {f.last_rss_mb} MB) {f.detail}")
    if report.failed:
        raise typer.Exit(1)


@cli.command()
def worker(data_dir: Path = typer.Option(...),
           cache_dir: Path = typer.Option(...),
           max_docs: int = typer.Option(...),
           rss_limit_mb: int = typer.Option(None)) -> None:
    """Internal: one worker subprocess, started by `supervise`."""
    serve_worker(int(os.environ[REPLY_FD_ENV]), data_dir, cache_dir, rss_limit_mb, max_docs)


if __name__ == "__main__":
    cli()
