# Implementation Plan: Post-Submission Agents (Compliance, Fraud, Advisor)

## Overview

Replace three stub agent nodes with deterministic (no-LLM) implementations that:
- **Compliance**: validate claims against hardcoded policy rules, call RAG MCP for clause citations
- **Fraud**: query DB MCP for duplicate receipts and category averages, compute risk score
- **Advisor**: synthesize compliance+fraud findings into approve/return/escalate decision, update DB, send email

All three agents follow the Direct Implementation pattern (not ReAct) -- deterministic logic, no LLM calls, faster and more testable.

---

## Critical Design Constraint: MCP Mocking in Tests

The tests patch `agentic_claims.agents.{agent}.node.mcpCallTool`. This means each `node.py` must import `mcpCallTool` directly at module level:

```python
from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
```

Tests 1-5 for compliance and tests 1, 5-6 for fraud do NOT mock `mcpCallTool`. The node must handle MCP unavailability gracefully (try/except with fallback to hardcoded rules) so these tests pass without a running MCP server.

---

## Agent 1: Compliance Node

### File: `src/agentic_claims/agents/compliance/node.py`

**Imports:**
```python
from datetime import datetime, date
import logging
from langchain_core.messages import AIMessage
from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
from agentic_claims.core.config import getSettings
from agentic_claims.core.state import ClaimState
```

**Hardcoded Policy Constants** (top of module):
```python
# Policy caps from meals.md Section 2
MEAL_CAPS = {
    "breakfast": 15.0,
    "lunch": 20.0,
    "dinner": 30.0,
    "daily": 50.0,
}
OVERSEAS_MULTIPLIER = 1.5

# Submission deadline from general.md Section 1
SUBMISSION_DEADLINE_DAYS = 30

# Approval thresholds from general.md Section 3
APPROVAL_THRESHOLDS = {
    "auto": 200.0,       # < SGD 200 auto-approve
    "manager": 1000.0,   # SGD 200-1000 manager approval
    # > SGD 1000 dept head approval
}
```

**Function signature:**
```python
async def complianceNode(state: ClaimState) -> dict:
```

**Logic flow:**
1. Extract receipt fields from `state["extractedReceipt"]["fields"]`
2. Initialize `violations: list[dict]` and `citedClauses: list[dict]`
3. **Budget cap check**: if category is "meals", compare totalAmount against MEAL_CAPS["daily"] (SGD 50). If exceeds, append violation `{"description": "Meal total SGD {amount} exceeds daily cap of SGD 50", "severity": "high"}` and cited clause `{"policy": "meals.md", "section": "Section 2", "clause": "Daily meal cap is SGD 50 per day"}`
4. **Submission deadline check**: parse receipt date, compute days_elapsed from today. If > 30, append violation about expired submission and cite general.md Section 1
5. **Approval threshold check**: if totalAmount > 1000, add cited clause `{"policy": "general.md", "section": "Section 3", "clause": "Claims above SGD 1000 require dept head approval"}`. This is NOT a violation (the test checks citedClauses, not violations[pass=False])
6. **RAG MCP enrichment** (try/except): call `mcpCallTool(settings.rag_mcp_url, "searchPolicies", {"query": f"{category} expense policy", "limit": 3})` to get additional policy text. If results come back, merge into citedClauses. On failure, log warning and continue with hardcoded clauses.
7. Compute `passResult = len(violations) == 0`
8. Build and return:
```python
{
    "complianceFindings": {
        "pass": passResult,
        "violations": violations,
        "citedClauses": citedClauses,
    },
    "messages": [AIMessage(content=summaryMessage)],
}
```

**Summary message format:**
- Pass: "Compliance check passed. Claim SGD {amount} for {category} is within policy limits."
- Fail: "Compliance check failed. {len(violations)} violation(s) found: {violation descriptions}"

**No separate tools file needed.** The original plan suggested `compliance/tools/searchPolicies.py`, but since compliance is NOT a ReAct agent, it does not need `@tool`-decorated functions. The node calls `mcpCallTool` directly, matching the test mock path `agentic_claims.agents.compliance.node.mcpCallTool`.

