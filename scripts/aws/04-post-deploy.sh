#!/usr/bin/env bash
# 04-post-deploy.sh — Run database migrations and ingest policies.
#
# Executes on EC2 via SSH after docker compose is running.
#
# Usage: ./scripts/aws/04-post-deploy.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
load_state

for var in EC2_PUBLIC_IP RDS_ENDPOINT; do
  if [[ -z "${!var:-}" ]]; then
    err "$var not set. Run previous scripts first."
    exit 1
  fi
done

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i $EC2_KEY_FILE"
SSH_CMD="ssh $SSH_OPTS ec2-user@${EC2_PUBLIC_IP}"
REMOTE_DIR="/home/ec2-user/mmae"

# ════════════════════════════════════════════════════════════════════
# 1. Run Alembic migrations
# ═════════��══════════════════════════════════���═══════════════════════
log "Running database migrations..."

$SSH_CMD << 'REMOTE'
set -ex
cd /home/ec2-user/mmae

# Run migrations inside the app container
docker compose -f docker-compose.prod.yml exec -T app \
  python -m alembic upgrade head

echo "Migrations complete."
REMOTE

ok "Database migrations applied"

# ════════════════════════════════════════════════════════════════════
# 2. Ingest policy documents into Qdrant
# ═══════════���═════════════════════════════���══════════════════════════
log "Ingesting policy documents into Qdrant..."

$SSH_CMD << 'REMOTE'
set -ex
cd /home/ec2-user/mmae

# Run ingestion script inside app container (Qdrant is on Docker network)
docker compose -f docker-compose.prod.yml exec -T app \
  python scripts/ingest_policies.py

echo "Policy ingestion complete."
REMOTE

ok "Policy documents ingested into Qdrant"

# ════════════════════════════════════════════════════════════════════
# 3. Health checks
# ════════════════════════════════════════════════════════════════════
log "Running health checks..."

$SSH_CMD << 'REMOTE'
set -e
cd /home/ec2-user/mmae

echo "=== Container Status ==="
docker compose -f docker-compose.prod.yml ps

echo ""
echo "=== App Health ==="
curl -sf http://localhost:80/ > /dev/null && echo "App: OK" || echo "App: FAIL"

echo ""
echo "=== Qdrant Health ==="
curl -sf http://localhost:6333/collections/expense_policies | python3 -c "
import sys, json
data = json.load(sys.stdin)
count = data.get('result', {}).get('points_count', 0)
print(f'Qdrant: {count} policy vectors loaded')
" 2>/dev/null || echo "Qdrant: FAIL"

echo ""
echo "=== MCP RAG Health ==="
HTTP_CODE=$(curl -so /dev/null -w '%{http_code}' http://localhost:8001/mcp 2>/dev/null || echo "000")
echo "MCP RAG: HTTP $HTTP_CODE (406 = healthy)"
REMOTE

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Post-Deploy Complete"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  App:  http://${EC2_PUBLIC_IP}"
echo "  SSH:  ssh -i $EC2_KEY_FILE ec2-user@${EC2_PUBLIC_IP}"
echo ""
echo "  Deployment finished!"
echo "═════════════════════════════════��═════════════════"
