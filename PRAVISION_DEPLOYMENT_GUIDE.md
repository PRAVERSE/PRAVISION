# PRAVISION — PRODUCTION DEPLOYMENT & OPERATIONS GUIDE (PHASE 2.5)

**Platform:** PRAVISION — Universal OSINT & Intelligence Platform  
**Target Environment:** Containerized Production (Docker / Podman / Kubernetes) & Standalone Local Workstation  
**Revision:** Phase 2.5 Final Production Release  

---

## 1. SYSTEM REQUIREMENTS & PREREQUISITES

### 1.1 Compute & Host Requirements
- **Operating System:** Linux (Ubuntu 22.04 LTS / Debian 12 / RHEL 9) or Windows 11 / Windows Server 2022.
- **CPU:** Minimum 2 cores (Recommended: 4+ cores for concurrent multi-source recursive OSINT discovery).
- **RAM:** Minimum 4 GB (Recommended: 8 GB for high-density NetworkX link graphs and large streaming evidence packages).
- **Disk:** Minimum 20 GB SSD storage for local caching, SQLite WAL journals, and temporary archive buffers.
- **Network:** Outbound HTTPS (TCP port 443) access to OpenSky Network (`opensky-network.org`), USGS feeds (`earthquake.usgs.gov`), Neon PostgreSQL, and Neon Object Storage S3.

### 1.2 Software Dependencies
- **Docker Engine:** Version 24.0+ & Docker Compose v2.20+.
- **Node.js (for local dev):** Node.js 20.x or 22.x LTS with npm 10+.
- **Python (for local dev):** Python 3.12.x with `venv` and pip.

---

## 2. ENVIRONMENT CONFIGURATION REFERENCE

Create a secure `.env` file in the project root:

```ini
# ==============================================================================
# PRAVISION PRODUCTION CONFIGURATION
# ==============================================================================

# Database Settings (Neon PostgreSQL or Local SQLite fallback)
DATABASE_URL=postgresql+asyncpg://<USER>:<PASSWORD>@ep-dark-mud-ao78ldb6-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?ssl=require
NEON_BRANCH=production

# Object Storage Settings (Neon S3-Compatible Storage)
S3_ENDPOINT_URL=https://br-red-breeze-aom32nma.storage.c-2.ap-southeast-1.aws.neon.tech
S3_BUCKET_NAME=pravision-evidence
S3_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=<NEON_STORAGE_ACCESS_KEY>
AWS_SECRET_ACCESS_KEY=<NEON_STORAGE_SECRET_KEY>

# Security & RBAC Configuration
JWT_SECRET=<SECURE_RANDOM_64_CHAR_HEX_KEY>
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Initial Provisioning Passwords (Seeded on first initialization only)
ADMIN_INITIAL_PASSWORD=PravisionAdmin2026!
OFFICER_INITIAL_PASSWORD=PravisionOfficer2026!
ANALYST_INITIAL_PASSWORD=PravisionAnalyst2026!

# Network & Gateway Settings
HOST=127.0.0.1
PORT=8000
WORKSPACE_DIR=./data
```

> [!WARNING]
> Ensure `.env`, `.env.local`, `backend/.auth_secret`, and `backend/.initial_admin_credentials` are strictly excluded from git version control. Verify with `git status --ignored`.

---

## 3. DOCKER PRODUCTION DEPLOYMENT

### 3.1 Building and Launching the Service
To build and start the multi-stage production container:

```bash
docker compose up -d --build
```

### 3.2 Inspecting Service Logs & Health
Verify backend startup, database initialization, and connector registration:

```bash
docker compose logs -f pravision
```

Expected log output:
```
[INFO] pravision.storage.db: Database initialized successfully on Neon Lakebase Postgres
[INFO] pravision.auth: Default multi-user accounts provisioned (admin, case_officer, analyst).
[INFO] pravision.storage.backup: PRAVISION BackupScheduler started (interval: 3600s).
[INFO] Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Check Docker container health status:
```bash
docker compose ps
```

---

## 4. PRODUCTION REVERSE PROXY CONFIGURATION (NGINX)

For enterprise network deployments with TLS termination and WebSocket support, deploy Nginx in front of PRAVISION:

```nginx
server {
    listen 443 ssl http2;
    server_name pravision.internal.agency;

    ssl_certificate /etc/ssl/certs/pravision.crt;
    ssl_certificate_key /etc/ssl/private/pravision.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' wss: https:;" always;

    # Maximum payload size for evidence uploads
    client_max_body_size 60M;

    # API and Frontend Proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Proxy for Real-Time Investigation Telemetry
    location ~* ^/api/investigations/.+/live$ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

---

## 5. LOCAL WORKSTATION DEPLOYMENT

For air-gapped forensic laptops or developer workstations running locally:

### 5.1 Backend Setup
```bash
# 1. Create and activate Python virtual environment
python -m venv venv
.\venv\Scripts\activate   # On Windows
source venv/bin/activate  # On Linux/macOS

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Initialize Database & Security Seed
python -c "import asyncio; from backend.app.storage.database import init_db; from backend.app.auth.auth_service import auth_service; asyncio.run(init_db()); asyncio.run(auth_service.seed_default_users())"

# 4. Start Backend Server
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

### 5.2 Frontend Setup & Build
```bash
# 1. Install frontend packages
npm --prefix frontend install

# 2. Build production assets
npm --prefix frontend run build

# 3. For local development with hot reload:
npm --prefix frontend run dev
```

---

## 6. DAY-1 POST-DEPLOYMENT VERIFICATION CHECKLIST

Execute the automated verification suites to confirm 100% operational integrity:

1. **Multi-User Security & RBAC Verification:**
   ```bash
   python backend/tests/verify_phase_2_5_auth_rbac.py
   # Expected: 16 PASSED, 0 FAILED
   ```
2. **Streaming Cryptographic Archive Verification:**
   ```bash
   python backend/tests/verify_phase_2_5_streaming_archive.py
   # Expected: 10 PASSED, 0 FAILED
   ```
3. **OpenSky Telemetry Gateway Verification:**
   ```bash
   python backend/tests/verify_phase_2_5_opensky.py
   # Expected: 9 PASSED, 0 FAILED
   ```
4. **End-to-End Playwright Browser Automation:**
   ```bash
   npx --prefix frontend playwright test --config frontend/playwright.config.ts
   # Expected: 14 PASSED across all 7 suites
   ```
5. **Security & Reliability Regression Suite:**
   ```bash
   python backend/tests/verify_reliability_regression.py
   # Expected: ALL TESTS PASSED 100%
   ```
