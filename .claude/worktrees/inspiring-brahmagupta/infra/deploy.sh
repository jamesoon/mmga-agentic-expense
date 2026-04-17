#!/usr/bin/env bash
# Author: jamesoon
# Deploy the Agentic Expense Claims app to AWS Free Tier.
#
# Creates: Security Groups, RDS PostgreSQL, EC2 instance, Route53 A record.
# EC2 runs Docker Compose with: Chainlit app, Qdrant, MCP-RAG, MCP-Currency, MCP-Email.
# RDS replaces the local Postgres container. MCP-DB Lambda is future (uses EC2 for now).
#
# Usage:
#   chmod +x infra/deploy.sh
#   ./infra/deploy.sh
#
# Prerequisites:
#   - AWS CLI v2 configured with credentials (aws sts get-caller-identity)
#   - EC2 key pair "made-prod" exists (for SSH access)
#   - Route53 hosted zone for mdaie-sutd.fit exists

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Load secrets (API keys — not in git)
SECRETS_FILE="${SCRIPT_DIR}/.secrets"
if [ ! -f "${SECRETS_FILE}" ]; then
    echo "[ERROR] Missing ${SECRETS_FILE}"
    echo "  Create it with:  echo 'OPENROUTER_API_KEY=sk-or-...' > infra/.secrets"
    exit 1
fi
source "${SECRETS_FILE}"

AWS="${AWS_CLI} --region ${AWS_REGION} --output json"

# --- Helpers ---
log()  { echo "[$(date '+%H:%M:%S')] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }

save_state() { echo "$1=$2" >> "${STATE_FILE}"; }
get_state()  { grep "^$1=" "${STATE_FILE}" 2>/dev/null | tail -1 | cut -d= -f2; }

# ---------------------------------------------------------------------------
# 1. Security Groups
# ---------------------------------------------------------------------------
create_security_groups() {
    log "Creating security groups..."

    # EC2 security group: allow SSH (22), HTTP (80), HTTPS (443), Chainlit (8000)
    EC2_SG_ID=$(${AWS} ec2 create-security-group \
        --group-name "${SG_EC2_NAME}" \
        --description "EC2 SG for ${PROJECT_TAG}" \
        --vpc-id "${VPC_ID}" \
        --query 'GroupId' --output text 2>/dev/null) || {
        EC2_SG_ID=$(${AWS} ec2 describe-security-groups \
            --filters "Name=group-name,Values=${SG_EC2_NAME}" \
            --query 'SecurityGroups[0].GroupId' --output text)
        log "  EC2 SG already exists: ${EC2_SG_ID}"
    }
    save_state "EC2_SG_ID" "${EC2_SG_ID}"

    # Add ingress rules (ignore errors if rules already exist)
    for PORT in 22 80 443 8000; do
        ${AWS} ec2 authorize-security-group-ingress \
            --group-id "${EC2_SG_ID}" \
            --protocol tcp --port ${PORT} --cidr 0.0.0.0/0 2>/dev/null || true
    done
    log "  EC2 SG: ${EC2_SG_ID} (ports 22, 80, 443, 8000)"

    # RDS security group: allow Postgres (5432) from EC2 SG only
    RDS_SG_ID=$(${AWS} ec2 create-security-group \
        --group-name "${SG_RDS_NAME}" \
        --description "RDS SG for ${PROJECT_TAG}" \
        --vpc-id "${VPC_ID}" \
        --query 'GroupId' --output text 2>/dev/null) || {
        RDS_SG_ID=$(${AWS} ec2 describe-security-groups \
            --filters "Name=group-name,Values=${SG_RDS_NAME}" \
            --query 'SecurityGroups[0].GroupId' --output text)
        log "  RDS SG already exists: ${RDS_SG_ID}"
    }
    save_state "RDS_SG_ID" "${RDS_SG_ID}"

    ${AWS} ec2 authorize-security-group-ingress \
        --group-id "${RDS_SG_ID}" \
        --protocol tcp --port 5432 \
        --source-group "${EC2_SG_ID}" 2>/dev/null || true
    log "  RDS SG: ${RDS_SG_ID} (port 5432 from EC2 SG)"
}

# ---------------------------------------------------------------------------
# 2. RDS PostgreSQL
# ---------------------------------------------------------------------------
create_rds() {
    log "Creating RDS PostgreSQL (${RDS_INSTANCE_CLASS})..."

    # Check if already exists
    EXISTING=$(${AWS} rds describe-db-instances \
        --db-instance-identifier "${RDS_INSTANCE_ID}" \
        --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null) || EXISTING="none"

    if [ "${EXISTING}" != "none" ]; then
        log "  RDS already exists (status: ${EXISTING})"
    else
        ${AWS} rds create-db-instance \
            --db-instance-identifier "${RDS_INSTANCE_ID}" \
            --db-instance-class "${RDS_INSTANCE_CLASS}" \
            --engine "${RDS_ENGINE}" \
            --engine-version "${RDS_ENGINE_VERSION}" \
            --master-username "${RDS_MASTER_USER}" \
            --master-user-password "${RDS_MASTER_PASSWORD}" \
            --allocated-storage "${RDS_STORAGE_GB}" \
            --db-name "${RDS_DB_NAME}" \
            --vpc-security-group-ids "${RDS_SG_ID}" \
            --no-multi-az \
            --storage-type gp2 \
            --publicly-accessible \
            --backup-retention-period 0 \
            --tags Key=Project,Value="${PROJECT_TAG}" \
            --no-cli-pager > /dev/null
        log "  RDS instance creating..."
    fi
    save_state "RDS_INSTANCE_ID" "${RDS_INSTANCE_ID}"

    # Wait for RDS to be available (can take 5-10 minutes)
    log "  Waiting for RDS to become available (this takes ~5-10 min)..."
    ${AWS} rds wait db-instance-available \
        --db-instance-identifier "${RDS_INSTANCE_ID}"

    RDS_ENDPOINT=$(${AWS} rds describe-db-instances \
        --db-instance-identifier "${RDS_INSTANCE_ID}" \
        --query 'DBInstances[0].Endpoint.Address' --output text)
    save_state "RDS_ENDPOINT" "${RDS_ENDPOINT}"
    log "  RDS ready: ${RDS_ENDPOINT}"
}

# ---------------------------------------------------------------------------
# 3. EC2 Instance
# ---------------------------------------------------------------------------
create_ec2() {
    log "Creating EC2 instance (${EC2_INSTANCE_TYPE})..."

    RDS_ENDPOINT=$(get_state "RDS_ENDPOINT")
    EC2_SG_ID=$(get_state "EC2_SG_ID")

    # Generate user-data script from template (inject secrets + config)
    USER_DATA=$(cat "${SCRIPT_DIR}/setup-ec2.sh" \
        | sed "s|__RDS_ENDPOINT__|${RDS_ENDPOINT}|g" \
        | sed "s|__RDS_DB_NAME__|${RDS_DB_NAME}|g" \
        | sed "s|__RDS_MASTER_USER__|${RDS_MASTER_USER}|g" \
        | sed "s|__RDS_MASTER_PASSWORD__|${RDS_MASTER_PASSWORD}|g" \
        | sed "s|__DOMAIN_NAME__|${DOMAIN_NAME}|g" \
        | sed "s|__OPENROUTER_API_KEY__|${OPENROUTER_API_KEY}|g")

    INSTANCE_ID=$(${AWS} ec2 run-instances \
        --image-id "${EC2_AMI}" \
        --instance-type "${EC2_INSTANCE_TYPE}" \
        --key-name "${EC2_KEY_NAME}" \
        --security-group-ids "${EC2_SG_ID}" \
        --subnet-id "${SUBNET_ID}" \
        --associate-public-ip-address \
        --user-data "${USER_DATA}" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${EC2_NAME}},{Key=Project,Value=${PROJECT_TAG}}]" \
        --query 'Instances[0].InstanceId' --output text)
    save_state "EC2_INSTANCE_ID" "${INSTANCE_ID}"
    log "  Instance launched: ${INSTANCE_ID}"

    # Wait for running
    log "  Waiting for instance to be running..."
    ${AWS} ec2 wait instance-running --instance-ids "${INSTANCE_ID}"

    # Get public IP
    EC2_PUBLIC_IP=$(${AWS} ec2 describe-instances \
        --instance-ids "${INSTANCE_ID}" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
    save_state "EC2_PUBLIC_IP" "${EC2_PUBLIC_IP}"
    log "  EC2 ready: ${EC2_PUBLIC_IP}"
}

# ---------------------------------------------------------------------------
# 4. Route53 DNS
# ---------------------------------------------------------------------------
update_dns() {
    log "Updating Route53: ${DOMAIN_NAME} -> ${EC2_PUBLIC_IP}..."

    EC2_PUBLIC_IP=$(get_state "EC2_PUBLIC_IP")

    CHANGE_BATCH=$(cat <<EOF
{
    "Changes": [{
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": "${DOMAIN_NAME}",
            "Type": "A",
            "TTL": 300,
            "ResourceRecords": [{"Value": "${EC2_PUBLIC_IP}"}]
        }
    }]
}
EOF
)

    ${AWS} route53 change-resource-record-sets \
        --hosted-zone-id "${HOSTED_ZONE_ID}" \
        --change-batch "${CHANGE_BATCH}" \
        --no-cli-pager > /dev/null
    log "  DNS updated: ${DOMAIN_NAME} -> ${EC2_PUBLIC_IP}"
}

