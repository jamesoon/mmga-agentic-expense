# Decommission & Rebuild Reference

Written: 2026-05-17. Use this document to rebuild the full production stack from scratch after teardown.

---

## 1. Live AWS Resources (as of 2026-05-17)

> Always re-query by tag before acting — instance IPs change on stop/start.

| Resource | ID / Value | Notes |
|---|---|---|
| **AWS Account** | `544794037284` | IAM user: `iamadmin` |
| **Region** | `ap-southeast-1` | Singapore |
| **EC2 Instance** | `i-0790b69077671d1dc` | t2.micro, Amazon Linux 2023. Re-query: `aws ec2 describe-instances --filters "Name=tag:Name,Values=mmae*" --region ap-southeast-1` |
| **EC2 Public IP** | `13.213.13.39` | Dynamic — may change on restart |
| **RDS Instance** | `mmga-expense-postgres.cfg6qy4oqaqg.ap-southeast-1.rds.amazonaws.com` | db.t3.micro, PostgreSQL 16.6, DB: `agentic_claims`, user: `agentic` |
| **Route53 Hosted Zone** | `Z089465439W0RXJJ0LOEW` | Domain: `mdaie-sutd.fit` |
| **Route53 A Record** | `mmga.mdaie-sutd.fit` → `13.212.241.181` | ⚠️ This IP is stale — points to old instance. Must be updated after rebuild. |
| **S3 Bucket** | `s3://mmga-expense-deploy/` | Docker image tars + bootstrap script |
| **ECR Repos** | `mmga-app`, `mmga-mcp-rag`, `mmga-mcp-db`, `mmga-mcp-currency`, `mmga-mcp-email` | Created but not actively used — went with S3 tar approach |
| **IAM Role** | `mmga-ec2-s3-role` + instance profile `mmga-ec2-s3-profile` | Attached to EC2 for S3 read access |
| **IAM User (SES)** | `mmae-ses-smtp` | Has `AmazonSESFullAccess`. SMTP credentials derived from its secret key. |
| **Security Group (EC2)** | `sg-043f35d5858e02163` (`mmga-expense-ec2-sg`) | Inbound: TCP 80, TCP 443, TCP 22 |
| **Security Group (RDS)** | `sg-03faccf69d8519b46` (`mmga-expense-rds-sg`) | Inbound: TCP 5432 from EC2 SG only |
| **Key Pair** | `made-prod` | PEM is NOT on James's Mac. Use EC2 Instance Connect (see SSH section). |
| **AWS SES** | Region: `ap-southeast-1`, sender: `claims@mdaie-sutd.fit` | Domain `mdaie-sutd.fit` verified. SES is in sandbox — can only send to verified addresses unless production access has been granted. |

### SES Verified Email Addresses
- `jamesooneh@gmail.com` — verified
- `sagarpratapsingh15@gmail.com` — pending verification (as of 2026-04-24)

---

## 2. EC2 File Locations

```
/opt/mmga-expense/          ← source code root (NOT /home/ec2-user/mmae)
├── .env.prod               ← live environment file (may differ from local copy — see §4)
├── docker-compose.prod.yml
├── uploads/                ← writable receipt image store (bind-mounted into app container at /data/uploads)
└── scripts/
    └── ingest_policies.py

/tmp/build.log              ← Docker build log from last deploy
/tmp/bootstrap.log          ← EC2 bootstrap log
```

---

## 3. SSH Access

The `made-prod.pem` key is not on this Mac. Always use EC2 Instance Connect:

```bash
# Step 1 — push ephemeral key (60-second window)
aws ec2-instance-connect send-ssh-public-key \
  --instance-id i-0790b69077671d1dc \
  --instance-os-user ec2-user \
  --ssh-public-key file://~/.ssh/id_ed25519.pub \
  --availability-zone ap-southeast-1a

# Step 2 — SSH immediately (within 60 seconds)
ssh -i ~/.ssh/id_ed25519 ec2-user@13.213.13.39
```

For scripted/automated operations prefer AWS SSM:
```bash
aws ssm send-command \
  --instance-ids i-0790b69077671d1dc \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["<your command>"]' \
  --region ap-southeast-1
```

---

## 4. Live Environment Variables

The local `.env.prod` file is **not the source of truth** for the running instance. The EC2 copy was patched in place after the email stub incident (2026-04-24). The table below reflects what should be on EC2.

