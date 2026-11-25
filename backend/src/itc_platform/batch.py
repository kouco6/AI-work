"""itc 共享：非阻塞批量写入器（供 usage / audit 等观测旁路使用）。

设计动机（见《基础层设计.md》§八·风险 2）：
observer 的 ``on_event`` 在 relay 线程**同步执行**，写库绝不能拖慢 turn。
因此统一走「入队即返回 + 后台守护线程批量 flush」，任何异常都吞掉并记日志——
**观测旁路永不影响主链路**。

用法::

    _w = BatchWriter("itc-usage-writer", fetch_engine=get_engine)
    _w.enqueue(record)
    _w.flush_now()        # 测试 / 关机同步落库
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, Optional

from sqlalchemy import Engine
from sqlmodel import Session

logger = logging.getLogger("itc.batch")


class BatchWriter:
    """线程安全的批量写入器：入队非阻塞，后台线程批量提交。"""

    def __init__(
        self,
        thread_name: str,
        *,
        engine_getter: Callable[[], Engine],
        batch_size: int = 200,
        drain_timeout: float = 1.0,
        on_first_batch: Optional[Callable[[Engine], None]] = None,
    ) -> None:
        self._thread_name = thread_name
        self._engine_getter = engine_getter
        self._batch_size = batch_size
        self._drain_timeout = drain_timeout
        self._on_first_batch = on_first_batch
        self._q: "queue.Queue[object]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._prepared = False
        self._lock = threading.Lock()

    # ── 公共 API ────────────────────────────────────────────────
    def enqueue(self, record: object) -> None:
        self._ensure_worker()
        self._q.put(record)

    def flush_now(self) -> int:
        """同步落库当前队列（测试 / 关机用）。返回写入行数。"""
        return self._persist(self._drain())

    def shutdown(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self.flush_now()

    # ── 内部 ────────────────────────────────────────────────────
    def _ensure_worker(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name=self._thread_name, daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._persist(self._drain())

    def _drain(self) -> list[object]:
        batch: list[object] = []
        try:
            batch.append(self._q.get(timeout=self._drain_timeout))
        except queue.Empty:
            return batch
        while len(batch) < self._batch_size:
            try:
                batch.append(self._q.get_nowait())
            except queue.Empty:
                break
        return batch

    def _persist(self, batch: list[object]) -> int:
        if not batch:
            return 0
        try:
            engine = self._engine_getter()
            if not self._prepared and self._on_first_batch is not None:
                self._on_first_batch(engine)
                self._prepared = True
            with Session(engine) as session:
                for record in batch:
                    session.add(record)
                session.commit()
            return len(batch)
        except Exception:
            logger.exception("%s 落库失败，丢弃 %d 行", self._thread_name, len(batch))
            return 0
