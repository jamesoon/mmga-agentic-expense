"""Eval orchestrator tests — queue behavior + crash recovery."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from agentic_claims.eval_worker.orchestrator import EvalOrchestrator


@pytest.mark.asyncio
async def testEnqueueBelowCapReturnsRunId() -> None:
    orch = EvalOrchestrator()
    with patch.object(orch, "_persistRun", AsyncMock(return_value=42)):
        runId = await orch.enqueue(triggeredBy="test")
    assert runId == 42


@pytest.mark.asyncio
async def testEnqueueWhenFullRaises() -> None:
    orch = EvalOrchestrator()
    await orch._queue.put(1)
    with pytest.raises(RuntimeError):
        await orch.enqueueNonblocking(triggeredBy="test")


@pytest.mark.asyncio
async def testIsRunningReflectsEvent() -> None:
    orch = EvalOrchestrator()
    assert orch.isRunning() is False
    orch._running.set()
    assert orch.isRunning() is True
    orch._running.clear()
    assert orch.isRunning() is False
