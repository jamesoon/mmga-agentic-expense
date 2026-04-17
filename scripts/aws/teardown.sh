#!/usr/bin/env bash
# teardown.sh — Destroy all AWS resources created by the deploy scripts.
#
# Reads resource IDs from .deploy-state and deletes them in reverse order.
# Prompts for confirmation before proceeding.
#
# Usage: ./scripts/aws/teardown.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
load_state

echo "═══════════════════════════════════════════════════"
echo "  TEARDOWN — This will destroy ALL AWS resources"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  VPC:       ${VPC_ID:-none}"
echo "  RDS:       ${RDS_IDENTIFIER:-none}"
echo "  EC2:       ${EC2_INSTANCE_ID:-none}"
echo "  Lambdas:   ${PROJECT}-mcp-db, ${PROJECT}-mcp-currency, ${PROJECT}-mcp-email"
echo ""
read -p "Type 'destroy' to confirm: " confirm
if [[ "$confirm" != "destroy" ]]; then
  echo "Aborted."
  exit 0
fi

# ════════════════════════════════════════════════════════════════════
# 1. Lambda functions + URLs
# ════════════════════════════════════════════════════════════════════
for fn in "${PROJECT}-mcp-db" "${PROJECT}-mcp-currency" "${PROJECT}-mcp-email"; do
  log "Deleting Lambda $fn..."
  aws lambda delete-function-url-config --function-name "$fn" --region "$AWS_REGION" 2>/dev/null || true
  aws lambda delete-function --function-name "$fn" --region "$AWS_REGION" 2>/dev/null || true
done

# ════════════════════════════════════════════════════════════════════
# 2. ECR repositories
# ════════════════════════════════════════════════════════════════════
for repo in "${ECR_REPOS[@]}"; do
  log "Deleting ECR repo $repo..."
  aws ecr delete-repository --repository-name "$repo" --force --region "$AWS_REGION" 2>/dev/null || true
done

# ════════════════════════════════════════════════════════════════════
# 3. Lambda role
# ════════════════════════════════════════════════════════════════════
if [[ -n "${LAMBDA_ROLE_NAME:-}" ]]; then
  log "Deleting Lambda IAM role..."
  aws iam detach-role-policy --role-name "$LAMBDA_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true
  aws iam detach-role-policy --role-name "$LAMBDA_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole 2>/dev/null || true
  aws iam delete-role --role-name "$LAMBDA_ROLE_NAME" 2>/dev/null || true
fi

# ════════════════════════════════════════════════════════════════════
# 4. EC2 instance
# ════════════════════════════════════════════════════════════════════
if [[ -n "${EC2_INSTANCE_ID:-}" ]]; then
  log "Terminating EC2 instance $EC2_INSTANCE_ID..."
  aws ec2 terminate-instances --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION" > /dev/null
  aws ec2 wait instance-terminated --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION"
  ok "EC2 terminated"
fi

# ════════════════════════════════════════════════════════════════════
# 5. RDS instance
# ════════════════════════════════════════════════════════════════════
if [[ -n "${RDS_IDENTIFIER:-}" ]]; then
  log "Deleting RDS instance $RDS_IDENTIFIER (skip final snapshot)..."
  aws rds delete-db-instance \
    --db-instance-identifier "$RDS_IDENTIFIER" \
    --skip-final-snapshot \
    --region "$AWS_REGION" > /dev/null 2>&1 || true
  log "Waiting for RDS deletion (5-10 min)..."
  aws rds wait db-instance-deleted --db-instance-identifier "$RDS_IDENTIFIER" --region "$AWS_REGION" 2>/dev/null || true
  ok "RDS deleted"
fi

# ════════════════════════════════════════════════════════════════════
# 6. RDS subnet group
# ════════════════════════════════════════════════════════════════════
aws rds delete-db-subnet-group --db-subnet-group-name "${PROJECT}-db-subnets" --region "$AWS_REGION" 2>/dev/null || true

