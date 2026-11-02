import sys
import tempfile
import unittest
from pathlib import Path

from app.methodo.parse_cache import cache_path
from app.methodo.parse_cache import load_cached_chunks
from app.methodo.parse_cache import load_failures
from app.methodo.parse_cache import ParseFailure
from app.methodo.parse_cache import save_failures
from app.methodo.parse_manifest import ManifestRow
from app.methodo.parse_worker import Lane
from app.methodo.parse_worker import LaneName
from app.methodo.parse_worker import Supervisor

LONG_DOC_PAGES = 100
LANES = {
    LaneName.NORMAL: Lane(LaneName.NORMAL, workers=2, rss_limit_mb=None, max_docs=2),
    LaneName.LONG: Lane(LaneName.LONG, workers=1, rss_limit_mb=None, max_docs=1),
}


class TestSupervisor(unittest.TestCase):
    """Supervisor + real worker subprocesses, with the parse faked (fake_parse_worker)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.data_dir = Path(self._tmp.name) / "data"
        self.cache_dir = Path(self._tmp.name) / "cache"
        self.data_dir.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _row(self, name: str, action: str, pages: int = 10) -> ManifestRow:
        (self.data_dir / f"{name}.pdf").write_text(action)
        return ManifestRow(source_url=f"url/{name}", label=name, file=f"{name}.pdf",
                           metadata={"name": name}, min_chunk_words=None,
                           content_start_page=1, page_count=pages)

    def _run(self, rows: list[ManifestRow]):
        def worker_cmd(lane: Lane) -> list[str]:
            return [sys.executable, "-m", "tests.unitary.fake_parse_worker",
                    str(self.data_dir), str(self.cache_dir), str(lane.max_docs)]
        return Supervisor(rows, self.data_dir, self.cache_dir, LANES, worker_cmd,
                          long_doc_pages=LONG_DOC_PAGES).run()

    def _cached(self, row: ManifestRow) -> list | None:
        return load_cached_chunks(self.cache_dir, row.source_url,
                                  row.to_job(self.data_dir).fingerprint())

    def test_parses_everything_and_restarts_workers(self) -> None:
        rows = [self._row(f"d{i}", "ok") for i in range(5)] + [self._row("long", "ok", 300)]
        report = self._run(rows)
        self.assertEqual(len(report.parsed), 6)
        self.assertEqual(report.failed, [])
        pids = {self._cached(r)[0]["page_content"] for r in rows}
        # 5 normal docs at 2 docs per worker need >= 3 workers, plus 1 long-lane worker
        self.assertGreaterEqual(len(pids), 4)

    def test_rerun_skips_cached_docs(self) -> None:
        rows = [self._row("a", "ok"), self._row("b", "ok")]
        self._run(rows)
        report = self._run(rows)
        self.assertEqual(report.skipped_cached, 2)
        self.assertEqual(report.parsed, [])

    def test_exception_fails_without_retry(self) -> None:
        bad, good = self._row("bad", "raise"), self._row("good", "ok")
        report = self._run([bad, good])
        self.assertEqual(report.parsed, ["url/good"])
        self.assertEqual(report.retried_in_long_lane, [])
        failure = load_failures(self.cache_dir)["url/bad"]
        self.assertEqual(failure.reason, "exception:ValueError")
        self.assertIsNone(self._cached(bad))

    def test_sigkill_mid_doc_lands_in_failed_with_no_cache_entry(self) -> None:
        killed, good = self._row("killed", "sigkill"), self._row("good", "ok")
        report = self._run([killed, good])
        self.assertEqual(report.retried_in_long_lane, ["url/killed"])  # one retry only
        failure = load_failures(self.cache_dir)["url/killed"]
        self.assertEqual((failure.reason, failure.exit_signal), ("oom_killed", 9))
        self.assertFalse(cache_path(self.cache_dir, killed.source_url).exists())
        self.assertIsNotNone(self._cached(good))

    def test_killed_doc_succeeds_on_long_lane_retry(self) -> None:
        row = self._row("flaky", "sigkill_once")
        report = self._run([row])
        self.assertEqual(report.retried_in_long_lane, ["url/flaky"])
        self.assertEqual(report.parsed, ["url/flaky"])
        self.assertEqual(load_failures(self.cache_dir), {})

    def test_success_clears_earlier_failure(self) -> None:
        row = self._row("again", "ok")
        save_failures(self.cache_dir, {row.source_url: ParseFailure(
            row.source_url, row.label, "oom_killed", "", 9, 12000, "old")})
        self._run([row])
        self.assertEqual(load_failures(self.cache_dir), {})


if __name__ == "__main__":
    unittest.main()
