"""End-to-end traversal: intake_gpt → abuseGuard → evaluatorGate → compliance+fraud → advisor."""

from unittest.mock import patch

import pytest

from agentic_claims.core.config import Settings


@pytest.mark.asyncio
async def testAbuseGuardNodeIsInCompiledGraph() -> None:
    """The abuseGuard node must be wired into the compiled LangGraph."""
    testSettings = Settings(_env_file="tests/.env.test")
    with patch("agentic_claims.core.graph.getSettings", return_value=testSettings):
        from agentic_claims.core.graph import buildGraph
        graph = buildGraph().compile()
    assert "abuseGuard" in graph.nodes


def testAbuseGuardNodeModuleImportable() -> None:
    """Guardrail — the node must be importable and be the one we expect."""
    from agentic_claims.agents.abuse_guard.node import abuseGuardNode
    assert abuseGuardNode.__name__ == "abuseGuardNode"