| Variable | Value / Notes |
|---|---|
| `POSTGRES_HOST` | RDS endpoint (see §1) |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `agentic_claims` |
| `POSTGRES_USER` | `agentic` |
| `POSTGRES_PASSWORD` | **[REDACTED — see local `.env.prod`]** — rotate after decommission |
| `OPENROUTER_API_KEY` | **[REDACTED — see local `.env.prod`]** — rotate after decommission |
| `OPENROUTER_MODEL_LLM` | `qwen/qwen3-235b-a22b-2507` |
| `OPENROUTER_MODEL_VLM` | `google/gemini-2.0-flash-001` |
| `OPENROUTER_FALLBACK_MODEL_LLM` | `google/gemini-2.0-flash-lite-001` |
| `OPENROUTER_FALLBACK_MODEL_VLM` | `google/gemini-2.0-flash-lite-001` |
| `SESSION_SECRET_KEY` | **[REDACTED — see local `.env.prod`]** — rotate after decommission |
| `SMTP_HOST` | `email-smtp.ap-southeast-1.amazonaws.com` ← **EC2 value** (local .env.prod still shows `localhost` — was patched on EC2 directly) |
| `SMTP_PORT` | `587` ← **EC2 value** (local shows `1025`) |
| `SMTP_USER` | SES SMTP username for `mmae-ses-smtp` IAM user — retrieve with `aws iam list-access-keys --user-name mmae-ses-smtp` |
| `SMTP_PASSWORD` | Derived from SES SMTP secret key (AWS4 HMAC derivation). Must re-derive on rebuild. |
| `IMAGE_MIN_WIDTH` | `800` |
| `IMAGE_MIN_HEIGHT` | `600` |
| `IMAGE_QUALITY_THRESHOLD` | `150.0` |
| `VLM_CONFIDENCE_THRESHOLD` | `0.7` |
| `APP_ENV` | `prod` |
| `LOG_LEVEL` | `INFO` |

### Deriving SES SMTP Password
```python
import hmac, hashlib, base64

def derive_ses_smtp_password(secret_access_key: str, region: str = "ap-southeast-1") -> str:
    date = "11111111"
    service = "ses"
    terminal = "aws4_request"
    message = "SendRawEmail"
    version = 0x04

    def sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    key = sign(sign(sign(sign(("AWS4" + secret_access_key).encode(), date), region), service), terminal)
    return base64.b64encode(bytes([version]) + sign(key, message)).decode()
```

---

## 5. Docker Services

All 5 services run on EC2 via `docker-compose.prod.yml`. Memory limits are tight for t2.micro (1 GB total):

| Service | Image Source | Port (host) | Mem Limit | Notes |
|---|---|---|---|---|
| `app` | Built from `./Dockerfile` | `8000` (127.0.0.1 only) | 768 MB | FastAPI + LangGraph. nginx proxies 80/443 → 8000. |
| `qdrant` | `qdrant/qdrant:latest` | `127.0.0.1:6333` | 256 MB | Vector store. Data in named volume `qdrant_data`. |
| `mcp-rag` | Built from `./mcp_servers/rag` | (internal only) | 1 GB | Uses `platform: linux/amd64`. HuggingFace cache in `hf_cache` volume. |
| `mcp-db` | Built from `./mcp_servers/db` | (internal only) | 384 MB | Talks to RDS directly via env var. |
| `mcp-currency` | Built from `./mcp_servers/currency` | (internal only) | 256 MB | No secrets needed — calls Frankfurter API. |
| `mcp-email` | Built from `./mcp_servers/email` | (internal only) | 128 MB | Needs SMTP env vars. |

**Named Docker volumes** (survive container restarts, must be backed up before teardown):
- `qdrant_data` — policy vector embeddings (~35 points, easily re-ingested)
- `hf_cache` — HuggingFace model cache for mcp-rag (large, saves ~2 min on first start)

**Bind mounts** (on EC2 filesystem):
- `./uploads:/data/uploads` — receipt images uploaded by users. **Back these up before teardown** if any production claims were submitted with images.

---

## 6. nginx Configuration

nginx owns ports 80 and 443 on the EC2 host. Config at `/etc/nginx/conf.d/mmga.conf`:

```nginx
server {
    listen 80;
    server_name mmga.mdaie-sutd.fit;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name mmga.mdaie-sutd.fit;

    ssl_certificate     /etc/letsencrypt/live/mmga.mdaie-sutd.fit/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mmga.mdaie-sutd.fit/privkey.pem;

    # Security headers (added 2026-04-26)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;  # LangGraph claims take 60-120s
    }
}
```