# ---------------------------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------------------------
print_summary() {
    EC2_PUBLIC_IP=$(get_state "EC2_PUBLIC_IP")
    EC2_INSTANCE_ID=$(get_state "EC2_INSTANCE_ID")
    RDS_ENDPOINT=$(get_state "RDS_ENDPOINT")

    echo ""
    echo "============================================"
    echo "  DEPLOYMENT COMPLETE"
    echo "============================================"
    echo ""
    echo "  App URL:    http://${DOMAIN_NAME}:8000"
    echo "  EC2 IP:     ${EC2_PUBLIC_IP}"
    echo "  EC2 ID:     ${EC2_INSTANCE_ID}"
    echo "  RDS Host:   ${RDS_ENDPOINT}"
    echo "  RDS DB:     ${RDS_DB_NAME}"
    echo ""
    echo "  SSH:        ssh -i ~/.ssh/made-prod.pem ec2-user@${EC2_PUBLIC_IP}"
    echo ""
    echo "  The EC2 user-data script is installing Docker and"
    echo "  starting services. This takes ~3-5 min after launch."
    echo "  Check progress:  ssh in, then: tail -f /var/log/cloud-init-output.log"
    echo ""
    echo "  State saved to: ${STATE_FILE}"
    echo "  Teardown:       ./infra/teardown.sh"
    echo "============================================"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    log "Starting deployment of ${PROJECT_TAG}..."

    # Clear previous state
    > "${STATE_FILE}"

    create_security_groups
    create_rds
    create_ec2
    update_dns
    print_summary

    log "Done!"
}

main "$@"
