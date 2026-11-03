# PRAVISION — Universal OSINT & Intelligence Platform
> *"See Everything. Connect Everything. Understand Everything."*

**PRAVISION** is an enterprise-grade Universal OSINT and Intelligence Investigation Platform modeled after Palantir Gotham. It combines automated entity classification, multi-source intelligence gathering, recursive discovery, cross-case entity resolution, advanced link-graph analytics, geospatial situational awareness, and granular role-based access control (RBAC) into a cohesive dark-first analytical environment.

---

## ⚡ Core Philosophy: ONE INPUT → UNIFIED INTELLIGENCE

The investigator inputs any seed entity (Username, Email, Phone, Domain, IP, Media, Document, Flight, or Coordinates) and the platform handles the orchestration:

```
SEED INPUT (Username, Email, Phone, Domain, IP, Media, Flight, Coords)
   │
   ▼
[Universal Input Classifier] ➔ Detects Entity Type & Sets Investigation Mode
   │
   ▼
[Concurrent Connector Orchestrator] ➔ Queries 89 Registered OSINT Sources
   │
   ▼
[Recursive Intelligence Engine] ➔ Expands Discovered Entities with Depth Bounds
   │
   ▼
[Entity Resolution Engine v2] ➔ Normalization, Lexical/Attribute Scoring & Conflict Detection
   │
   ▼
[Link Graph & Community Analytics] ➔ Network Centrality, Shortest Path & GEXF Export
   │
   ▼
[Unified Intelligence Dossier] ➔ Case Management, Encrypted Streaming Archive & Reports
```

---

## 🏛️ Gotham-Level Analytical Architecture

PRAVISION delivers a unified intelligence environment across 19 lazy-loaded analytical views:

1. **Unified Intelligence Ontology**: Strict provenance attribution linking all entities, relationships, and evidence to specific source connectors, confidence levels, and parent investigations.
2. **Entity Resolution Engine v2**: Multi-factor probabilistic entity matching (exact match, lexical similarity, shared attributes, graph overlap) with automated conflict detection. Supports non-destructive entity merging and unmerging with complete audit trails.
3. **Advanced Link Graph Engine**: Powered by NetworkX with multi-hop neighborhood expansion, shortest path segment tracing, Degree/Betweenness/Closeness centrality, and Louvain community detection. Exports to standard GEXF format.
4. **Cross-Case Unified Search**: Full-text and property-level search across all historical cases, entities, relationships, and evidence objects.
5. **Entity Dossier Drawer**: Comprehensive slide-out dossier detailing aliases, identifiers, provenance, linked relationships, and raw evidence metadata.
6. **Live Situational Map**: Geospatial visualization integrating OpenSky Network live ADS-B flight telemetry, USGS earthquake data, and geocoded evidence.
7. **Streaming Encrypted Archives**: Memory-efficient AES-256-GCM chunked streaming for exporting massive multi-gigabyte case dossiers without OOM or gateway timeouts.

---

## 🧭 Investigation Modes

| Mode | Name | Key Capabilities |
| :--- | :--- | :--- |
| **Mode 1** | Public Identity Intelligence | Sherlock, Maigret, GHunt, SocialScan, public handle mapping |
| **Mode 2** | Media & Document Intelligence | EXIF camera metadata, GPS tags, perceptual hashes, Error Level Analysis (ELA) |
| **Mode 3** | Email Intelligence | MX DNS routing, GHunt Google Gaia discovery, EmailRep, HIBP exposure |
| **Mode 4** | Phone Intelligence | E.164 normalization, international carrier detection, region classification |
| **Mode 5** | Website & Domain Intelligence | Subfinder (CRT.sh), DNSx multi-record resolver, WhatWeb, TLS profiling |
| **Mode 6** | Organization & Asset Intelligence | Passive ASN lookup, Shodan / Censys adapters, Nmap policy guard |
| **Mode 7** | Global Situational Intelligence | OpenSky Network live aircraft ADS-B, USGS Earthquakes, OpenStreetMap |

---

## 🔒 Security, Authentication & Multi-User RBAC

PRAVISION enforces strict enterprise security controls:
- **Authentication**: JWT authentication with Argon2 / PBKDF2 password hashing.
- **Three-Tier RBAC**:
  - `admin`: Full administrative access, user management, connector controls, case creation, and evidence manipulation.
  - `case_officer`: Case creation, evidence uploads, dossier exports, and investigative queries.
  - `analyst`: Read-only analytical access to cases, graphs, and searches.
- **Audit Trails**: Complete transaction audit logging for all entity merges, case modifications, and archive exports.

---

## ☁️ Cloud Infrastructure & Deployment

### Primary Cloud Stack
- **Database**: [Neon Lakebase PostgreSQL](https://neon.tech/) with pooled connections via `asyncpg`.
- **Object Storage**: Neon S3-Compatible Object Storage for evidence storage and streaming archives.
- **Edge CDN & Protection**: Cloudflare Pages for global frontend distribution with strict edge security headers.
- **Edge Routing**: Cloudflare Tunnel (`cloudflared`) providing zero-inbound-port access to the containerized FastAPI backend.

### Dual-Layer Resilience & Disaster Recovery
If cloud services are unreachable, PRAVISION automatically degrades gracefully:
- **Database Fallback**: SQLite with Write-Ahead Logging (WAL) and automatic journal mode.
- **Storage Fallback**: Local AES-encrypted Evidence Vault (`backend/evidence_vault/`).
- **Recovery**: Automatic reconnection and state synchronization upon service restoration.

See [PRAVISION_CLOUDFLARE_DEPLOYMENT_GUIDE.md](file:///C:/Users/hp/OneDrive/Desktop/PRAVISION/PRAVISION_CLOUDFLARE_DEPLOYMENT_GUIDE.md) for full deployment instructions.

---

## 🚀 Quickstart

### 1. Local Development
```powershell
# Run setup script (checks Python 3.12, Node.js 20+, venv)
powershell -ExecutionPolicy Bypass -File .\setup_pravision.ps1

# Start the application
.\start_pravision.bat
```

### 2. Production Docker Deployment
```bash
# Copy and configure environment variables
cp .env.production.example .env

# Build and run with Docker Compose
docker compose -f deploy/cloudflare/docker-compose.prod.yml up -d --build
```

---

## 🧪 Testing & Verification

The platform includes end-to-end regression and verification test suites:
```bash
# Run 20-Step Gotham Workflow Acceptance Test
python -m pytest backend/tests/verify_gotham_workflow.py -v

# Run Playwright E2E Browser Suite (18 tests across 8 suites)
cd frontend
npx playwright test
```

---

## 📜 License & Compliance
This software is provided for authorized intelligence analysis, cybersecurity investigations, and academic research. Users must comply with all applicable local, national, and international laws and data privacy regulations.