### Test Compatibility Analysis

| Test | Mocks MCP? | How it passes |
|------|-----------|---------------|
| 1. Returns structure | No | Hardcoded rules produce structure without MCP |
| 2. Over-budget SGD 80 | No | Hardcoded MEAL_CAPS["daily"]=50, 80>50 triggers violation |
| 3. Clean SGD 18.50 | No | 18.50<50, no deadline issue, passes |
| 4. Expired receipt 2026-01-15 | No | Days since 2026-01-15 > 30, triggers violation |
| 5. Approval threshold SGD 1500 | No | 1500>1000, adds citedClause mentioning "1000"/"dept head"/"approval" |
| 6. Calls searchPolicies | Yes | Mock verifies mcpCallTool called with "searchPolicies" |
| 7. Cites specific clauses | No | Hardcoded citedClauses have policy/section/clause keys |

**Issue with tests 1-5 not mocking MCP:** The node calls `mcpCallTool` which will raise ConnectionError in test env. Solution: wrap MCP call in try/except, log warning on failure, continue with hardcoded clauses. Tests 1-5 will hit the except path; test 6 mocks it to verify the call path.

---

## Agent 2: Fraud Node

### File: `src/agentic_claims/agents/fraud/node.py`

**Imports:**
```python
import logging
from langchain_core.messages import AIMessage
from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
from agentic_claims.core.config import getSettings
from agentic_claims.core.state import ClaimState
```

**Constants:**
```python
DUPLICATE_RISK_SCORE = 0.9    # Risk score contribution for duplicate detection
ANOMALY_RISK_SCORE = 0.5      # Risk score contribution for anomalous amount
ANOMALY_MULTIPLIER = 3.0      # Amount must be Nx above average to flag
```

**Function signature:**
```python
async def fraudNode(state: ClaimState) -> dict:
```

**Logic flow:**
1. Extract receipt fields: merchant, date, totalAmount, currency, category
2. Initialize `duplicates: list[dict]`, `anomalies: list[dict]`, `riskScore = 0.0`
3. **Duplicate check** (MCP call 1): call `mcpCallTool(settings.db_mcp_url, "executeQuery", {"query": sqlQuery})` where sqlQuery is:
   ```sql
   SELECT c.claim_id, c.claim_number, r.merchant, r.receipt_date, r.total_amount, c.employee_id
   FROM claims c JOIN receipts r ON c.claim_id = r.claim_id
   WHERE r.merchant = '{merchant}' AND r.receipt_date = '{date}' AND r.total_amount = {totalAmount}
   AND c.claim_number != '{claimId}'
   ```
   If results non-empty, populate `duplicates` list and add `DUPLICATE_RISK_SCORE` to riskScore.
4. **Anomaly check** (MCP call 2): call `mcpCallTool(settings.db_mcp_url, "executeQuery", {"query": avgQuery})` where avgQuery is:
   ```sql
   SELECT AVG(r.total_amount) as avg_amount, '{category}' as category
   FROM receipts r JOIN claims c ON c.claim_id = r.claim_id
   WHERE c.status != 'rejected'
   ```
   If avg_amount exists and totalAmount > avg_amount * ANOMALY_MULTIPLIER, append anomaly and add `ANOMALY_RISK_SCORE` to riskScore.
5. **Clamp risk score** to [0.0, 1.0]: `riskScore = min(riskScore, 1.0)`
6. Return:
```python
{
    "fraudFindings": {
        "riskScore": riskScore,
        "duplicates": duplicates,
        "anomalies": anomalies,
    },
    "messages": [AIMessage(content=summaryMessage)],
}
```

**No separate tools file needed.** Same reasoning as compliance -- direct `mcpCallTool` calls, not `@tool` wrappers.

### Test Compatibility Analysis

