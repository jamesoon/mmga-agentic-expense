#!/usr/bin/env bash
# 02-deploy-lambdas.sh — Build, push, and create/update Lambda functions
# for mcp-db, mcp-currency, mcp-email.
#
# Each Lambda uses a container image with AWS Lambda Web Adapter, so the
# existing MCP server code runs unchanged.
#
# Usage: ./scripts/aws/02-deploy-lambdas.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
load_state

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Validate prerequisites
for var in VPC_ID SUBNET_PRIV_1 SUBNET_PRIV_2 SG_LAMBDA LAMBDA_ROLE_ARN RDS_ENDPOINT; do
  if [[ -z "${!var:-}" ]]; then
    err "$var not set. Run 01-setup-infra.sh first."
    exit 1
  fi
done

RDS_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' "$PROJECT_ROOT/.env.prod" | cut -d= -f2-)

# ECR login
log "Logging into ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# ════════════════════════════════════════════════════════════════════
# Build, push, deploy each Lambda
# ════════════════════════════════════════════════════════════════════
deploy_lambda() {
  local name="$1"        # e.g. mcp-db
  local server_dir="$2"  # e.g. mcp_servers/db
  local env_json="$3"    # JSON env vars for the function

  local repo="${PROJECT}-${name}"
  local image_uri="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${repo}:latest"
  local fn_name="${PROJECT}-${name}"

  log "Building $name..."
  docker build -t "${repo}:latest" \
    -f "$PROJECT_ROOT/${server_dir}/Dockerfile.lambda" \
    "$PROJECT_ROOT/${server_dir}"

  log "Tagging and pushing $name to ECR..."
  docker tag "${repo}:latest" "$image_uri"
  docker push "$image_uri"

  # Create or update function
  if aws lambda get-function --function-name "$fn_name" --region "$AWS_REGION" > /dev/null 2>&1; then
    log "Updating Lambda function $fn_name..."
    aws lambda update-function-code \
      --function-name "$fn_name" \
      --image-uri "$image_uri" \
      --region "$AWS_REGION" > /dev/null
    aws lambda wait function-updated --function-name "$fn_name" --region "$AWS_REGION"

    aws lambda update-function-configuration \
      --function-name "$fn_name" \
      --timeout "$LAMBDA_TIMEOUT" \
      --memory-size "$LAMBDA_MEMORY" \
      --environment "$env_json" \
      --region "$AWS_REGION" > /dev/null
    aws lambda wait function-updated --function-name "$fn_name" --region "$AWS_REGION"
  else
    log "Creating Lambda function $fn_name..."
    aws lambda create-function \
      --function-name "$fn_name" \
      --package-type Image \
      --code "ImageUri=$image_uri" \
      --role "$LAMBDA_ROLE_ARN" \
      --timeout "$LAMBDA_TIMEOUT" \
      --memory-size "$LAMBDA_MEMORY" \
      --environment "$env_json" \
      --vpc-config "SubnetIds=${SUBNET_PRIV_1},${SUBNET_PRIV_2},SecurityGroupIds=${SG_LAMBDA}" \
      --region "$AWS_REGION" > /dev/null
    aws lambda wait function-active --function-name "$fn_name" --region "$AWS_REGION"
  fi

  # Create or get Function URL
  local fn_url
  fn_url=$(aws lambda get-function-url-config --function-name "$fn_name" \
    --query 'FunctionUrl' --output text --region "$AWS_REGION" 2>/dev/null || echo "")

  if [[ -z "$fn_url" || "$fn_url" == "None" ]]; then
    fn_url=$(aws lambda create-function-url-config \
      --function-name "$fn_name" \
      --auth-type NONE \
      --query 'FunctionUrl' --output text --region "$AWS_REGION")

    # Allow public access to function URL
    aws lambda add-permission \
      --function-name "$fn_name" \
      --statement-id "FunctionURLPublicAccess" \
      --action "lambda:InvokeFunctionUrl" \
      --principal "*" \
      --function-url-auth-type NONE \
      --region "$AWS_REGION" > /dev/null 2>&1 || true
  fi

  ok "$fn_name deployed → $fn_url"
  echo "$fn_url"
}

