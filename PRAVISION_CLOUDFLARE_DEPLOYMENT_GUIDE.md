# PRAVISION — Production Cloudflare Deployment Runbook

**Platform:** PRAVISION — Universal OSINT & Intelligence Platform  
**Architecture:** Cloudflare Pages (Frontend) + Containerized FastAPI via Cloudflare Tunnel (Backend)  
**Database:** Neon Lakebase PostgreSQL (AWS ap-southeast-1)  
**Object Storage:** Neon S3-Compatible Object Storage (`pravision-evidence`)  
**Official Repository:** `https://github.com/PRAVERSE/PRAVISION/`

---

## 1. Architectural Overview & Cloudflare Runtime Evaluation

PRAVISION is a production-grade intelligence analysis platform requiring:
1. High-concurrency async PostgreSQL connection pooling via `asyncpg`.
2. Encrypted streaming evidence archives with AES-256-GCM.
3. Bidirectional WebSockets for real-time live investigation telemetry.
4. OS subprocess execution for investigative connectors (Nmap, Sherlock, ExifTool, DNS resolvers).
5. OpenSky flight telemetry ingestion and geospatial caching.

### Why Cloudflare Pages + Cloudflare Tunnel?

| Dimension | Native Cloudflare Python Workers (Pyodide) | Cloudflare Pages + Cloudflare Tunnel (Selected) |
| :--- | :--- | :--- |
| **TCP Sockets** | No raw TCP sockets (breaks `asyncpg` connection pool to Neon) | Full TCP socket pooling with `asyncpg` directly to Neon |
| **C-Extensions** | Severe WebAssembly compilation limitations (Argon2, Cryptography) | Native Linux x86_64 / arm64 Python 3.12 binaries |
| **Subprocess Connectors**| Forbidden (Pyodide sandbox has no OS kernel or forks) | Full Linux process isolation for all 89 OSINT connectors |
| **Streaming Archives** | Limited memory (128MB max, timeout in seconds) | Chunked streaming AES-256-GCM with zero file truncation |
| **WebSockets** | Constrained session durations | Long-lived persistent WebSocket connections |
| **Edge Performance** | Not applicable | Global edge CDN, DDoS mitigation, HTTP/3, and automatic SSL |

**Verdict:** The verified production architecture pairs **Cloudflare Pages** (for global edge frontend distribution) with **Cloudflare Tunnel (`cloudflared`)** (for secure, zero-inbound-port communication to the FastAPI container).

```
[ User Browser ]
       |
       +---> (HTTPS/WSS) ---> Cloudflare Global Edge
                                    |
      +-----------------------------+-----------------------------+
      | (Static Assets & SPA)                                     | (API / WebSocket Requests)
      v                                                           v
[ Cloudflare Pages ]                                     [ Cloudflare Tunnel ]
(React 19 + Vite 8 SPA)                                           |
                                                                  v (Zero-Inbound Tunnel)
                                                         [ Docker Container: PRAVISION ]
                                                           - Python 3.12 + FastAPI
                                                           - 89 OSINT Connectors
                                                           - Entity Resolution v2
                                                           - Link Graph Analytics
                                                                  |
                                      +---------------------------+---------------------------+
                                      |                                                       |
                                      v                                                       v
                          [ Neon Lakebase Postgres ]                             [ Neon Object Storage ]
                           (Production Branch)                                    (S3-Compatible Bucket)
```

---

## 2. Prerequisites

1. **Cloudflare Account**: Access to Cloudflare dashboard with your domain added.
2. **Neon Console**: PostgreSQL database on `production` branch and S3 object storage credentials.
3. **Deployment Host**: A host or virtual machine with Docker and Docker Compose installed (AWS EC2, GCP Compute Engine, DigitalOcean Droplet, Hetzner, or on-premises server).
4. **Git Access**: Access to GitHub repository `PRAVERSE/PRAVISION`.

---

## 3. Frontend Deployment (Cloudflare Pages)

