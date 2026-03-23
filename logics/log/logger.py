"""Central logging configuration for the PCAP Analyzer."""
from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator, Optional

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
) -> None:
    """
    Configure the root logger with a console handler and an optional file handler.
    Should be called once at application startup (e.g. in main.py lifespan).
    """
    handlers: list = [logging.StreamHandler(sys.stdout)]

    if log_file is not None:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=handlers,
        force=True,
    )

    # Quieten noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.  Call configure_logging() once at startup."""
    configure_logging()
    return logging.getLogger(name)


# ── Timing utilities ───────────────────────────────────────────────────────────

class StepTimer:
    """
    Lightweight step timer that logs elapsed time for a named pipeline step.

    Usage (sync)::

        with StepTimer(logger, "embed question"):
            embeddings = svc.embed_batch(texts)

    Usage (async)::

        async with StepTimer.async_ctx(logger, "vector search"):
            flows = await repo.vector_search(...)

    Both variants log::

        ⏱  STEP  embed question  →  42.3 ms
        ⏱  STEP  vector search  →  108.7 ms
    """

    def __init__(self, log: logging.Logger, name: str, level: int = logging.INFO) -> None:
        self._log = log
        self._name = name
        self._level = level
        self._start: float = 0.0
        self.elapsed_ms: float = 0.0

    # ── sync context manager ──────────────────────────────────────────────
    def __enter__(self) -> "StepTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._log.log(
            self._level,
            "⏱  STEP  %-40s  →  %.1f ms",
            self._name,
            self.elapsed_ms,
        )

    # ── async context manager ─────────────────────────────────────────────
    async def __aenter__(self) -> "StepTimer":
        self._start = time.perf_counter()
        return self

    async def __aexit__(self, *_) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._log.log(
            self._level,
            "⏱  STEP  %-40s  →  %.1f ms",
            self._name,
            self.elapsed_ms,
        )


def log_pipeline_start(log: logging.Logger, session_id: str, question: str) -> float:
    """Log the start of a chat pipeline and return the start timestamp."""
    log.info(
        "┌─ CHAT PIPELINE START ──────────────────────────────\n"
        "│  session  : %s\n"
        "│  question : %.120s%s",
        session_id,
        question,
        "…" if len(question) > 120 else "",
    )
    return time.perf_counter()


def log_pipeline_end(
    log: logging.Logger,
    session_id: str,
    start: float,
    cached: bool = False,
    answer_len: int = 0,
) -> None:
    """Log a summary line at the end of the chat pipeline."""
    total_ms = (time.perf_counter() - start) * 1000
    src = "CACHE" if cached else "LLM"
    log.info(
        "└─ CHAT PIPELINE END ── session=%s  source=%-5s  answer_chars=%d  total=%.1f ms",
        session_id,
        src,
        answer_len,
        total_ms,
    )