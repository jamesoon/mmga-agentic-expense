#!/usr/bin/env bash
# Author: jamesoon
# Shared configuration for deploy/teardown scripts.
# All tunables in one place — no magic values in other scripts.

# --- AWS General ---
export AWS_REGION="ap-southeast-1"
export AWS_CLI="/usr/local/bin/aws"
export PROJECT_TAG="mmga-expense"

# --- Networking (default VPC) ---
export VPC_ID="vpc-03734be893068776a"
export SUBNET_ID="subnet-0e2b83c0bd5d8eee9"  # ap-southeast-1a, public

# --- EC2 ---
export EC2_AMI="ami-0c0292c4186d3d1ec"       # Amazon Linux 2023 x86_64
export EC2_INSTANCE_TYPE="t3.micro"            # Free tier eligible
export EC2_KEY_NAME="made-prod"                # Existing key pair
export EC2_NAME="${PROJECT_TAG}-server"

# --- RDS ---
export RDS_INSTANCE_ID="${PROJECT_TAG}-postgres"
export RDS_INSTANCE_CLASS="db.t3.micro"        # Free tier eligible
export RDS_ENGINE="postgres"
export RDS_ENGINE_VERSION="16.6"
export RDS_DB_NAME="agentic_claims"
export RDS_MASTER_USER="agentic"
export RDS_MASTER_PASSWORD="agentic_password"  # Change in production!
export RDS_STORAGE_GB=20                       # Free tier: up to 20 GB

# --- Route53 ---
export HOSTED_ZONE_ID="Z089465439W0RXJJ0LOEW"
export DOMAIN_NAME="mmga.mdaie-sutd.fit"

# --- Security Group Names ---
export SG_EC2_NAME="${PROJECT_TAG}-ec2-sg"
export SG_RDS_NAME="${PROJECT_TAG}-rds-sg"

# --- State file (tracks resource IDs for teardown) ---
export STATE_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.deploy-state"
