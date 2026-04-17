#!/usr/bin/env bash
# 01-setup-infra.sh — One-time AWS infrastructure setup.
# Creates: VPC, subnets, IGW, NAT, security groups, RDS, EC2, ECR repos, Lambda role.
# Idempotent: skips resources that already exist (checked via state file + AWS queries).
#
# Prerequisites: aws cli configured, .env.prod with POSTGRES_PASSWORD set.
#
# Usage: ./scripts/aws/01-setup-infra.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/config.sh"
load_state

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Read RDS password from .env.prod
if [[ ! -f "$PROJECT_ROOT/.env.prod" ]]; then
  err ".env.prod not found. Copy .env.prod.example to .env.prod and set POSTGRES_PASSWORD."
  exit 1
fi
RDS_PASSWORD=$(grep -E '^POSTGRES_PASSWORD=' "$PROJECT_ROOT/.env.prod" | cut -d= -f2-)
if [[ -z "$RDS_PASSWORD" || "$RDS_PASSWORD" == "CHANGE_ME_STRONG_PASSWORD" ]]; then
  err "Set a real POSTGRES_PASSWORD in .env.prod before running this script."
  exit 1
fi

# ════════════════════════════════════════════════════════════════════
# 1. VPC
# ════════════════════════════════════════════════════════════════════
if [[ -z "${VPC_ID:-}" ]]; then
  log "Creating VPC ($VPC_CIDR)..."
  VPC_ID=$(aws ec2 create-vpc \
    --cidr-block "$VPC_CIDR" \
    --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=${PROJECT}-vpc},{$TAGS}]" \
    --query 'Vpc.VpcId' --output text --region "$AWS_REGION")
  aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames '{"Value":true}' --region "$AWS_REGION"
  aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support '{"Value":true}' --region "$AWS_REGION"
  save_state VPC_ID "$VPC_ID"
  ok "VPC: $VPC_ID"
else
  ok "VPC exists: $VPC_ID"
fi

# ════════════════════════════════════════════════════════════════════
# 2. Subnets (2 public, 2 private across AZs)
# ════════════════════════════════════════════════════════════════════
AZS=($(aws ec2 describe-availability-zones --region "$AWS_REGION" --query 'AvailabilityZones[0:2].ZoneName' --output text))

create_subnet() {
  local name="$1" cidr="$2" az="$3" public="$4" state_key="$5"
  if [[ -z "${!state_key:-}" ]]; then
    local sid
    sid=$(aws ec2 create-subnet \
      --vpc-id "$VPC_ID" --cidr-block "$cidr" --availability-zone "$az" \
      --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT}-${name}},{$TAGS}]" \
      --query 'Subnet.SubnetId' --output text --region "$AWS_REGION")
    if [[ "$public" == "true" ]]; then
      aws ec2 modify-subnet-attribute --subnet-id "$sid" --map-public-ip-on-launch --region "$AWS_REGION"
    fi
    save_state "$state_key" "$sid"
    ok "Subnet $name: $sid ($az)"
  else
    ok "Subnet $name exists: ${!state_key}"
  fi
}

create_subnet "pub-1"  "$SUBNET_PUBLIC_1_CIDR"  "${AZS[0]}" true  SUBNET_PUB_1
create_subnet "pub-2"  "$SUBNET_PUBLIC_2_CIDR"  "${AZS[1]}" true  SUBNET_PUB_2
create_subnet "priv-1" "$SUBNET_PRIVATE_1_CIDR" "${AZS[0]}" false SUBNET_PRIV_1
create_subnet "priv-2" "$SUBNET_PRIVATE_2_CIDR" "${AZS[1]}" false SUBNET_PRIV_2

load_state  # reload after saves

# ════════════════════════════════════════════════════════════════════
# 3. Internet Gateway + NAT Gateway
# ════════════════════════════════════════════════════════════════════
if [[ -z "${IGW_ID:-}" ]]; then
  log "Creating Internet Gateway..."
  IGW_ID=$(aws ec2 create-internet-gateway \
    --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=${PROJECT}-igw},{$TAGS}]" \
    --query 'InternetGateway.InternetGatewayId' --output text --region "$AWS_REGION")
  aws ec2 attach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID" --region "$AWS_REGION"
  save_state IGW_ID "$IGW_ID"
  ok "IGW: $IGW_ID"
