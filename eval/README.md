# MMGA Toolkit

CLI + Evaluation Suite for the MMGA Expense AI deployment.

## Quick Start — CLI Only (no setup needed)

```bash
unzip mmga-toolkit.zip
chmod +x mmga

# Check system health (prompts for login on first use)
./mmga status

# View logs
./mmga logs

# Check current models
./mmga models
```

**Login credentials:** Ask the team for a reviewer account (e.g. james or tung).

### CLI Commands

| Command | What it does | Needs SSH? |
|---------|-------------|------------|
| `./mmga status` | Health check, models, disk | No |
| `./mmga logs` | Service errors/warnings | No |
| `./mmga models` | Show current LLM/VLM | No |
| `./mmga models set-llm <model>` | Change LLM | No |
| `./mmga models set-vlm <model>` | Change VLM | No |
| `./mmga deploy` | Rsync + rebuild + restart | Yes |
| `./mmga restart` | Restart app container | Yes |
| `./mmga logs agent <claim-id>` | Agent event trace | Yes |
| `./mmga logs download` | Save full logs locally | Yes |
| `./mmga logs clear` | Truncate container logs | Yes |
| `./mmga cleanup` | Prune Docker images | Yes |
| `./mmga ssh` | EC2 shell | Yes |
| `./mmga env` | Show .env.local | Yes |
| `./mmga env set KEY=VALUE` | Update env var | Yes |

## Evaluation Suite (requires Python + API keys)

### Prerequisites

```bash
pip install deepeval litellm playwright
playwright install chromium
```

### Setup

```bash
cp eval/.env.eval eval/.env
# Edit eval/.env — fill in:
#   OPENROUTER_API_KEY=sk-or-v1-...
#   ANTHROPIC_API_KEY=sk-ant-...
source eval/.env
```

### Run

```bash
# Full suite (20 benchmarks against AWS)
python eval/run_eval.py --skip-push --verbose

# Single benchmark
python eval/run_eval.py --benchmark ER-005 --skip-push --verbose

# Re-score without re-capturing
python eval/run_eval.py --skip-capture --skip-push --verbose
```

### Against local Docker (instead of AWS)

```bash
export EVAL_APP_URL=http://localhost:8000
export DATABASE_URL=postgresql://agentic:agentic_password@localhost:5432/agentic_claims
python eval/run_eval.py --skip-push --verbose
```

### Benchmarks (20 total)

| Category | Weight | Benchmarks |
|----------|--------|------------|
| Classification | 15% | ER-001 to ER-004, ER-009 |
| Extraction | 25% | ER-005, ER-006, ER-010, ER-011 |
| Reasoning | 30% | ER-007, ER-008, ER-012 to ER-014, ER-017 |
| Workflow | 10% | ER-015, ER-016 |
| Safety | 20% | ER-018 to ER-020 |
