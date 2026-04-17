#!/usr/bin/env bash
# Author: jamesoon
# Teardown all AWS resources created by deploy.sh.
# Reads resource IDs from .deploy-state file.
#
# Usage:
#   chmod +x infra/teardown.sh
#   ./infra/teardown.sh
#
# This script is DESTRUCTIVE — it terminates EC2, deletes RDS,
# removes security groups, and clears the DNS record.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

AWS="${AWS_CLI} --region ${AWS_REGION} --output json"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
get_state() { grep "^$1=" "${STATE_FILE}" 2>/dev/null | tail -1 | cut -d= -f2; }

# ---------------------------------------------------------------------------
# Safety prompt
# ---------------------------------------------------------------------------
echo ""
echo "  WARNING: This will DELETE all resources for ${PROJECT_TAG}:"
echo "    - EC2 instance: $(get_state EC2_INSTANCE_ID)"
echo "    - RDS instance: ${RDS_INSTANCE_ID}"
echo "    - Security groups: $(get_state EC2_SG_ID), $(get_state RDS_SG_ID)"
echo "    - DNS record: ${DOMAIN_NAME}"
echo ""
read -p "  Type 'yes' to confirm: " CONFIRM
if [ "${CONFIRM}" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# ---------------------------------------------------------------------------
# 1. Remove DNS record
# ---------------------------------------------------------------------------
EC2_PUBLIC_IP=$(get_state "EC2_PUBLIC_IP")
if [ -n "${EC2_PUBLIC_IP}" ]; then
    log "Removing Route53 record: ${DOMAIN_NAME}..."
    CHANGE_BATCH=$(cat <<EOF
{
    "Changes": [{
        "Action": "DELETE",
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
        --no-cli-pager > /dev/null 2>&1 || log "  DNS record already removed or different"
    log "  DNS record removed"
fi

# ---------------------------------------------------------------------------
# 2. Terminate EC2 instance
# ---------------------------------------------------------------------------
EC2_INSTANCE_ID=$(get_state "EC2_INSTANCE_ID")
if [ -n "${EC2_INSTANCE_ID}" ]; then
    log "Terminating EC2 instance: ${EC2_INSTANCE_ID}..."
    ${AWS} ec2 terminate-instances --instance-ids "${EC2_INSTANCE_ID}" --no-cli-pager > /dev/null 2>&1 || true
    log "  Waiting for termination..."
    ${AWS} ec2 wait instance-terminated --instance-ids "${EC2_INSTANCE_ID}" 2>/dev/null || true
    log "  EC2 terminated"
fi

# ---------------------------------------------------------------------------
# 3. Delete RDS instance (skip final snapshot to avoid costs)
# ---------------------------------------------------------------------------
log "Deleting RDS instance: ${RDS_INSTANCE_ID}..."
${AWS} rds delete-db-instance \
    --db-instance-identifier "${RDS_INSTANCE_ID}" \
    --skip-final-snapshot \
    --no-cli-pager > /dev/null 2>&1 || log "  RDS already deleted or not found"

log "  Waiting for RDS deletion (this takes ~5-10 min)..."
${AWS} rds wait db-instance-deleted \
    --db-instance-identifier "${RDS_INSTANCE_ID}" 2>/dev/null || true
log "  RDS deleted"

# ---------------------------------------------------------------------------
# 4. Delete security groups (must wait for EC2/RDS to be gone)
# ---------------------------------------------------------------------------
RDS_SG_ID=$(get_state "RDS_SG_ID")
EC2_SG_ID=$(get_state "EC2_SG_ID")

if [ -n "${RDS_SG_ID}" ]; then
    log "Deleting RDS security group: ${RDS_SG_ID}..."
    ${AWS} ec2 delete-security-group --group-id "${RDS_SG_ID}" 2>/dev/null || log "  Could not delete RDS SG (may have dependencies)"
fi

if [ -n "${EC2_SG_ID}" ]; then
    log "Deleting EC2 security group: ${EC2_SG_ID}..."
    ${AWS} ec2 delete-security-group --group-id "${EC2_SG_ID}" 2>/dev/null || log "  Could not delete EC2 SG (may have dependencies)"
fi

# ---------------------------------------------------------------------------
# 5. Clean up state file
# ---------------------------------------------------------------------------
rm -f "${STATE_FILE}"
log "State file removed"

echo ""
echo "============================================"
echo "  TEARDOWN COMPLETE"
echo "============================================"
echo "  All ${PROJECT_TAG} resources have been deleted."
echo "  No recurring AWS charges should remain."
echo "============================================"