else
  ok "IGW exists: $IGW_ID"
fi

# Public route table
if [[ -z "${RT_PUBLIC:-}" ]]; then
  RT_PUBLIC=$(aws ec2 create-route-table --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT}-public-rt},{$TAGS}]" \
    --query 'RouteTable.RouteTableId' --output text --region "$AWS_REGION")
  aws ec2 create-route --route-table-id "$RT_PUBLIC" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID" --region "$AWS_REGION" > /dev/null
  aws ec2 associate-route-table --route-table-id "$RT_PUBLIC" --subnet-id "$SUBNET_PUB_1" --region "$AWS_REGION" > /dev/null
  aws ec2 associate-route-table --route-table-id "$RT_PUBLIC" --subnet-id "$SUBNET_PUB_2" --region "$AWS_REGION" > /dev/null
  save_state RT_PUBLIC "$RT_PUBLIC"
  ok "Public route table: $RT_PUBLIC"
fi

# EIP + NAT Gateway (for Lambda in private subnets to reach internet)
if [[ -z "${NAT_ID:-}" ]]; then
  log "Creating NAT Gateway (takes ~2 min)..."
  EIP_ALLOC=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text --region "$AWS_REGION")
  save_state EIP_ALLOC "$EIP_ALLOC"
  NAT_ID=$(aws ec2 create-nat-gateway --subnet-id "$SUBNET_PUB_1" --allocation-id "$EIP_ALLOC" \
    --tag-specifications "ResourceType=natgateway,Tags=[{Key=Name,Value=${PROJECT}-nat},{$TAGS}]" \
    --query 'NatGateway.NatGatewayId' --output text --region "$AWS_REGION")
  save_state NAT_ID "$NAT_ID"
  log "Waiting for NAT Gateway to become available..."
  aws ec2 wait nat-gateway-available --nat-gateway-ids "$NAT_ID" --region "$AWS_REGION"
  ok "NAT Gateway: $NAT_ID"
else
  ok "NAT Gateway exists: $NAT_ID"
fi

# Private route table (via NAT)
if [[ -z "${RT_PRIVATE:-}" ]]; then
  RT_PRIVATE=$(aws ec2 create-route-table --vpc-id "$VPC_ID" \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT}-private-rt},{$TAGS}]" \
    --query 'RouteTable.RouteTableId' --output text --region "$AWS_REGION")
  aws ec2 create-route --route-table-id "$RT_PRIVATE" --destination-cidr-block 0.0.0.0/0 --nat-gateway-id "$NAT_ID" --region "$AWS_REGION" > /dev/null
  aws ec2 associate-route-table --route-table-id "$RT_PRIVATE" --subnet-id "$SUBNET_PRIV_1" --region "$AWS_REGION" > /dev/null
  aws ec2 associate-route-table --route-table-id "$RT_PRIVATE" --subnet-id "$SUBNET_PRIV_2" --region "$AWS_REGION" > /dev/null
  save_state RT_PRIVATE "$RT_PRIVATE"
  ok "Private route table: $RT_PRIVATE"
fi

# ════════════════════════════════════════════════════════════════════
# 4. Security Groups
# ════════════════════════════════════════════════════════════════════
if [[ -z "${SG_EC2:-}" ]]; then
  log "Creating security groups..."
  SG_EC2=$(aws ec2 create-security-group --group-name "${PROJECT}-ec2" \
    --description "EC2: HTTP 80, SSH 22" --vpc-id "$VPC_ID" \
    --query 'GroupId' --output text --region "$AWS_REGION")
  aws ec2 authorize-security-group-ingress --group-id "$SG_EC2" --protocol tcp --port 80   --cidr 0.0.0.0/0 --region "$AWS_REGION" > /dev/null
  aws ec2 authorize-security-group-ingress --group-id "$SG_EC2" --protocol tcp --port 22   --cidr 0.0.0.0/0 --region "$AWS_REGION" > /dev/null
  aws ec2 create-tags --resources "$SG_EC2" --tags "Key=Name,Value=${PROJECT}-ec2-sg" --region "$AWS_REGION"
  save_state SG_EC2 "$SG_EC2"
  ok "SG EC2: $SG_EC2"
fi

