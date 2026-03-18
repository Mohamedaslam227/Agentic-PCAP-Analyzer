"""
Research Router
~~~~~~~~~~~~~~~
Async job queue for long-running deep-research requests.

A research request is immediately accepted and a background job is
scheduled.  The caller receives a ``job_id`` and should poll
``GET /research/{job_id}`` for the result.

Phase F implements the actual agentic research runner
(logics.agents.research_runner).  Until then, the background task
records a placeholder result so the polling endpoint returns correctly.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from logics.api.models.schema import (
    ResearchCreateResponse,
    ResearchRequest,
    ResearchResultResponse,
)
from logics.api.routers.auth import get_current_user
from logics.data_layer.postgres.connection import db_pool
from logics.data_layer.postgres.repositories import ResearchRepo
from logics.log import get_logger

logger = get_logger(__name__)

# Attempt to import the agentic runner — available only after Phase F.
try:
    from logics.agents.research_runner import run_research as _agent_run_research  # type: ignore[import]
    _agent_available = True
except ImportError:
    _agent_available = False


router = APIRouter(prefix="/research", tags=["research"])


# ── Background task ─────────────────────────────────────────────────────────

async def _run_research_job(job_id: str, session_id: str, question: str) -> None:
    """
    Background task that runs the research job.
    Delegates to the agentic runner when Phase F is available;
    until then writes a placeholder so the poll endpoint returns correctly.
    """
    pool = db_pool.get_pool()
    async with pool.acquire() as conn:
        repo = ResearchRepo(conn)
        try:
            if _agent_available:
                result = await _agent_run_research(job_id, session_id, question)
            else:
                result = (
                    "Deep-research agent not yet implemented (Phase F). "
                    "Implement logics/agents/research_runner.py to enable full analysis."
                )
            await repo.update_result(job_id, result, status="completed")
            logger.info("research.bg | job=%s completed", job_id)
        except Exception as exc:
            logger.error("research.bg | job=%s error=%s", job_id, exc)
            await repo.update_result(job_id, str(exc), status="failed")


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("", response_model=ResearchCreateResponse)
async def start_research(
    request: ResearchRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a deep-research question against a processed PCAP session.

    The job is queued immediately.  Poll ``GET /research/{job_id}`` to
    check progress and retrieve the final report.

    Requires ``Authorization: Bearer <access_token>`` header.
    """
    job_id = str(uuid4())
    pool = db_pool.get_pool()
    async with pool.acquire() as conn:
        repo = ResearchRepo(conn)
        await repo.create_job(job_id, request.session_id or "", request.question)

    background_tasks.add_task(
        _run_research_job, job_id, request.session_id or "", request.question
    )
    logger.info(
        "research.start | job=%s session=%s user=%s",
        job_id, request.session_id, current_user["username"],
    )
    return ResearchCreateResponse(job_id=job_id)


@router.get("/{job_id}", response_model=ResearchResultResponse)
async def get_research_result(
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Poll the result of a previously submitted research job.

    Status transitions: ``pending`` → ``running`` → ``completed`` | ``failed``

    Requires ``Authorization: Bearer <access_token>`` header.
    """
    pool = db_pool.get_pool()
    async with pool.acquire() as conn:
        repo = ResearchRepo(conn)
        job = await repo.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research job '{job_id}' not found.",
        )

    return ResearchResultResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        result=job.get("result"),
    )
