#!/usr/bin/env bash
# deploy-all.sh — Master deployment script. Runs all steps in sequence.
#
# Usage: ./scripts/aws/deploy-all.sh
#
# Prerequisites:
#   1. AWS CLI configured (aws configure)
#   2. Docker installed locally (for building Lambda images)
#   3. .env.prod filled in (copy from .env.prod.example)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "═══════════════════════════════════════════════════"
echo "  MMAE Full AWS Deployment"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Architecture:"
echo "    EC2 (free tier) : app + qdrant + mcp-rag"
echo "    RDS (free tier) : PostgreSQL 16"
echo "    Lambda          : mcp-db, mcp-currency, mcp-email"
echo ""
echo "  Steps:"
echo "    1. Setup infrastructure (VPC, RDS, EC2, ECR, Lambda role)"
echo "    2. Deploy Lambda functions (build, push, create)"
echo "    3. Deploy EC2 services (rsync, docker compose)"
echo "    4. Post-deploy (migrations, policy ingestion)"
echo ""
read -p "Press Enter to start (Ctrl+C to abort)..."

echo ""
bash "$SCRIPT_DIR/01-setup-infra.sh"

echo ""
bash "$SCRIPT_DIR/02-deploy-lambdas.sh"

echo ""
bash "$SCRIPT_DIR/03-deploy-ec2.sh"

echo ""
bash "$SCRIPT_DIR/04-post-deploy.sh"