| Test | Mocks MCP? | How it passes |
|------|-----------|---------------|
| 1. Returns structure | No | try/except on MCP, returns empty findings with riskScore=0.0 |
| 2. Detects duplicate | Yes | Mock returns matching record, duplicates populated, riskScore>0 |
| 3. Passes unique | Yes | Mock returns [], riskScore==0.0, duplicates==[] |
| 4. Calls executeQuery | Yes | Mock verifies mcpCallTool called with "executeQuery" |
| 5. Anomalous amount | Yes | side_effect=[[], [{avg_amount: 40}]], 500>40*3, anomaly flagged |
| 6. Risk score [0,1] | Yes | Mock returns [], clamped to [0.0, 1.0] |

**Issue with test 1 not mocking MCP:** Same solution as compliance -- try/except around MCP calls. When MCP fails, return `{riskScore: 0.0, duplicates: [], anomalies: []}` with a warning message.

### SQL Injection Note

The SQL query uses string interpolation with values from `extractedReceipt`. Since these values come from VLM extraction (our own pipeline, not user input) and `executeQuery` is SELECT-only, the risk is low. However, for defense-in-depth, use parameterized-style queries if the MCP supports them. If not, at minimum sanitize single quotes in merchant names by replacing `'` with `''`.

---

## Agent 3: Advisor Node

### File: `src/agentic_claims/agents/advisor/node.py`

**Imports:**
```python
import logging
from langchain_core.messages import AIMessage
from agentic_claims.agents.intake.utils.mcpClient import mcpCallTool
from agentic_claims.core.config import getSettings
from agentic_claims.core.state import ClaimState
```

**Constants:**
```python
FRAUD_RISK_THRESHOLD = 0.5     # riskScore above this triggers escalation
NOTIFICATION_RECIPIENT = "claims@company.com"  # Default notification email
```

**Function signature:**
```python
async def advisorNode(state: ClaimState) -> dict:
```

**Decision matrix:**

| Compliance Pass | Fraud Risk | Action | Status |
|----------------|------------|--------|--------|
| True | < 0.5 | approve | approved |
| False | < 0.5 | return | returned |
| any | >= 0.5 | escalate | escalated |
| True | >= 0.5 (disagreement) | escalate | escalated |

The key insight from the tests: when compliance passes but fraud flags exist (riskScore >= threshold OR non-empty anomalies), the conservative action is ESCALATE.

**Logic flow:**
1. Read `state["complianceFindings"]` and `state["fraudFindings"]`
2. Handle None/missing findings defensively (default to pass=True, riskScore=0.0)
3. **Decision logic:**
   ```python
   compliancePass = complianceFindings.get("pass", True)
   riskScore = fraudFindings.get("riskScore", 0.0)
   hasFraudFlags = riskScore >= FRAUD_RISK_THRESHOLD or len(fraudFindings.get("anomalies", [])) > 0
   
   if hasFraudFlags:
       action = "escalate"
       status = "escalated"
   elif not compliancePass:
       action = "return"
       status = "returned"
   else:
       action = "approve"
       status = "approved"
   ```
4. **Build reasoning string** incorporating:
   - Compliance result and violation summaries (with policy citations from citedClauses)
   - Fraud risk score and any duplicate/anomaly descriptions
   - The decision rationale
   - Example for return: "Claim returned due to compliance violation: Meal total SGD 80 exceeds daily cap of SGD 50. Policy: meals.md Section 2."
5. **Update DB** (try/except): call `mcpCallTool(settings.db_mcp_url, "updateClaimStatus", {"claimId": int(state["claimId"]), "newStatus": status, "actor": "advisor-agent"})`
6. **Send email notification** (try/except): call `mcpCallTool(settings.email_mcp_url, "sendClaimNotification", {"to": NOTIFICATION_RECIPIENT, "claimNumber": state["claimId"], "status": status, "message": reasoning})`
7. Return:
```python
{
    "advisorDecision": {
        "action": action,
        "reasoning": reasoning,
    },
    "status": status,
    "messages": [AIMessage(content=f"Advisor decision: {action}. {reasoning}")],
}
```

