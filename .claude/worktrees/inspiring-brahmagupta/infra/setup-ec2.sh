#!/usr/bin/env bash
# Author: jamesoon
# EC2 user-data bootstrap script.
# Runs as root on first boot via cloud-init.
# Installs Docker, clones repo, configures .env, starts services.
#
# Placeholders replaced by deploy.sh at launch time:
#   __RDS_ENDPOINT__       -> RDS hostname
#   __RDS_DB_NAME__        -> Database name
#   __RDS_MASTER_USER__    -> DB username
#   __RDS_MASTER_PASSWORD__-> DB password
#   __DOMAIN_NAME__        -> Public domain

set -euo pipefail
exec > /var/log/user-data.log 2>&1

echo "=== EC2 bootstrap start: $(date) ==="

# --- 1. Install Docker + Docker Compose ---
dnf update -y
dnf install -y docker git
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Verify
docker --version
docker compose version

# --- 2. Clone repository ---
APP_DIR="/opt/mmga-expense"
if [ -d "${APP_DIR}" ]; then
    cd "${APP_DIR}" && git pull
else
    git clone https://github.com/jamesoon/multimodal-agentic-expense-claim-kit.git "${APP_DIR}"
fi
cd "${APP_DIR}"

# --- 3. Create .env.local for production ---
cat > .env.local <<'ENVEOF'
# PostgreSQL (RDS)
POSTGRES_HOST=__RDS_ENDPOINT__
POSTGRES_PORT=5432
POSTGRES_DB=__RDS_DB_NAME__
POSTGRES_USER=__RDS_MASTER_USER__
POSTGRES_PASSWORD=__RDS_MASTER_PASSWORD__

# Chainlit
CHAINLIT_HOST=0.0.0.0
CHAINLIT_PORT=8000
APP_ENV=prod

# OpenRouter (set these manually after deploy or via Secrets Manager)
OPENROUTER_API_KEY=__OPENROUTER_API_KEY__
OPENROUTER_MODEL_LLM=qwen/qwen-2.5-72b-instruct
OPENROUTER_MODEL_VLM=qwen/qwen-2.5-vl-72b-instruct
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MAX_RETRIES=3
OPENROUTER_RETRY_DELAY=2.0

# Qdrant (local container)
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# SMTP (stub for now)
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=

# Image quality
IMAGE_BLUR_THRESHOLD=150.0
IMAGE_MIN_WIDTH=800
IMAGE_MIN_HEIGHT=600
VLM_CONFIDENCE_THRESHOLD=0.7
ENVEOF

# --- 4. Create docker-compose.prod.yml (no Postgres container — uses RDS) ---
cat > docker-compose.prod.yml <<'COMPEOF'
version: "3.8"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file: .env.local
    environment:
      POSTGRES_HOST: __RDS_ENDPOINT__
      QDRANT_HOST: qdrant
    depends_on:
      qdrant:
        condition: service_healthy
      mcp-rag:
        condition: service_healthy
      mcp-db:
        condition: service_healthy
      mcp-currency:
        condition: service_healthy
      mcp-email:
        condition: service_healthy
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  mcp-rag:
    build:
      context: ./mcp_servers/rag
    ports:
      - "8001:8000"
    environment:
      QDRANT_URL: http://qdrant:6333
      COLLECTION_NAME: expense_policies
      EMBEDDING_MODEL: sentence-transformers/all-MiniLM-L6-v2
      FASTMCP_HOST: 0.0.0.0
    platform: linux/amd64
    depends_on:
      qdrant:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8000/mcp"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  mcp-db:
    build:
      context: ./mcp_servers/db
    ports:
      - "8002:8000"
    environment:
      DATABASE_URL: "postgresql://__RDS_MASTER_USER__:__RDS_MASTER_PASSWORD__@__RDS_ENDPOINT__:5432/__RDS_DB_NAME__"
      FASTMCP_HOST: 0.0.0.0
    healthcheck:
      test: ["CMD", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8000/mcp"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  mcp-currency:
    build:
      context: ./mcp_servers/currency
    ports:
      - "8003:8000"
    environment:
      FASTMCP_HOST: 0.0.0.0
    healthcheck:
      test: ["CMD", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8000/mcp"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  mcp-email:
    build:
      context: ./mcp_servers/email
    ports:
      - "8004:8000"
    environment:
      SMTP_HOST: mailhog
      SMTP_PORT: 1025
      SMTP_USER: ""
      SMTP_PASSWORD: ""
      FASTMCP_HOST: 0.0.0.0
    healthcheck:
      test: ["CMD", "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8000/mcp"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  qdrant_data:
COMPEOF

# Replace placeholders in docker-compose.prod.yml
sed -i "s|__RDS_ENDPOINT__|__RDS_ENDPOINT__|g" docker-compose.prod.yml
sed -i "s|__RDS_DB_NAME__|__RDS_DB_NAME__|g" docker-compose.prod.yml
sed -i "s|__RDS_MASTER_USER__|__RDS_MASTER_USER__|g" docker-compose.prod.yml
sed -i "s|__RDS_MASTER_PASSWORD__|__RDS_MASTER_PASSWORD__|g" docker-compose.prod.yml

# --- 5. Start services ---
echo "=== Starting Docker Compose services ==="
docker compose -f docker-compose.prod.yml up -d --build

# --- 6. Wait for services and run migrations ---
echo "=== Waiting for services to be healthy ==="
sleep 30

# Run Alembic migrations against RDS
docker compose -f docker-compose.prod.yml exec -T app \
    poetry run alembic upgrade head || echo "Migration failed — may need manual run"

# Ingest policies into Qdrant
docker compose -f docker-compose.prod.yml exec -T app \
    python scripts/ingest_policies.py || echo "Policy ingestion failed — may need manual run"

echo "=== EC2 bootstrap complete: $(date) ==="
echo "App should be available at http://__DOMAIN_NAME__:8000"