if [[ -z "${SG_RDS:-}" ]]; then
  SG_RDS=$(aws ec2 create-security-group --group-name "${PROJECT}-rds" \
    --description "RDS: Postgres 5432 from EC2+Lambda" --vpc-id "$VPC_ID" \
    --query 'GroupId' --output text --region "$AWS_REGION")
  aws ec2 authorize-security-group-ingress --group-id "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_EC2" --region "$AWS_REGION" > /dev/null
  aws ec2 create-tags --resources "$SG_RDS" --tags "Key=Name,Value=${PROJECT}-rds-sg" --region "$AWS_REGION"
  save_state SG_RDS "$SG_RDS"
  ok "SG RDS: $SG_RDS"
fi

if [[ -z "${SG_LAMBDA:-}" ]]; then
  SG_LAMBDA=$(aws ec2 create-security-group --group-name "${PROJECT}-lambda" \
    --description "Lambda: outbound only" --vpc-id "$VPC_ID" \
    --query 'GroupId' --output text --region "$AWS_REGION")
  aws ec2 create-tags --resources "$SG_LAMBDA" --tags "Key=Name,Value=${PROJECT}-lambda-sg" --region "$AWS_REGION"
  # Allow Lambda → RDS
  aws ec2 authorize-security-group-ingress --group-id "$SG_RDS" --protocol tcp --port 5432 --source-group "$SG_LAMBDA" --region "$AWS_REGION" > /dev/null 2>&1 || true
  save_state SG_LAMBDA "$SG_LAMBDA"
  ok "SG Lambda: $SG_LAMBDA"
fi

load_state

# ════════════════════════════════════════════════════════════════════
# 5. RDS PostgreSQL (free tier)
# ════════════════════════════════════════════════════════════════════
if [[ -z "${RDS_ENDPOINT:-}" ]]; then
  log "Creating RDS subnet group..."
  aws rds create-db-subnet-group \
    --db-subnet-group-name "${PROJECT}-db-subnets" \
    --db-subnet-group-description "Private subnets for RDS" \
    --subnet-ids "$SUBNET_PRIV_1" "$SUBNET_PRIV_2" \
    --region "$AWS_REGION" > /dev/null 2>&1 || true

  log "Creating RDS instance (takes 5-10 min)..."
  aws rds create-db-instance \
    --db-instance-identifier "$RDS_IDENTIFIER" \
    --db-instance-class "$RDS_INSTANCE_CLASS" \
    --engine postgres --engine-version "16.3" \
    --allocated-storage "$RDS_STORAGE_GB" \
    --db-name "$RDS_DB_NAME" \
    --master-username "$RDS_USERNAME" \
    --master-user-password "$RDS_PASSWORD" \
    --vpc-security-group-ids "$SG_RDS" \
    --db-subnet-group-name "${PROJECT}-db-subnets" \
    --no-publicly-accessible \
    --storage-type gp2 \
    --backup-retention-period 1 \
    --no-multi-az \
    --tags "Key=Project,Value=${PROJECT}" "Key=Environment,Value=prod" \
    --region "$AWS_REGION" > /dev/null

  log "Waiting for RDS to become available..."
  aws rds wait db-instance-available --db-instance-identifier "$RDS_IDENTIFIER" --region "$AWS_REGION"

  RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier "$RDS_IDENTIFIER" \
    --query 'DBInstances[0].Endpoint.Address' --output text --region "$AWS_REGION")
  save_state RDS_ENDPOINT "$RDS_ENDPOINT"
  ok "RDS endpoint: $RDS_ENDPOINT"
else
  ok "RDS exists: $RDS_ENDPOINT"
fi

# ════════════════════════════════════════════════════════════════════
# 6. ECR Repositories (for Lambda container images)
# ════════════════════════════════════════════════════════════════════
log "Ensuring ECR repositories..."
for repo in "${ECR_REPOS[@]}"; do
  aws ecr describe-repositories --repository-names "$repo" --region "$AWS_REGION" > /dev/null 2>&1 || \
    aws ecr create-repository --repository-name "$repo" --region "$AWS_REGION" > /dev/null
  ok "ECR: $repo"
done