**No separate tools files needed.** Direct `mcpCallTool` calls in the node.

### Test Compatibility Analysis

| Test | Mocks MCP? | How it passes |
|------|-----------|---------------|
| 1. Returns decision | No | try/except on MCP, decision computed from findings |
| 2. Auto-approve clean | No | pass=True, risk=0.0 -> approve |
| 3. Return with violations | No | pass=False, risk=0.1 -> return, reasoning mentions "violation"/"exceed"/"cap" |
| 4. Escalate suspicious | No | risk=0.85 -> escalate |
| 5. Escalate disagreement | No | pass=True, risk=0.6+anomalies -> escalate |
| 6. Updates DB status | Yes | Mock verifies "updateClaimStatus" called |
| 7. Sends email | Yes | Mock verifies "sendClaimNotification" called |
| 8. Cites policy clauses | No | reasoning built from complianceFindings citedClauses, contains "meals"/"section"/"policy" |

### Reasoning String Construction for Test 8

The advisor must forward policy citations from `complianceFindings["citedClauses"]` into its reasoning. For the violationClaimState fixture:
```python
citedClauses = [{"policy": "meals.md", "section": "Section 2", "clause": "Daily meal cap is SGD 50 per day"}]
```
The reasoning should include something like: "Policy meals.md Section 2: Daily meal cap is SGD 50 per day"

---

## File Creation Summary

### Files to CREATE (4 files):

None -- no separate tools files needed. The original plan suggested tools subdirectories, but since these agents call `mcpCallTool` directly (matching the test mock paths), all logic lives in `node.py`.

### Files to MODIFY (3 files):

1. **`src/agentic_claims/agents/compliance/node.py`** -- Replace 22-line stub with ~80-line implementation
2. **`src/agentic_claims/agents/fraud/node.py`** -- Replace 22-line stub with ~90-line implementation  
3. **`src/agentic_claims/agents/advisor/node.py`** -- Replace 22-line stub with ~100-line implementation

### Files NOT modified:
- `state.py` -- already has all needed fields
- `graph.py` -- topology is correct, no changes needed
- `config.py` -- already has all MCP URL settings
- `mcpClient.py` -- shared utility, no changes needed

---

## Implementation Order

1. **Compliance node first** -- simplest, no dependencies on other agents, 7 tests
2. **Fraud node second** -- similar pattern to compliance, 6 tests
3. **Advisor node third** -- depends on compliance+fraud output shapes, 8 tests
4. **Run full test suite** to verify no regressions in existing tests

---

## Edge Cases to Handle

1. **Missing extractedReceipt**: if `state.get("extractedReceipt")` is None, return pass=True with empty violations (compliance), riskScore=0.0 (fraud), or approve (advisor)
2. **Missing fields in extractedReceipt**: use `.get()` with defaults throughout
3. **MCP connection failures**: try/except around all `mcpCallTool` calls, log warnings, continue with deterministic fallback
4. **claimId type mismatch**: tests use string IDs like "test-compliance-001" but `updateClaimStatus` expects int. The advisor should try `int(claimId)` and handle ValueError by passing the string as-is
5. **Date parsing**: receipt dates should be in ISO format (YYYY-MM-DD). Use `datetime.strptime` with fallback
6. **SQL injection in merchant names**: sanitize single quotes in SQL string interpolation for fraud queries

---

## Key Design Decisions

1. **No `@tool` wrappers** -- these agents are not ReAct, they don't need LangChain tool decorators. Direct function calls to `mcpCallTool` are simpler and match the test mock paths.
2. **Hardcoded policy constants** -- deterministic rules don't need RAG lookup. MCP enrichment is optional/additive.
3. **try/except around MCP** -- enables tests without mocking and production resilience.
4. **Risk score is additive and clamped** -- duplicate=0.9, anomaly=0.5, max=1.0.
5. **Conservative escalation** -- any fraud signal overrides compliance pass (test 5 confirms this).
