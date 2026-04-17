"""Lifespan-owned eval worker (Spec B §8.1–8.2).

Single asyncio.Queue(maxsize=1) guards against concurrent full runs.
Started in web/main.py lifespan.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Awaitable, Callable, Optional

from sqlalchemy import text

from agentic_claims.web.db import getAsyncSession

logger = logging.getLogger(__name__)


class EvalOrchestrator:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
        self._running = asyncio.Event()
        self._workerTask: Optional[asyncio.Task] = None

    async def _persistRun(self, *, triggeredBy: str, configJson: dict) -> int:
        async with getAsyncSession() as session:
            result = await session.execute(
                text("""
                    INSERT INTO eval_runs
                      (started_at, status, git_sha, judge_model, verifier_model,
                       config_json, results_path, triggered_by)
                    VALUES (now(), 'queued', :git, :judge, :verifier,
                            cast(:cfg as jsonb), :path, :triggered)
                    RETURNING id
                """),
                {
                    "git": configJson.get("gitSha", "unknown"),
                    "judge": configJson.get("judgeModel", "unknown"),
                    "verifier": configJson.get("verifierModel", "unknown"),
                    "cfg": json.dumps(configJson),
                    "path": configJson.get("resultsPath", ""),
                    "triggered": triggeredBy,
                },
            )
            runId = int(result.scalar_one())
            await session.commit()
        return runId

    async def enqueue(self, *, triggeredBy: str, configJson: Optional[dict] = None) -> int:
        if configJson is None:
            configJson = {}
        if self._queue.full():
            raise RuntimeError("eval run already queued or running")
        runId = await self._persistRun(triggeredBy=triggeredBy, configJson=configJson)
        await self._queue.put(runId)
        return runId

    async def enqueueNonblocking(self, *, triggeredBy: str, configJson: Optional[dict] = None) -> int:
        if configJson is None:
            configJson = {}
        if self._queue.full():
            raise RuntimeError("eval run already queued or running")
        runId = await self._persistRun(triggeredBy=triggeredBy, configJson=configJson)
        self._queue.put_nowait(runId)
        return runId

    async def markOrphansInterrupted(self) -> None:
        async with getAsyncSession() as session:
            await session.execute(text(
                "UPDATE eval_runs SET status='interrupted', finished_at=now() "
                "WHERE status IN ('running','queued')"
            ))
            await session.commit()

    async def workerLoop(self, executeRunFn: Callable[[int], Awaitable[None]]) -> None:
        while True:
            runId = await self._queue.get()
            self._running.set()
            try:
                await executeRunFn(runId)
            except Exception as exc:
                logger.exception("eval run %s failed: %s", runId, exc)
                try:
                    async with getAsyncSession() as session:
                        await session.execute(text(
                            "UPDATE eval_runs SET status='failed', finished_at=now(), "
                            "summary_json=COALESCE(summary_json,'{}'::jsonb) || cast(:err as jsonb) "
                            "WHERE id=:id"
                        ), {"err": json.dumps({"error": str(exc)}), "id": runId})
                        await session.commit()
                except Exception:
                    logger.exception("failed to mark run %s as failed", runId)
            finally:
                self._running.clear()
                self._queue.task_done()

    def isRunning(self) -> bool:
        return self._running.is_set()

    async def start(self, executeRunFn: Callable[[int], Awaitable[None]]) -> None:
        if self._workerTask is None or self._workerTask.done():
            self._workerTask = asyncio.create_task(self.workerLoop(executeRunFn))

    async def stop(self) -> None:
        if self._workerTask is not None:
            self._workerTask.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._workerTask
