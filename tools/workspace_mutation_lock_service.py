from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class WorkspaceMutationBusyError(RuntimeError):
    pass


def _try_lock(handle, *, shared: bool) -> bool:
    if os.name == "nt":
        import msvcrt

        try:
            handle.seek(0)
            mode = msvcrt.LK_NBRLCK if shared else msvcrt.LK_NBLCK
            msvcrt.locking(handle.fileno(), mode, 1)
            return True
        except OSError:
            return False
    import fcntl  # type: ignore

    try:
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        fcntl.flock(handle.fileno(), mode | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl  # type: ignore

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def _workspace_lock(
    lock_path: Path,
    *,
    shared: bool,
    timeout_seconds: float,
    poll_seconds: float,
) -> Iterator[None]:
    path = Path(lock_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while not _try_lock(handle, shared=shared):
            if time.monotonic() >= deadline:
                boundary = "writer" if shared else "reader or writer"
                raise WorkspaceMutationBusyError(
                    f"Another workspace {boundary} owns the cross-engine boundary; retry after it completes."
                )
            time.sleep(max(0.005, min(float(poll_seconds), 0.25)))
        try:
            yield
        finally:
            _unlock(handle)


@contextmanager
def workspace_mutation_lock(
    lock_path: Path,
    *,
    timeout_seconds: float = 5.0,
    poll_seconds: float = 0.025,
) -> Iterator[None]:
    """Exclusive cross-process boundary for SQLite, DuckDB, and recovery artifacts."""
    with _workspace_lock(
        lock_path,
        shared=False,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    ):
        yield


@contextmanager
def workspace_read_lock(
    lock_path: Path,
    *,
    timeout_seconds: float = 5.0,
    poll_seconds: float = 0.025,
) -> Iterator[None]:
    """Shared cross-process boundary that keeps reads out of recovery writes."""
    with _workspace_lock(
        lock_path,
        shared=True,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    ):
        yield
