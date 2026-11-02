"""
Worker subprocess for test_parse_worker: the real `serve_worker` loop with a fake parse.

The doc "PDF" is a text file whose content says what the parse does: `ok`, `raise`,
`sigkill` (dies mid-doc like an OOM kill) or `sigkill_once` (dies on the first attempt
only, tracked by a marker file next to it).
"""
import os
import signal
import sys
from pathlib import Path
from typing import Any

from app.methodo.parse_cache import ParseJob
from app.methodo.parse_worker import REPLY_FD_ENV
from app.methodo.parse_worker import serve_worker


def fake_parse(job: ParseJob) -> list[dict[str, Any]]:
    path = Path(job.source)
    action = path.read_text().strip()
    marker = path.with_suffix(".attempted")
    if action == "sigkill_once" and not marker.exists():
        marker.touch()
        action = "sigkill"
    if action == "sigkill":
        os.kill(os.getpid(), signal.SIGKILL)
    if action == "raise":
        raise ValueError(f"cannot parse {path.name}")
    return [{"page_content": f"pid {os.getpid()}", "metadata": job.metadata}]


if __name__ == "__main__":
    data_dir, cache_dir, max_docs = sys.argv[1], sys.argv[2], int(sys.argv[3])
    serve_worker(int(os.environ[REPLY_FD_ENV]), Path(data_dir), Path(cache_dir), None,
                 max_docs, parse=fake_parse)