# ════════════════════════════════════════════════════════════════════
# 7. Key pair
# ════════════════════════════════════════════════════════════════════
aws ec2 delete-key-pair --key-name "$EC2_KEY_NAME" --region "$AWS_REGION" 2>/dev/null || true
rm -f "$EC2_KEY_FILE"

# ════════════════════════════════════════════════════════════════════
# 8. NAT Gateway + EIP
# ════════════════════════════════════════════════════════════════════
if [[ -n "${NAT_ID:-}" ]]; then
  log "Deleting NAT Gateway..."
  aws ec2 delete-nat-gateway --nat-gateway-id "$NAT_ID" --region "$AWS_REGION" > /dev/null 2>&1 || true
  log "Waiting for NAT Gateway deletion..."
  sleep 30  # NAT takes time to delete
  for i in $(seq 1 12); do
    state=$(aws ec2 describe-nat-gateways --nat-gateway-ids "$NAT_ID" \
      --query 'NatGateways[0].State' --output text --region "$AWS_REGION" 2>/dev/null || echo "deleted")
    [[ "$state" == "deleted" ]] && break
    sleep 10
  done
fi

if [[ -n "${EIP_ALLOC:-}" ]]; then
  aws ec2 release-address --allocation-id "$EIP_ALLOC" --region "$AWS_REGION" 2>/dev/null || true
fi

# ════════════════════════════════════════════════════════════════════
# 9. Security groups
# ════════════════════════════════════════════════════════════════════
for sg in "${SG_LAMBDA:-}" "${SG_RDS:-}" "${SG_EC2:-}"; do
  if [[ -n "$sg" ]]; then
    log "Deleting security group $sg..."
    aws ec2 delete-security-group --group-id "$sg" --region "$AWS_REGION" 2>/dev/null || true
  fi
done

# ════════════════════════════════════════════════════════════════════
# 10. Subnets
# ════════════════════════════════════════════════════════════════════
for subnet in "${SUBNET_PUB_1:-}" "${SUBNET_PUB_2:-}" "${SUBNET_PRIV_1:-}" "${SUBNET_PRIV_2:-}"; do
  if [[ -n "$subnet" ]]; then
    aws ec2 delete-subnet --subnet-id "$subnet" --region "$AWS_REGION" 2>/dev/null || true
  fi
done

# ════════════════════════════════════════════════════════════════════
# 11. Route tables (non-default)
# ════════════════════════════════════════════════════════════════════
for rt in "${RT_PUBLIC:-}" "${RT_PRIVATE:-}"; do
  if [[ -n "$rt" ]]; then
    # Disassociate all associations first
    for assoc in $(aws ec2 describe-route-tables --route-table-ids "$rt" \
      --query 'RouteTables[0].Associations[?!Main].RouteTableAssociationId' --output text --region "$AWS_REGION" 2>/dev/null); do
      aws ec2 disassociate-route-table --association-id "$assoc" --region "$AWS_REGION" 2>/dev/null || true
    done
    aws ec2 delete-route-table --route-table-id "$rt" --region "$AWS_REGION" 2>/dev/null || true
  fi
done

# ════════════════════════════════════════════════════════════════════
# 12. Internet Gateway
# ════════════════════════════════════════════════════════════════════
if [[ -n "${IGW_ID:-}" && -n "${VPC_ID:-}" ]]; then
  aws ec2 detach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID" --region "$AWS_REGION" 2>/dev/null || true
  aws ec2 delete-internet-gateway --internet-gateway-id "$IGW_ID" --region "$AWS_REGION" 2>/dev/null || true
fi

# ════════════════════════════════════════════════════════════════════
# 13. VPC
# ════════════════════════════════════════════════════════════════════
if [[ -n "${VPC_ID:-}" ]]; then
  log "Deleting VPC $VPC_ID..."
  aws ec2 delete-vpc --vpc-id "$VPC_ID" --region "$AWS_REGION" 2>/dev/null || true
fi

# ════════════════════════════════════════════════════════════════════
# 14. Clean state file
# ════════════════════════════════════════════════════════════════════
rm -f "$STATE_FILE"

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Teardown Complete — all resources destroyed"
echo "═══════════════════════════════════════════════════"