# ════════════════════════════════════════════════════════════════════
# 7. Lambda Execution Role
# ════════════════════════════════════════════════════════════════════
if [[ -z "${LAMBDA_ROLE_ARN:-}" ]]; then
  log "Creating Lambda execution role..."
  TRUST_POLICY='{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
  LAMBDA_ROLE_ARN=$(aws iam create-role \
    --role-name "$LAMBDA_ROLE_NAME" \
    --assume-role-policy-document "$TRUST_POLICY" \
    --query 'Role.Arn' --output text 2>/dev/null || \
    aws iam get-role --role-name "$LAMBDA_ROLE_NAME" --query 'Role.Arn' --output text)

  # Attach basic execution + VPC access policies
  aws iam attach-role-policy --role-name "$LAMBDA_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true
  aws iam attach-role-policy --role-name "$LAMBDA_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole 2>/dev/null || true

  save_state LAMBDA_ROLE_ARN "$LAMBDA_ROLE_ARN"
  # Wait for IAM propagation
  sleep 10
  ok "Lambda role: $LAMBDA_ROLE_ARN"
else
  ok "Lambda role exists: $LAMBDA_ROLE_ARN"
fi

# ════════════════════════════════════════════════════════════════════
# 8. EC2 Key Pair
# ════════════════════════════════════════════════════════════════════
if [[ ! -f "$EC2_KEY_FILE" ]]; then
  log "Creating EC2 key pair..."
  aws ec2 create-key-pair --key-name "$EC2_KEY_NAME" \
    --query 'KeyMaterial' --output text --region "$AWS_REGION" > "$EC2_KEY_FILE"
  chmod 400 "$EC2_KEY_FILE"
  ok "Key pair saved: $EC2_KEY_FILE"
else
  ok "Key pair exists: $EC2_KEY_FILE"
fi

# ════════════════════════════════════════════════════════════════════
# 9. EC2 Instance (Amazon Linux 2023, free tier)
# ════════════════════════════════════════════════════════════════════
if [[ -z "${EC2_INSTANCE_ID:-}" ]]; then
  log "Finding latest Amazon Linux 2023 AMI..."
  AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=al2023-ami-2023*-x86_64" "Name=state,Values=available" \
    --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' --output text --region "$AWS_REGION")
  log "AMI: $AMI_ID"

  # User data script to install Docker + Docker Compose on first boot
  USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
set -ex
# Install Docker
dnf update -y
dnf install -y docker git
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Docker Compose v2 plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Signal ready
touch /tmp/docker-ready
USERDATA
)

  log "Launching EC2 instance ($EC2_INSTANCE_TYPE)..."
  EC2_INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type "$EC2_INSTANCE_TYPE" \
    --key-name "$EC2_KEY_NAME" \
    --security-group-ids "$SG_EC2" \
    --subnet-id "$SUBNET_PUB_1" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${PROJECT}-app},{$TAGS}]" \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]' \
    --query 'Instances[0].InstanceId' --output text --region "$AWS_REGION")
  save_state EC2_INSTANCE_ID "$EC2_INSTANCE_ID"

  log "Waiting for EC2 instance to be running..."
  aws ec2 wait instance-running --instance-ids "$EC2_INSTANCE_ID" --region "$AWS_REGION"

  EC2_PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$EC2_INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text --region "$AWS_REGION")
  save_state EC2_PUBLIC_IP "$EC2_PUBLIC_IP"
  ok "EC2 instance: $EC2_INSTANCE_ID ($EC2_PUBLIC_IP)"
else
  EC2_PUBLIC_IP=$(get_state EC2_PUBLIC_IP)
  ok "EC2 exists: $EC2_INSTANCE_ID ($EC2_PUBLIC_IP)"
fi

# ════════════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Infrastructure Setup Complete"
echo "═══════════════════════════════════════════════════"
echo "  VPC:           $VPC_ID"
echo "  RDS Endpoint:  ${RDS_ENDPOINT:-pending}"
echo "  EC2 Instance:  ${EC2_INSTANCE_ID:-pending}"
echo "  EC2 Public IP: ${EC2_PUBLIC_IP:-pending}"
echo "  Lambda Role:   ${LAMBDA_ROLE_ARN:-pending}"
echo ""
echo "  State file: $STATE_FILE"
echo ""
echo "  Next: ./scripts/aws/02-deploy-lambdas.sh"
echo "═══════════════════════════════════════════════════"
