"""Run a set of items through sessions, in parallel, one client per thread."""

from __future__ import annotations

import queue
import shutil
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from bp.session import Client, ItemResult, run_document, seal

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from bp.contract import Item


def run_items(
    items: list[Item],
    make_client: Callable[[int], Client],
    *,
    root: Path,
    workdir: Path,
    jobs: int = 1,
    progress: bool = True,
    close_client: Callable[[Client], None] | None = None,
) -> list[ItemResult]:
    """`root` is the directory that `Item.doc` is relative to. `workdir` receives the sealed copies."""
    by_doc: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        by_doc[item.doc].append(item)
    docs = sorted(by_doc)
    clients: queue.Queue[Client] = queue.Queue()
    made: list[Client] = []
    for index in range(max(1, jobs)):
        client = make_client(index)
        made.append(client)
        clients.put(client)
    done = 0
    lock = threading.Lock()
    started = time.monotonic()

    def one(doc: str) -> list[ItemResult]:
        nonlocal done
        sealed = seal(root / doc, workdir)
        client = clients.get()
        try:
            results, _ = run_document(client, sealed, by_doc[doc])
        finally:
            clients.put(client)
        with lock:
            done += 1
            if progress and (done % 200 == 0 or done == len(docs)):
                rate = done / max(1e-9, time.monotonic() - started)
                print(f"  {done}/{len(docs)} documents, {rate:.1f} per second", file=sys.stderr)
        return results

    try:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            nested = list(pool.map(one, docs))
    finally:
        if close_client is not None:
            for client in made:
                close_client(client)
        shutil.rmtree(workdir, ignore_errors=True)
    results = [result for group in nested for result in group]
    results.sort(key=lambda r: r.item_id)
    return results