SSL cert managed by Certbot (Let's Encrypt). On rebuild:
```bash
sudo certbot --nginx -d mmga.mdaie-sutd.fit
```

---

## 7. Database Schema

Current Alembic head: `014_add_email_to_users` (14 migrations applied in order).

| Migration | What it does |
|---|---|
| `001_initial_schema` | `claims`, `receipts`, `audit_log` tables |
| `002_add_dual_currency_columns` | `original_amount`, `original_currency`, `exchange_rate`, `converted_amount` on `receipts` |
| `003_add_intake_findings` | `intake_findings` on `claims` |
| `004_add_claim_number_sequence` | Auto-incrementing claim number |
| `005_add_users_table` | `users` table with session auth |
| `006_add_agent_output_columns` | Agent output fields on `claims` |
| `007_add_advisor_findings_column` | `advisor_findings` on `claims` |
| `008_add_category_column` | `category` on `receipts` |
| `009_add_policy_content_table` | `policy_content` table |
| `010_add_justification_to_claims` | `user_justification`, `abuse_flags` on `claims` |
| `011_add_user_quota_usage_table` | `user_quota_usage` table |
| `012_extend_audit_action_values` | Extends `audit_log.action` enum |
| `013_add_eval_runs_tables` | `eval_runs`, `eval_results` tables |
| `014_add_email_to_users` | `email` column on `users` (applied via direct ALTER on RDS) |

### Users (seeded data to recreate)

| username | role | employee_id | display_name | email |
|---|---|---|---|---|
| `james` | `reviewer` | `909090` | James Oon | `jamesooneh@gmail.com` |
| `tung` | `reviewer` | `909091` | Tung | (unknown) |
| `sagar` | `user` | `1010736` | Sagar | `sagarpratapsingh15@gmail.com` |
| `josiah` | `user` | `1010740` | Josiah | (unknown) |

Passwords are bcrypt-hashed in the DB. On rebuild, reset via the app's admin surface or directly via psql.

---

## 8. External Service Dependencies

| Service | Purpose | How to re-provision |
|---|---|---|
| **OpenRouter** | LLM (qwen3-235b) + VLM (gemini-2.0-flash) inference | Log in at openrouter.ai, create new API key, update `.env.prod` |
| **AWS SES** | Outbound email for claim notifications | Already configured — domain `mdaie-sutd.fit` verified, sender `claims@mdaie-sutd.fit`. IAM user `mmae-ses-smtp` holds SMTP credentials. SES may still be in sandbox. |
| **Frankfurter API** | Currency conversion (EUR/MYR/USD → SGD) | No key needed — free public API. Note: VND not supported. |
| **Let's Encrypt** | TLS cert for `mmga.mdaie-sutd.fit` | Run `certbot --nginx` on EC2 — auto-renews every 90 days. |
| **HuggingFace** | `all-MiniLM-L6-v2` embedding model for mcp-rag | Auto-downloaded on first start. No API key needed for this model. |

---

## 9. Rebuild Procedure

### Prerequisites (on your Mac)
- `aws` CLI configured with `iamadmin` credentials
- `docker` with buildx for `linux/amd64` (`/Applications/Docker.app/Contents/Resources/bin/docker`)
- `~/.ssh/id_ed25519` (for EC2 Instance Connect)

### Step 1 — Provision Infrastructure
```bash
# Edit config.sh if needed (region, instance types)
./scripts/aws/01-setup-infra.sh
```

This creates: VPC, subnets, IGW, NAT gateway, security groups, RDS (takes 5-10 min), ECR repos, Lambda IAM role, EC2 instance. Resource IDs saved to `scripts/aws/.deploy-state`.

### Step 2 — Configure .env.prod
```bash
cp .env.prod.example .env.prod
# Fill in:
#   POSTGRES_PASSWORD  ← new strong password
#   OPENROUTER_API_KEY ← from openrouter.ai
#   SESSION_SECRET_KEY ← generate: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
#   SMTP_HOST          ← email-smtp.ap-southeast-1.amazonaws.com
#   SMTP_PORT          ← 587
#   SMTP_USER          ← SES SMTP username for mmae-ses-smtp IAM user
#   SMTP_PASSWORD      ← derived via SES SMTP derivation function (see §4)
```

### Step 3 — Build and Deploy Docker Images
```bash
# Option A: S3 tar approach (used in original deploy)
docker build --platform linux/amd64 -t mmga-app:latest .
docker build --platform linux/amd64 -t mmga-mcp-rag:latest ./mcp_servers/rag
docker build --platform linux/amd64 -t mmga-mcp-db:latest ./mcp_servers/db
docker build --platform linux/amd64 -t mmga-mcp-currency:latest ./mcp_servers/currency
docker build --platform linux/amd64 -t mmga-mcp-email:latest ./mcp_servers/email

docker save mmga-app mmga-mcp-rag mmga-mcp-db mmga-mcp-currency mmga-mcp-email \
  | gzip > /tmp/mmga-images.tar.gz

aws s3 cp /tmp/mmga-images.tar.gz s3://mmga-expense-deploy/mmga-images.tar.gz

# Option B: rsync source + build on EC2 (simpler, requires EC2 to have Docker + Poetry)
./scripts/aws/03-deploy-ec2.sh
```

### Step 4 — SSH into EC2 and Start Services
```bash
# Send Instance Connect key, SSH in
aws ec2-instance-connect send-ssh-public-key \
  --instance-id <new-instance-id> \
  --instance-os-user ec2-user \
  --ssh-public-key file://~/.ssh/id_ed25519.pub \
  --availability-zone ap-southeast-1a

ssh -i ~/.ssh/id_ed25519 ec2-user@<new-public-ip>

# On EC2:
cd /opt/mmga-expense
docker compose -f docker-compose.prod.yml up -d --build
```

### Step 5 — Post-Deploy
```bash
./scripts/aws/04-post-deploy.sh
# or manually on EC2:
docker compose -f docker-compose.prod.yml exec app python -m alembic upgrade head
docker compose -f docker-compose.prod.yml exec app python scripts/ingest_policies.py
```

### Step 6 — nginx + TLS
```bash
# On EC2:
sudo dnf install -y nginx certbot python3-certbot-nginx
sudo systemctl enable --now nginx

# Create /etc/nginx/conf.d/mmga.conf (see §6 for full config)
# Add the proxy_pass block pointing to 127.0.0.1:8000

sudo certbot --nginx -d mmga.mdaie-sutd.fit
```

### Step 7 — Update Route53

After the new EC2 gets an Elastic IP (or any stable IP):
```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id Z089465439W0RXJJ0LOEW \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "mmga.mdaie-sutd.fit",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{"Value": "<new-ip>"}]
      }
    }]
  }'
```

### Step 8 — Seed Users
```bash
# On EC2, via psql or app admin surface:
# INSERT into users table for james/tung/sagar/josiah (see §7 for details)
# Set bcrypt-hashed passwords
```

---

## 10. Teardown Procedure

```bash
# This destroys ALL AWS resources. Reads IDs from scripts/aws/.deploy-state.
./scripts/aws/teardown.sh
# Type 'destroy' to confirm

# Resources NOT covered by teardown.sh — delete manually:
aws s3 rm s3://mmga-expense-deploy/ --recursive
aws s3api delete-bucket --bucket mmga-expense-deploy

# Route53 A record (leave hosted zone, just remove the A record):
aws route53 change-resource-record-sets \
  --hosted-zone-id Z089465439W0RXJJ0LOEW \
  --change-batch '{"Changes":[{"Action":"DELETE","ResourceRecordSet":{"Name":"mmga.mdaie-sutd.fit","Type":"A","TTL":300,"ResourceRecords":[{"Value":"13.213.13.39"}]}}]}'

# ECR repos (if not already deleted by teardown):
for repo in mmga-app mmga-mcp-rag mmga-mcp-db mmga-mcp-currency mmga-mcp-email; do
  aws ecr delete-repository --repository-name $repo --force --region ap-southeast-1
done
```

After teardown, **rotate these credentials**:
- `POSTGRES_PASSWORD` (set a new one in `.env.prod` for next deploy)
- `OPENROUTER_API_KEY` (revoke old key at openrouter.ai)
- `SESSION_SECRET_KEY` (generate new one)

---

## 11. Known Gotchas (from Mistakes Log)

| Issue | What to do |
|---|---|
| Port 8000 must not be publicly exposed | Use `"127.0.0.1:8000:8000"` in `docker-compose.prod.yml`, not `"8000:8000"` |
| nginx owns port 80 — never map app container to port 80 | nginx proxies 80/443 → 8000; app container should never bind port 80 |
| SMTP_HOST=mailhog means stub mode | Set `SMTP_HOST=email-smtp.ap-southeast-1.amazonaws.com` and `SMTP_PORT=587` |
| `./static` is mounted read-only | Receipt images go to `./uploads:/data/uploads` (writable bind mount) |
| EC2 Instance Connect key expires in 60 seconds | Run `send-ssh-public-key` then SSH immediately |
| `POSTGRES_HOST` via shell var in compose causes silent failures | Load from `.env.prod` directly; never use `${RDS_ENDPOINT}` shell expansion in compose |
| SES sandbox limits sending to verified addresses only | Verify recipient emails in SES console, or request production access |
| VND not supported by Frankfurter API | Only 30 ECB currencies. MYR is supported but agent must send ISO code, not symbol "RM" |
| mcp-rag requires `platform: linux/amd64` | sentence-transformers has ARM issues — always specify this in compose |
| HuggingFace model download takes ~90s on first mcp-rag start | Set `start_period: 90s` in healthcheck |
| Security headers must be in nginx, not app | nginx adds all 6 headers (HSTS, X-Frame-Options, etc.) — app doesn't set them |
