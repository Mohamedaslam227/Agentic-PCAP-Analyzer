"""
Chat Router
~~~~~~~~~~~
Routes incoming chat queries to ChatService, which performs
hybrid flow retrieval (vector search + fallback scan), per-AP retry
aggregation, and calls an LLM to generate an engineer-grade answer.

Endpoints
---------
POST /chat          – returns a single JSON answer (buffered)
POST /chat/stream   – streams the answer token-by-token via SSE
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from logics.api.models.schema import ChatRequest, ChatResponse
from logics.api.routers.auth import get_current_user
from logics.chat.service import ChatService
from logics.log import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a natural-language question about a processed PCAP session.

    The system:
    1. Verifies the session was fully processed.
    2. Embeds the question via HTTP embedding service (or local fallback).
    3. Hybrid retrieval: pgvector cosine search → fallback full scan if < 5 hits.
    4. Loads per-AP retry aggregation leaderboard.
    5. Loads enriched AP inventory (inventory + capabilities + flow stats).
    6. Loads last 6 conversation turns for multi-turn context.
    7. Builds prompt and calls LLM.
    8. Caches answer in Redis (5 min TTL) and persists to chat_messages.

    Requires ``Authorization: Bearer <access_token>`` header.
    """
    try:
        answer = await ChatService().process_query(
            request.session_id, request.message
        )
    except ValueError as exc:
        # Session not found or not yet completed
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("chat.router | session=%s error=%s", request.session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the chat query.",
        )

    return ChatResponse(session_id=request.session_id, answer=answer)


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Stream a natural-language answer token-by-token using Server-Sent Events.

    Identical pipeline to ``POST /chat`` but the LLM response is forwarded
    to the client incrementally as each token arrives, so the UI can start
    rendering before the full answer is ready.

    Wire format
    -----------
    Each event is a line:

    .. code-block:: text

        data: {"token": "<chunk>", "done": false}\\n\\n
        data: {"token": "<chunk>", "done": false}\\n\\n
        ...
        data: {"done": true, "answer": "<full text>", "cached": false}\\n\\n

    On a cache hit the stream emits exactly two events: the cached answer as
    a single token event followed by the done event (``"cached": true``).

    On error the stream emits:

    .. code-block:: text

        data: {"error": "<message>", "done": true}\\n\\n

    Client-side (JavaScript / EventSource)
    ----------------------------------------
    .. code-block:: javascript

        const es = new EventSource('/chat/stream?...');
        // Or with POST + fetch:
        const res = await fetch('/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer <token>'
            },
            body: JSON.stringify({ session_id: '...', message: '...' })
        });
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const lines = decoder.decode(value).split('\\n\\n');
            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const event = JSON.parse(line.slice(6));
                if (!event.done) process.stdout.write(event.token);
                else console.log('\\n[stream done]', event.answer);
            }
        }

    Requires ``Authorization: Bearer <access_token>`` header.
    """
    svc = ChatService()

    async def event_generator():
        try:
            async for sse_line in svc.stream_query(request.session_id, request.message):
                yield sse_line
        except ValueError as exc:
            import json as _json
            yield f'data: {_json.dumps({"error": str(exc), "done": True})}\n\n'
        except Exception as exc:
            import json as _json
            logger.error(
                "chat.stream | session=%s error=%s", request.session_id, exc
            )
            yield f'data: {_json.dumps({"error": "Internal server error", "done": True})}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Connection": "keep-alive",
        },
    )