# ─── mcp-db (needs DATABASE_URL for RDS) ──────────────────────────
DB_ENV="{\"Variables\":{\"FASTMCP_HOST\":\"0.0.0.0\",\"DATABASE_URL\":\"postgresql://${RDS_USERNAME}:${RDS_PASSWORD}@${RDS_ENDPOINT}:5432/${RDS_DB_NAME}\"}}"
DB_URL=$(deploy_lambda "mcp-db" "mcp_servers/db" "$DB_ENV")
save_state LAMBDA_URL_MCP_DB "${DB_URL}mcp/"

# ─── mcp-currency (no special env) ────────────────────────────────
CURRENCY_ENV='{"Variables":{"FASTMCP_HOST":"0.0.0.0"}}'
CURRENCY_URL=$(deploy_lambda "mcp-currency" "mcp_servers/currency" "$CURRENCY_ENV")
save_state LAMBDA_URL_MCP_CURRENCY "${CURRENCY_URL}mcp/"

# ─── mcp-email (SMTP config) ──────────────────────────────────────
SMTP_HOST=$(grep -E '^SMTP_HOST=' "$PROJECT_ROOT/.env.prod" | cut -d= -f2- || echo "localhost")
SMTP_PORT=$(grep -E '^SMTP_PORT=' "$PROJECT_ROOT/.env.prod" | cut -d= -f2- || echo "1025")
EMAIL_ENV="{\"Variables\":{\"FASTMCP_HOST\":\"0.0.0.0\",\"SMTP_HOST\":\"${SMTP_HOST}\",\"SMTP_PORT\":\"${SMTP_PORT}\"}}"
EMAIL_URL=$(deploy_lambda "mcp-email" "mcp_servers/email" "$EMAIL_ENV")
save_state LAMBDA_URL_MCP_EMAIL "${EMAIL_URL}mcp/"

load_state

# ════════════════════════════════════════════════════════════════════
# Inject Lambda URLs into .env.prod
# ════════════════════════════════════════════════════════════════════
log "Updating .env.prod with Lambda Function URLs..."
sed -i.bak "s|^DB_MCP_URL=.*|DB_MCP_URL=${LAMBDA_URL_MCP_DB}|" "$PROJECT_ROOT/.env.prod"
sed -i.bak "s|^CURRENCY_MCP_URL=.*|CURRENCY_MCP_URL=${LAMBDA_URL_MCP_CURRENCY}|" "$PROJECT_ROOT/.env.prod"
sed -i.bak "s|^EMAIL_MCP_URL=.*|EMAIL_MCP_URL=${LAMBDA_URL_MCP_EMAIL}|" "$PROJECT_ROOT/.env.prod"
sed -i.bak "s|^RDS_ENDPOINT=.*|RDS_ENDPOINT=${RDS_ENDPOINT}|" "$PROJECT_ROOT/.env.prod"
sed -i.bak "s|^POSTGRES_HOST=.*|POSTGRES_HOST=${RDS_ENDPOINT}|" "$PROJECT_ROOT/.env.prod"
rm -f "$PROJECT_ROOT/.env.prod.bak"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Lambda Deployment Complete"
echo "═══════════════════════════════════════════════════"
echo "  mcp-db:       $LAMBDA_URL_MCP_DB"
echo "  mcp-currency: $LAMBDA_URL_MCP_CURRENCY"
echo "  mcp-email:    $LAMBDA_URL_MCP_EMAIL"
echo ""
echo "  .env.prod updated with Lambda URLs."
echo ""
echo "  Next: ./scripts/aws/03-deploy-ec2.sh"
echo "═══════════════════════════════════════════════════"