### Step 3.1: Connect Repository to Cloudflare Pages
1. Log in to the [Cloudflare Dashboard](https://dash.cloudflare.com/).
2. Navigate to **Workers & Pages** > **Create application** > **Pages** > **Connect to Git**.
3. Select the repository: `PRAVERSE/PRAVISION`.
4. Choose the production branch: `main`.

### Step 3.2: Configure Build Settings
Configure the build parameters exactly as follows:
- **Framework preset**: `Vite`
- **Root directory**: `frontend`
- **Build command**: `npm run build`
- **Build output directory**: `dist`
- **Node.js Version**: In Environment Variables, set `NODE_VERSION` to `20.18.0` or higher.

### Step 3.3: Configure Production Environment Variables
In the Cloudflare Pages settings under **Environment variables** (Production):
- `VITE_API_BASE_URL`: `https://api.yourdomain.com/api` (or `/api` if using Cloudflare Pages Functions reverse proxy)
- `VITE_WS_URL`: `wss://api.yourdomain.com`

### Step 3.4: SPA Routing and Edge Headers
The repository already includes:
- `frontend/public/_redirects`: Contains `/*    /index.html   200` to prevent 404s on browser refreshes.
- `frontend/public/_headers`: Enforces strict Content Security, Clickjacking protection (`X-Frame-Options: DENY`), and MIME-type sniffing prevention.

Click **Save and Deploy**. Cloudflare Pages will build and deploy the frontend globally in under 60 seconds.

---

## 4. Backend Deployment (Docker + Cloudflare Tunnel)

### Step 4.1: Create a Cloudflare Tunnel
1. In Cloudflare Dashboard, go to **Zero Trust** > **Networks** > **Tunnels**.
2. Click **Create a Tunnel** > Select **Cloudflare Tunnel (cloudflared)**.
3. Name your tunnel: `pravision-production-tunnel`.
4. Cloudflare will generate a `TUNNEL_TOKEN`. Copy this token.

### Step 4.2: Configure Public Hostname in Cloudflare
In the Tunnel settings under **Public Hostnames**:
- **Subdomain**: `api`
- **Domain**: `yourdomain.com` (e.g. `api.yourdomain.com`)
- **Service Type**: `HTTP`
- **URL**: `pravision_backend:8000`
- Under **Additional application settings** > **HTTP Settings**:
  - Enable **HTTP/2**.
  - Enable **WebSockets**.

### Step 4.3: Deploy on Host via Docker Compose
On your target deployment host:

```bash
# Clone the repository
git clone https://github.com/PRAVERSE/PRAVISION.git
cd PRAVISION

# Copy environment template
cp .env.production.example .env

# Edit .env with your real credentials:
# - DATABASE_URL (Neon pooled PostgreSQL URL)
# - AWS_ACCESS_KEY_ID & AWS_SECRET_ACCESS_KEY (Neon S3)
# - S3_ENDPOINT_URL & S3_BUCKET_NAME
# - JWT_SECRET (generate via `openssl rand -hex 32`)
# - CLOUDFLARE_TUNNEL_TOKEN (from step 4.1)
nano .env

# Launch production stack
docker compose -f deploy/cloudflare/docker-compose.prod.yml up -d --build
```

### Step 4.4: Verify Backend Health
Verify the container status:
```bash
docker compose -f deploy/cloudflare/docker-compose.prod.yml ps
```
Verify the health endpoint over the public Cloudflare edge:
```bash
curl -I https://api.yourdomain.com/api/storage/status
```
Expected response:
```http
HTTP/2 200
content-type: application/json
```

---

## 5. Security & Multi-User RBAC Configuration

### Initial Admin Bootstrap
PRAVISION automatically initializes three pre-configured accounts upon first boot if they do not exist:
- **Administrator**: `admin`
- **Case Officer**: `officer`
- **Analyst**: `analyst`

Initial passwords are read from `.env` (`ADMIN_INITIAL_PASSWORD`, `OFFICER_INITIAL_PASSWORD`, `ANALYST_INITIAL_PASSWORD`).

> [!IMPORTANT]
> Immediately after initial login:
> 1. Log in as `admin`.
> 2. Navigate to **Platform Settings** > **User Accounts**.
> 3. Update the administrator password and generate analyst accounts.
> 4. Ensure passwords meet minimum complexity: at least 12 characters, uppercase, lowercase, numbers, and symbols.

### RBAC Permission Matrix

| Role | Case Creation | Evidence Upload | Streaming Archive Export | User Management | Connector Management |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Admin** | Yes | Yes | Yes | Yes | Yes |
| **Case Officer** | Yes | Yes | Yes | Read-Only | Read-Only |
| **Analyst** | Read-Only | Read-Only | Read-Only | No | Read-Only |

---

## 6. Disaster Recovery & Fallback Operation

PRAVISION features dual-layer redundancy:
1. **Primary Cloud Engine**: Neon Lakebase PostgreSQL + Neon S3 Object Storage.
2. **Local Fallback Engine**: If Neon cloud is temporarily unreachable or undergoing maintenance:
   - Backend automatically degrades gracefully to local SQLite WAL database.
   - Evidence files persist safely to local encrypted Evidence Vault (`/app/backend/data/vault`).
   - Audit logs capture all offline transactions.
   - When Neon connectivity is restored, system resumes normal operations without restart.

---

## 7. Operational Verification Checklist

- [ ] Frontend builds successfully with `npm run build` (2,075 modules transformed, 0 errors).
- [ ] SPA routing works on direct refresh of subpages (verified via `_redirects`).
- [ ] Cloudflare edge headers active (verified via `_headers`).
- [ ] Backend container healthy (`/api/storage/status` returns `postgres_neon` and `neon_s3_compatible`).
- [ ] JWT authentication succeeds at `/api/auth/login`.
- [ ] Live WebSocket connects at `wss://api.yourdomain.com/api/investigations/{id}/live`.
- [ ] OpenSky aircraft telemetry stream functions through `/api/geospatial/flights`.
- [ ] Case dossier AES-256-GCM streaming download operates without timeout.

