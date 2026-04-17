#!/usr/bin/env bash
# deploy-s3.sh — Build images locally, push to S3, pull on EC2, restart.
#
# This is the standard deploy workflow. Run from your local machine.
# Builds Docker images on your Mac, uploads to S3, loads on EC2.
#
# Usage: ./scripts/aws/deploy-s3.sh
#
# Options:
#   --app-only    Only rebuild and deploy the app image
#   --rag-only    Only rebuild and deploy the mcp-rag image
#   --no-build    Skip build, just restart EC2 services
#   --migrate     Run alembic migrations after deploy

set -euo pipefail

# ─── Auto-increment version in .env.local on EC2 ──────────────────
bumpVersion() {
  local envFile="$1"
  if [[ ! -f "$envFile" ]]; then return; fi
  local current
  current=$(grep -E '^APP_VERSION=' "$envFile" | cut -d= -f2- || echo "0.9.0")
  if [[ -z "$current" ]]; then current="0.9.0"; fi
  # Bump patch version: 0.9.0 → 0.9.1
  local major minor patch
  IFS='.' read -r major minor patch <<< "$current"
  patch=$((patch + 1))
  local newVersion="${major}.${minor}.${patch}"
  if grep -q '^APP_VERSION=' "$envFile"; then
    sed -i.bak "s/^APP_VERSION=.*/APP_VERSION=${newVersion}/" "$envFile"
    rm -f "${envFile}.bak"
  else
    echo "APP_VERSION=${newVersion}" >> "$envFile"
  fi
  echo "$newVersion"
}

# ─── Config ────────────────────────────────────────────────────────
S3_BUCKET="mmga-expense-deploy"
S3_PREFIX="images"
EC2_HOST="13.213.13.39"
EC2_USER="ec2-user"
REMOTE_DIR="/opt/mmga-expense"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
REGION="ap-southeast-1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ─── Parse args ────────────────────────────────────────────────────
BUILD_APP=true
BUILD_RAG=true
DO_BUILD=true
DO_MIGRATE=false

for arg in "$@"; do
  case $arg in
    --app-only)  BUILD_RAG=false ;;
    --rag-only)  BUILD_APP=false ;;
    --no-build)  DO_BUILD=false ;;
    --migrate)   DO_MIGRATE=true ;;
  esac
done

log() { echo "[$(date '+%H:%M:%S')] $*"; }

# ─── 1. Build images locally ──────────────────────────────────────
if $DO_BUILD; then
  cd "$PROJECT_ROOT"

  if $BUILD_APP; then
    log "Building mmga-app (linux/amd64)..."
    docker build --platform linux/amd64 -t mmga-app:latest . 2>&1 | tail -3
    log "Uploading mmga-app to S3..."
    docker save mmga-app:latest | gzip | \
      aws s3 cp - "s3://${S3_BUCKET}/${S3_PREFIX}/mmga-app.tar.gz" --region "$REGION"
    log "mmga-app uploaded."
  fi

  if $BUILD_RAG; then
    log "Building mmga-mcp-rag (linux/amd64)..."
    docker build --platform linux/amd64 -t mmga-mcp-rag:latest ./mcp_servers/rag 2>&1 | tail -3
    log "Uploading mmga-mcp-rag to S3..."
    docker save mmga-mcp-rag:latest | gzip | \
      aws s3 cp - "s3://${S3_BUCKET}/${S3_PREFIX}/mmga-mcp-rag.tar.gz" --region "$REGION"
    log "mmga-mcp-rag uploaded."
  fi
fi

# ─── 2. Sync code to EC2 ──────────────────────────────────────────
log "Syncing code to EC2..."
rsync -avz --delete \
  --exclude '.git' --exclude '.DS_Store' --exclude '__pycache__' \
  --exclude '.venv' --exclude '.playwright-mcp' --exclude '.qa' \
  --exclude 'reference-code' --exclude '.env.local' --exclude '.env.prod' \
  --exclude 'poetry.lock' --exclude 'eval' \
  --exclude 'docker-compose.prod.yml' \
  -e "ssh $SSH_OPTS" \
  "$PROJECT_ROOT/" "${EC2_USER}@${EC2_HOST}:/tmp/mmae-update/" 2>&1 | tail -3

ssh $SSH_OPTS "${EC2_USER}@${EC2_HOST}" \
  "sudo rsync -a --exclude='.env.local' --exclude='docker-compose.prod.yml' /tmp/mmae-update/ ${REMOTE_DIR}/"

# ─── 2b. Bump version in .env.local on EC2 ────────────────────────
log "Bumping APP_VERSION on EC2..."
NEW_VERSION=$(ssh $SSH_OPTS "${EC2_USER}@${EC2_HOST}" "
  ENV_FILE=${REMOTE_DIR}/.env.local
  CURRENT=\$(grep -E '^APP_VERSION=' \$ENV_FILE 2>/dev/null | cut -d= -f2- || echo '0.9.0')
  if [ -z \"\$CURRENT\" ]; then CURRENT='0.9.0'; fi
  MAJOR=\$(echo \$CURRENT | cut -d. -f1)
  MINOR=\$(echo \$CURRENT | cut -d. -f2)
  PATCH=\$(echo \$CURRENT | cut -d. -f3)
  PATCH=\$((PATCH + 1))
  NEW=\"\${MAJOR}.\${MINOR}.\${PATCH}\"
  if grep -q '^APP_VERSION=' \$ENV_FILE 2>/dev/null; then
    sed -i \"s/^APP_VERSION=.*/APP_VERSION=\${NEW}/\" \$ENV_FILE
  else
    echo \"APP_VERSION=\${NEW}\" >> \$ENV_FILE
  fi
  echo \$NEW
")
log "Version bumped to ${NEW_VERSION}"

# ─── 3. Pull images and restart on EC2 ────────────────────────────
log "Loading images and restarting services on EC2..."
ssh $SSH_OPTS "${EC2_USER}@${EC2_HOST}" << REMOTE
set -ex
cd ${REMOTE_DIR}

# Load images from S3
$($BUILD_APP && echo 'aws s3 cp s3://${S3_BUCKET}/${S3_PREFIX}/mmga-app.tar.gz - | docker load' || echo 'echo "Skipping app image"')
$($BUILD_RAG && echo 'aws s3 cp s3://${S3_BUCKET}/${S3_PREFIX}/mmga-mcp-rag.tar.gz - | docker load' || echo 'echo "Skipping rag image"')

# Restart
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# Wait for healthy
sleep 15
docker compose -f docker-compose.prod.yml ps
REMOTE

# ─── 4. Optional: run migrations ──────────────────────────────────
if $DO_MIGRATE; then
  log "Running database migrations..."
  ssh $SSH_OPTS "${EC2_USER}@${EC2_HOST}" \
    "cd ${REMOTE_DIR} && docker compose -f docker-compose.prod.yml exec -T app python -m alembic upgrade head"
fi

log "Deploy complete → https://mmga.mdaie-sutd.fit"
