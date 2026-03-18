"""
WebSocket Router – Real-time Processing Progress
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides a WebSocket endpoint that streams live processing events for
a PCAP session as they are published by the pipeline.

Usage
-----
Connect to ``ws://<host>/ws/{session_id}`` immediately after calling
``POST /upload/fileupload`` to receive JSON progress messages in real time.

Message schema (each message is a JSON string)
----------------------------------------------
{
    "status":       "processing" | "completed" | "failed",
    "progress_pct": 42.5,
    "total_packets": 120000,
    "packets_done":  50000,
    "chunk":         2,
    "total_flows":   831,
    "unique_aps":    3,
    "unique_clients": 12,
    "capture_type":  "raw_80211",
    "error":         null
}

The stream closes automatically when ``status`` is ``"completed"`` or
``"failed"``.  The client may also close the connection at any time.

Design
------
The pipeline publishes events to the Redis Pub/Sub channel
``session:{session_id}:events`` (see ``RedisKeys.events_channel``).
This endpoint subscribes to that channel and forwards each message
as a WebSocket text frame.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from logics.data_layer.redis import RedisClient
from logics.data_layer.redis.keys import RedisKeys
from logics.log import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["websocket"])

_TERMINAL_STATUSES = {"completed", "failed"}


@router.websocket("/ws/{session_id}")
async def processing_updates(websocket: WebSocket, session_id: str):
    """
    Stream live processing progress events for *session_id*.

    The WebSocket connection stays open until:
    - The pipeline publishes a ``completed`` or ``failed`` status event, or
    - The client closes the connection, or
    - The Redis pub/sub channel produces an error.
    """
    await websocket.accept()
    logger.info("ws.connect | session=%s client=%s", session_id, websocket.client)

    redis = RedisClient.get_client()
    channel = RedisKeys.events_channel(session_id)
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(channel)
        logger.debug("ws.subscribed | channel=%s", channel)

        async for message in pubsub.listen():
            # redis.asyncio yields control messages first (type='subscribe'),
            # then actual data messages (type='message').
            if message.get("type") != "message":
                continue

            raw_data = message.get("data", "")
            if not raw_data:
                continue

            # Forward the raw JSON string directly to the WebSocket client.
            await websocket.send_text(raw_data)

            # Stop if a terminal status was published.
            try:
                payload = json.loads(raw_data)
                if payload.get("status") in _TERMINAL_STATUSES:
                    logger.info(
                        "ws.terminal | session=%s status=%s",
                        session_id, payload.get("status"),
                    )
                    break
            except (json.JSONDecodeError, AttributeError):
                # Non-JSON message — keep listening.
                pass

    except WebSocketDisconnect:
        logger.info("ws.disconnect | session=%s client closed", session_id)
    except Exception as exc:
        logger.error("ws.error | session=%s error=%s", session_id, exc)
        try:
            await websocket.send_text(
                json.dumps({"status": "error", "error": str(exc)})
            )
        except Exception:
            pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("ws.closed | session=%s", session_id)
