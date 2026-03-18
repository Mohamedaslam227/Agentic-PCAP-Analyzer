import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks

from logics.api.models.schema import ProcessingStatusResponse, UploadResponse
from logics.api.core.config import settings
from logics.data_layer.redis import RedisClient
from logics.data_layer.redis.keys import RedisKeys
from logics.processing.pipeline import run_pipeline

router = APIRouter(prefix="/upload", tags=["upload"])

_ALLOWED_EXTENSIONS = {".pcap", ".pcapng"}


@router.post("/fileupload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload only .pcap and .pcapng files are allowed",
        )
    session_id = str(uuid4())
    session_dir = Path(settings.upload_dir) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    file_path = session_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    # Schedule the processing pipeline to run in the background
    background_tasks.add_task(run_pipeline, session_id, str(file_path))

    return UploadResponse(
        session_id=session_id,
        filename=file.filename,
        message="File Uploaded Successfully and Processing Started in the Background",
    )


@router.get("/status/{session_id}", response_model=ProcessingStatusResponse)
async def get_processing_status(session_id: str):
    """
    Poll the processing status for a previously uploaded PCAP.

    Status values
    -------------
    - ``pending``    – queued, not yet started
    - ``processing`` – actively processing chunks
    - ``completed``  – all data persisted to PostgreSQL
    - ``failed``     – pipeline encountered a fatal error

    The ``progress_pct`` field (0–100) is a rough estimate based on
    packets processed vs total packets detected by capinfos.
    """
    redis = RedisClient.get_client()
    raw = await redis.get(RedisKeys.stats(session_id))
    if not raw:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. "
                   "Ensure the session_id was returned from /upload/fileupload.",
        )

    try:
        stats: dict = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise HTTPException(status_code=500, detail="Corrupted session stats in cache")

    return ProcessingStatusResponse(
        session_id=session_id,
        status=stats.get("status", "unknown"),
        progress_pct=float(stats.get("progress_pct", 0.0)),
        total_packets=int(stats.get("total_packets", 0)),
        total_flows=int(stats.get("total_flows", 0)),
        unique_aps=int(stats.get("unique_aps", 0)),
        unique_clients=int(stats.get("unique_clients", 0)),
        capture_type=stats.get("capture_type"),
        wifi_bands=stats.get("wifi_bands", []),
        channels=stats.get("channels", []),
        error=stats.get("error"),
    )
