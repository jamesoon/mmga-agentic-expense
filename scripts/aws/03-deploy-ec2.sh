#!/usr/bin/env bash
# 03-deploy-ec2.sh — Sync project to EC2 and run docker compose.
#
# Copies source code, .env.prod, and docker-compose.prod.yml to EC2,
# then builds and starts the services (app, qdrant, mcp-rag).
#
# Usage: ./scripts/aws/03-deploy-ec2.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
load_state

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Validate
for var in EC2_INSTANCE_ID EC2_PUBLIC_IP; do
  if [[ -z "${!var:-}" ]]; then
    err "$var not set. Run 01-setup-infra.sh first."
    exit 1
  fi
done

if [[ ! -f "$EC2_KEY_FILE" ]]; then
  err "SSH key not found: $EC2_KEY_FILE"
  exit 1
fi

SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -i $EC2_KEY_FILE"
SSH_CMD="ssh $SSH_OPTS ec2-user@${EC2_PUBLIC_IP}"
SCP_CMD="scp $SSH_OPTS"

# ���═══════════════════════════════════════════════════════════════════
# 1. Wait for EC2 Docker to be ready
# ══════════��═════════════════════════════��═══════════════════════════
log "Waiting for EC2 Docker setup to complete..."
for i in $(seq 1 30); do
  if $SSH_CMD "test -f /tmp/docker-ready" 2>/dev/null; then
    ok "Docker is ready on EC2"
    break
  fi
  if [[ $i -eq 30 ]]; then
    err "Timed out waiting for Docker on EC2. SSH in and check user-data logs."
    exit 1
  fi
  sleep 10
done

# ═════════════════���══════════════════════════════════════════════════
# 2. Sync project files to EC2
# ═════════════════════════════════════════════���══════════════════════
log "Syncing project to EC2..."

REMOTE_DIR="/home/ec2-user/mmae"
$SSH_CMD "mkdir -p $REMOTE_DIR"

# rsync the essential files (exclude large/unnecessary dirs)
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.git 2' \
  --exclude '.claude 2' \
  --exclude '.planning 2' \
  --exclude '.DS_Store' \
  --exclude '__pycache__' \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude '.playwright-mcp' \
  --exclude '.qa' \
  --exclude 'reference-code' \
  --exclude 'project-reports' \
  --exclude 'project-rubrics' \
  --exclude 'eval' \
  --exclude 'poetry.lock' \
  --exclude '.env.local' \
  --exclude '.env.prod.example' \
  --exclude 'scripts/aws/.deploy-state' \
  -e "ssh $SSH_OPTS" \
  "$PROJECT_ROOT/" "ec2-user@${EC2_PUBLIC_IP}:${REMOTE_DIR}/"

ok "Project synced to EC2:${REMOTE_DIR}"

# ═══════���════════════════════════════════���═══════════════════════════
# 3. Build and start services
# ════════════════════���═══════════════════════════════════════════════
log "Building and starting Docker services on EC2..."

$SSH_CMD << REMOTE
set -ex
cd $REMOTE_DIR

# Export RDS_ENDPOINT for docker-compose.prod.yml variable substitution
export RDS_ENDPOINT="${RDS_ENDPOINT}"
set -a; source .env.prod; set +a

# Pull base images first
docker pull qdrant/qdrant:latest

# Build and start
docker compose -f docker-compose.prod.yml up -d --build

# Show status
echo ""
echo "Container status:"
docker compose -f docker-compose.prod.yml ps
REMOTE

ok "Services started on EC2"

echo ""
echo "════════════���══════════════════════════════════════"
echo "  EC2 Deployment Complete"
echo "═════��══════════════════════════════════════���══════"
echo "  App URL:  http://${EC2_PUBLIC_IP}"
echo "  EC2 SSH:  ssh -i $EC2_KEY_FILE ec2-user@${EC2_PUBLIC_IP}"
echo ""
echo "  Next: ./scripts/aws/04-post-deploy.sh"
echo "═════���═════════════════════════��═══════════════════"
