#!/usr/bin/env bash
# Shared configuration for all AWS deployment scripts.
# Edit these values before first deploy.

set -euo pipefail

# ─── Project ────────────────────────────────────────────────────────
export PROJECT="mmae"
export AWS_REGION="${AWS_REGION:-ap-southeast-1}"
export AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo 'UNKNOWN')}"

# ─── Networking ─────────────────────────────────────────────────────
export VPC_CIDR="10.0.0.0/16"
export SUBNET_PUBLIC_1_CIDR="10.0.1.0/24"
export SUBNET_PUBLIC_2_CIDR="10.0.2.0/24"
export SUBNET_PRIVATE_1_CIDR="10.0.10.0/24"
export SUBNET_PRIVATE_2_CIDR="10.0.11.0/24"

# ─── RDS (free tier: db.t3.micro, 20 GB) ──────────────────────────
export RDS_INSTANCE_CLASS="db.t3.micro"
export RDS_DB_NAME="agentic_claims"
export RDS_USERNAME="agentic"
export RDS_STORAGE_GB=20
export RDS_IDENTIFIER="${PROJECT}-postgres"

# ─── EC2 (free tier: t2.micro) ────────────────────────────────────
export EC2_INSTANCE_TYPE="t2.micro"
export EC2_KEY_NAME="${PROJECT}-key"
export EC2_KEY_FILE="$HOME/.ssh/${EC2_KEY_NAME}.pem"

# ─── ECR Repositories ─────────────────────────────────────────────
export ECR_REPOS=("${PROJECT}-mcp-db" "${PROJECT}-mcp-currency" "${PROJECT}-mcp-email")

# ─── Lambda ────────────────────────────────────────────────────────
export LAMBDA_TIMEOUT=60
export LAMBDA_MEMORY=512
export LAMBDA_ROLE_NAME="${PROJECT}-lambda-role"

# ─── Tag helpers ───────────────────────────────────────────────────
TAGS="Key=Project,Value=${PROJECT} Key=Environment,Value=prod Key=ManagedBy,Value=script"

# ─── State file (tracks resource IDs across scripts) ──────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="${SCRIPT_DIR}/.deploy-state"

save_state() { echo "$1=$2" >> "$STATE_FILE"; }

load_state() {
  if [[ -f "$STATE_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$STATE_FILE"
  fi
}

get_state() {
  load_state
  local var="$1"
  echo "${!var:-}"
}

# ─── Logging ───────────────────────────────────────────────────────
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
err()  { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; }
ok()   { echo "[$(date '+%H:%M:%S')] ✓ $*"; }
warn() { echo "[$(date '+%H:%M:%S')] WARN: $*" >&2; }
