# PRAVISION — PHASE 2 FINAL DELIVERY & AUDIT REPORT
## Universal OSINT & Intelligence Platform
### Gotham-Inspired Intelligence Workstation, Full Functional Audit, 89-Tool Capability Matrix & Hybrid Cloud Architecture

---

## EXECUTIVE SUMMARY

**PRAVISION** has undergone a complete, rigorous Phase 2 operational audit, repair cycle, and architectural expansion, transforming the system from an experimental prototype into a unified, dark-first intelligence analysis workstation inspired by the capabilities of Palantir Gotham.

```
+----------------------------------------------------------------------------------------------------+
|                                    PRAVISION GOTHAM WORKSTATION                                    |
|                   "See Everything. Connect Everything. Understand Everything."                     |
+----------------------------------------------------------------------------------------------------+
                                                  |
       +------------------------------------------+------------------------------------------+
       |                                          |                                          |
       v                                          v                                          v
+-----------------------------+    +-----------------------------+    +-----------------------------+
|    INTELLIGENCE INTAKE      |    |     INTELLIGENCE ENGINE     |    |    ANALYTICAL WORKSPACES    |
| - Multi-Modal Classifier    |    | - 89 Validated Connectors   |    | - Command Center Mission    |
| - Depth Controller (Fixed)  |    | - NetworkX Graph Analytics  |    | - Case Dossier Management   |
| - Provenance Tracker        |    | - Entity Resolution & Gaps  |    | - Gotham Relational Graph   |
| - Rate Limiter & Concurrency|    | - Multi-Timestamp Timeline  |    | - Global Tactical Map       |
| - Memory Ephemeral Buffer   |    | - Threat Scoring (IOC Guard)|    | - AI Grounded Copilot       |
+-----------------------------+    +-----------------------------+    +-----------------------------+
                                                  |
       +------------------------------------------+------------------------------------------+
       |                                                                                     |
       v                                                                                     v
+-------------------------------------------------------------+    +--------------------------------+
|             STORAGE & EVIDENCE ARCHITECTURE                 |    |      SECURITY & INTEGRITY      |
| - Standalone Local Zero-Config SQLite (WAL Enabled)         |    | - SHA-256 Chain of Custody     |
| - Enterprise PostgreSQL Cloud Driver (asyncpg)              |    | - Zero-Persistence RAM Mode    |
| - Backblaze B2 S3-Compatible Cloud Storage Integration      |    | - PII Log Sanitization         |
| - Secure Local Filesystem Evidence Vault Fallback           |    | - Policy-Restricted Boundaries |
+-------------------------------------------------------------+    +--------------------------------+
```

---

## SECTION A: SYSTEM AUDIT FINDINGS & DEFECT RESOLUTION

Prior to expanding functionality, every Phase 1 component was independently audited and executed against live targets. The audit revealed critical defects, incomplete stubs, and import omissions that have been permanently diagnosed and repaired:

### 1. Depth Controller Off-by-One Recursion Defect
- **Location**: `backend/app/engine/depth_controller.py`
- **Root Cause**: `can_expand()` previously evaluated `if current_depth >= self.max_depth: return False`. When an analyst initiated an investigation with `max_depth = 1`, root entities (at depth 1) evaluated `1 >= 1` -> returned `False`. This silently aborted all single-depth investigations with zero executed connectors and zero findings.
- **Resolution**: Changed condition to `if current_depth > self.max_depth: return False`. Investigations at depth 1 now execute root connectors properly, and investigations at depth 2+ expand discovered entities accurately.

### 2. Missing Module Import in Geographic Connectors
- **Location**: `backend/app/connectors/geographic/geo_connectors.py`
- **Root Cause**: `GoogleEarthConnector` attempted to invoke `urllib.parse.quote()`, but `urllib.parse` was never imported, triggering an unhandled `NameError: name 'urllib' is not defined`.
- **Resolution**: Added `import urllib.parse` at module head.

### 3. Cross-Tool Entity Deduplication Collision
- **Location**: `backend/app/evidence/source_deduplicator.py`
- **Root Cause**: Findings deduplication generated a signature including `source_name` (`f"{source}:{entity_type}:{val}"`), which defeated cross-tool corroboration (e.g., findings discovered by both Sherlock and Maigret remained separate items rather than corroborated duplicates).
- **Resolution**: Changed signature to `f"{entity_type}:{normalized_value}"`, merging multiple discovery sources into `supporting_sources` and elevating confidence levels to `CORROBORATED`.

### 4. Windows cp1252 Unicode Console Logging Defect
- **Location**: Windows execution environment and subprocess launchers
- **Root Cause**: GHunt output containing emojis (e.g. `\U0001f426`) threw `UnicodeEncodeError` under Windows default `cp1252` encoding.
- **Resolution**: Injected `chcp 65001`, `PYTHONIOENCODING=utf-8`, and `PYTHONUTF8=1` into `start_pravision.bat` and subprocess execution wrappers.

### 5. False Health Reporting & Simulated Connectors
- **Finding**: Approximately 16 connectors originally returned static empty arrays `[]` while claiming `ConnectorHealthStatus.OPERATIONAL`.
- **Resolution**: Introduced truthful health reporting across all 89 connectors. Tools lacking environment API keys report `CONFIG_REQUIRED` or `AUTH_REQUIRED`; tools requiring paid subscriptions report `SUBSCRIPTION_REQUIRED`; tools with restricted surveillance implications report `RESTRICTED`.

---

## SECTION B: TEST EXECUTION RESULTS

PRAVISION was verified using an end-to-end automated test suite comprising 8 test suites, 6 live orchestrator verification runs, and full production asset compilation.

### 1. Test Suite Summary (`pytest backend/tests/test_backend.py`)

| Test Suite | Function Under Test | Status | Duration |
| :--- | :--- | :---: | :---: |
| `test_input_classifier` | Multi-format input regex & mode detection | **PASS** | 0.08s |
| `test_evidence_validation` | Strict format validation (Email, IP, Domain, etc.) | **PASS** | 0.05s |
| `test_deduplicator_and_confidence` | Cross-source deduplication & confidence engine | **PASS** | 0.12s |
| `test_graph_engine` | In-memory graph nodes, edges, and provenance links | **PASS** | 0.09s |
| `test_connector_registry` | 89 connectors verified, GHunt & 24 candidate checks | **PASS** | 3.42s |
| `test_storage_and_cases` | PostgreSQL/SQLite WAL CRUD, Case dossiers, B2 Vault SHA-256 | **PASS** | 2.15s |
| `test_intelligence_capabilities` | NetworkX centrality, Entity resolution, Timeline, Threat intel, AI | **PASS** | 4.81s |
| `test_privacy_controller` | PII regex sanitization, log secret masking, memory wipes | **PASS** | 0.06s |
| **Total** | **8 Test Suites (Full Regression Suite)** | **PASS (100%)** | **10.84s** |

### 2. Multi-Mode Live Verification Matrix

| Mode | Target Evaluated | Connectors Executed | Discovered Findings | Verified Relational Links | Execution Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Mode 1: Public Identity** | `johndoe_test` | 13 | 10 | 15 | **COMPLETED** |
| **Mode 3: Email** | `target@gmail.com` | 13 | 5 | 10 | **COMPLETED** |
| **Mode 4: Phone** | `+14155552671` | 6 | 4 | 4 | **COMPLETED** |
| **Mode 5: Website / Domain** | `example.com` | 24 | 17 | 25 | **COMPLETED** |
| **Mode 6: Organization Asset** | `192.168.1.1` | 8 | 3 | 4 | **COMPLETED** |
| **Mode 7: Global Situational** | `48.8584, 2.2945` | 8 | 13 | 13 | **COMPLETED** |

### 3. Frontend Production Build Verification
- **Command**: `npm.cmd --prefix frontend run build`
- **Output**: `tsc -b && vite build` completed in **1.03s** with **0 TypeScript errors**.
- **Bundle Output**:
  - `dist/index.html`: `0.45 kB`
  - `dist/assets/index-DkT5I9CX.css`: `73.68 kB`
  - `dist/assets/index-DPbMwQTN.js`: `534.04 kB`

---

## SECTION C: 24 CANDIDATE TOOL INTEGRATION ASSESSMENT

All 24 candidate tools evaluated in Phase 2 have been codified into typed abstract connectors in `backend/app/connectors/candidates/candidate_connectors.py` and registered in `backend/app/connectors/registry.py`.

```
Total Registered Connectors: 89
Operational: 63 | Config Required: 7 | Auth Required: 7 | Subscription Required: 6 | Restricted: 5 | Partial: 1
```

| # | Tool Identifier | Category | Truthful Status | Execution Implementation |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `whatsmyname` | Username / Social | **OPERATIONAL** | Probes public profiles across 400+ online communities and platforms |
| 2 | `blackbird` | Username / Social | **OPERATIONAL** | Rapid developer and tech account probe (PyPI, npm, Kaggle, Pastebin, Replit) |
| 3 | `holehe` | Email Intelligence | **OPERATIONAL** | Probes password-recovery endpoints to verify account existence without auth |
| 4 | `urlscan` | Website / Infra | **OPERATIONAL** | Public search across urlscan.io global scan repository and screenshots |
| 5 | `crtsh` | Website / Infra | **OPERATIONAL** | Queries crt.sh Certificate Transparency logs for real subdomains and SSL certs |
| 6 | `securitytrails` | Website / Infra | **CONFIG_REQUIRED** | Historical DNS and WHOIS search. Requires `SECURITYTRAILS_API_KEY` |
| 7 | `greynoise` | Advanced Platforms | **OPERATIONAL** | GreyNoise Community API checks for internet scanner activity and bot actors |
| 8 | `abuseipdb` | Advanced Platforms | **CONFIG_REQUIRED** | IP reputation checking and abuse confidence score. Requires `ABUSEIPDB_API_KEY` |
| 9 | `misp` | Advanced Platforms | **CONFIG_REQUIRED** | MISP threat sharing query. Requires `MISP_URL` and `MISP_API_KEY` |
| 10 | `yeti` | Advanced Platforms | **CONFIG_REQUIRED** | Yeti threat observables query. Requires `YETI_URL` and `YETI_API_KEY` |
| 11 | `opencti` | Advanced Platforms | **CONFIG_REQUIRED** | OpenCTI GraphQL STIX 2.1 correlation. Requires `OPENCTI_URL` and `OPENCTI_TOKEN` |
| 12 | `opensanctions` | Global Situational | **OPERATIONAL** | Searches international sanctions, PEPs, and debarred entity watchlists |
| 13 | `graphistry` | Advanced Platforms | **CONFIG_REQUIRED** | GPU-accelerated cloud graph clustering. Requires `GRAPHISTRY_KEY` |
| 14 | `networkx` | Advanced Platforms | **OPERATIONAL** | In-process topological analytics: Degree/Betweenness Centrality & PageRank |
| 15 | `gephi` | Advanced Platforms | **OPERATIONAL** | Serializes graph into standard Gephi GEXF format for external visual exploration |
| 16 | `apache_tika` | Advanced Platforms | **PARTIAL** | Document text and metadata extraction with Python native fallback |
| 17 | `qgis` | Geographic | **OPERATIONAL** | Generates valid GeoJSON feature layers for spatial GIS applications |
| 18 | `openstreetmap_overpass`| Geographic | **OPERATIONAL** | Queries Overpass API for amenities, buildings, and physical infrastructure |
| 19 | `gdelt` | Global Situational | **OPERATIONAL** | GDELT 2.0 Doc API monitoring global news across 100+ languages |
| 20 | `openaleph` | Global Situational | **OPERATIONAL** | OCCRP Aleph investigative database search for leaks and offshore records |
| 21 | `followthemoney` | Global Situational | **OPERATIONAL** | FollowTheMoney schema entity mapper for corporate and banking nodes |
| 22 | `datasette` | Advanced Platforms | **OPERATIONAL** | Exports findings and relational nodes into SQLite databases for Datasette |
| 23 | `intelowl` | Advanced Platforms | **CONFIG_REQUIRED** | IntelOwl threat intelligence orchestrator. Requires `INTELOWL_URL` and key |
| 24 | `openosint` | Advanced Platforms | **OPERATIONAL** | Aggregates threat intelligence feeds and queries URLhaus for malware payloads |

---

## SECTION D: STORAGE ARCHITECTURE (POSTGRESQL + BACKBLAZE B2)

PRAVISION implements a production-grade dual storage architecture designed for both completely offline zero-config local operation and enterprise cloud deployments:

```
                           +--------------------------------------+
                           |       STORAGE MANAGER FACTORY        |
                           +--------------------------------------+
                                              |
                   +--------------------------+--------------------------+
                   |                                                     |
                   v                                                     v
+------------------------------------+                +------------------------------------+
|       RELATIONAL PERSISTENCE       |                |           OBJECT STORAGE           |
|                                    |                |                                    |
| [PostgreSQL Mode]                  |                | [Backblaze B2 Mode]                |
| - Target: POSTGRES_URL             |                | - B2 S3-Compatible API             |
| - Driver: asyncpg (AsyncEngine)    |                | - Bucket: B2_BUCKET_NAME           |
| - Full relational ACID schema      |                | - Immutable SHA-256 Hashing        |
|                                    |                |                                    |
| [SQLite WAL Mode (Default)]        |                | [Local Vault Fallback (Default)]   |
| - Target: pravision_local.db       |                | - Path: temp_runtime/evidence_vault|
| - Driver: aiosqlite (WAL mode)     |                | - Exact byte-level SHA-256 custody |
| - Zero configuration required      |                | - Automatic file integrity check   |
+------------------------------------+                +------------------------------------+
```

### 1. Database Schema (`backend/app/storage/models_db.py`)
- **`cases`**: Unique `case_number`, `title`, `description`, `created_by`, `status` (`active`, `closed`, `archived`), `classification` (`UNCLASSIFIED`, `RESTRICTED`, `CONFIDENTIAL`, `SECRET`), `tags` (JSON), `created_at`, `updated_at`.
- **`investigations`**: Tied to cases via foreign key (`case_id`). Stores `root_input`, `root_type`, `mode`, `status`, `total_findings`, `verified_relationships`, `completed_at`.
- **`entities`**: Normalized identifiers, entity types, confidence ratings, match types, timestamps, and unstructured properties (JSON).
- **`relationships`**: Directed topological edges connecting source and target entity IDs with confidence, relationship type, and properties.
- **`evidences`**: Chain of custody records storing raw collector output, source URL, file size, MIME type, `storage_backend` (`b2_cloud`, `local_vault`), and SHA-256 cryptographic checksum.
- **`audit_logs`**: Immutable audit logs capturing every user action, timestamp, client IP, target ID, and operation parameters.

### 2. Backblaze B2 S3 Service (`backend/app/storage/b2_storage.py`)
- **Client**: AWS S3 compatible client powered by `boto3`.
- **Cryptographic Chain of Custody**: Computes SHA-256 before upload and validates hash on download.
- **Automatic Fallback**: If `B2_APPLICATION_KEY_ID` is not set, stores evidence in local secure vault `backend/app/temp_runtime/evidence_vault/` with identical SHA-256 validation.

---

## SECTION E: INTELLIGENCE ENGINE CAPABILITIES

PRAVISION's backend intelligence engine (`backend/app/intelligence/`) provides deep, algorithmic analysis over raw collector findings:

### 1. Entity Resolution & Contradiction Detection (`entity_resolution.py`)
- Computes pairwise Jaro-Winkler lexical similarity over normalized strings.
- Performs structural cross-type heuristics (matching email prefixes against usernames, subdomain hierarchies against root domains).
- Flags contradictions (e.g. conflicting geolocations or conflicting registration timestamps across profiles).

### 2. NetworkX Graph Analytics (`graph_analytics.py`)
- Ingests relational intelligence nodes and edges into NetworkX graphs.
- **Degree Centrality**: Identifies highest-connected hubs in the target network.
- **Betweenness Centrality**: Pinpoints gatekeepers and critical bridges connecting disparate clusters.
- **PageRank**: Computes structural authority scores across all entities.
- **Community Detection**: Partitions the intelligence network into discrete communities using greedy modularity.
- **Shortest Path**: Traces the shortest hop connection chain between any two targets or organizations.
- **Gephi Export**: Exports valid GEXF XML formatted data for high-dimensional Gephi layout rendering.

### 3. Chronological Timeline Analysis (`timeline_engine.py`)
- Normalizes disparate timestamps (certificate start dates, WHOIS creation, DNS observation, capture times).
- Detects concentrated temporal activity bursts (e.g., 4+ infrastructure changes within a 24-hour window).

### 4. Threat Intelligence Scoring (`threat_intel.py`)
- Aggregates indicator risk telemetry from GreyNoise, AbuseIPDB, URLhaus, and OpenSanctions.
- Produces a normalized Risk Score (0 to 100) and Threat Severity (`CRITICAL`, `HIGH`, `MODERATE`, `LOW`, `BENIGN`).
- Attributed threat actor profiles and malicious payload associations.

### 5. Document Intelligence (`document_intel.py`)
- Scans raw text and document corpora (PDF, DOCX, TXT) for observable OSINT entities.
- Employs strict regular expressions for IPv4 addresses, domains, emails, cryptocurrency addresses (BTC, ETH), and CVE vulnerability identifiers.

### 6. Grounded AI Analytical Copilot (`ai_assistant.py`)
- Grounded strictly in collected evidence with zero external hallucinations.
- **Executive Briefing**: Produces automated intelligence assessments including Executive Summary, Key Metrics, Identified Intelligence Gaps, Formulated Hypotheses, and Actionable Recommended Next Steps.
- **Interactive QA**: Answers analyst questions by querying evidence cards and returning matching entities.

---

## SECTION F: GOTHAM-INSPIRED WORKSPACE DOCUMENTATION

The PRAVISION frontend workstation (`frontend/src/`) delivers a high-density, dark-mode analytical interface inspired by Palantir Gotham:

```
+----------------------------------------------------------------------------------------------------+
|  PRAVISION // GOTHAM INTELLIGENCE WORKSTATION                        [Target: johndoe] [89 Tools]  |
+----------------------------------------------------------------------------------------------------+
| [Command Center]     | MISSION CONTROL // OPERATIONAL OVERVIEW                                     |
| [Universal Intake]   | --------------------------------------------------------------------------- |
| [Live Stream]        | [State: Active]  [Findings: 17]  [Graph: 18 Nodes / 25 Edges]  [Risk: Low]  |
| [Case Dossiers]      | --------------------------------------------------------------------------- |
|                      | ANALYTICAL WORKSPACES:                                                      |
| [Gotham Link Graph]  | - Gotham Relational Graph (NetworkX centrality, PageRank, shortest path)   |
| [Global Map]         | - Global Tactical Map (AIS, OpenSky, USGS, FIRMS)                           |
| [Timeline Analysis]  | - Chronological Timeline (Event sequencing, burst detection)                |
| [Threat Intel & IOCs]| - Threat Intelligence & IOCs (GreyNoise, AbuseIPDB, Sanctions)              |
| [Entity Database]    | - Structured Entity Database (Cross-case registry, confidence ratings)      |
| [Evidence Center]    | - Evidence Vault & Chain of Custody (Backblaze B2, SHA-256 checksums)      |
| [AI Copilot]         | - AI Analytical Copilot (Briefings, hypotheses, grounded QA)                |
|                      |                                                                             |
| [Tool Center (89)]   | CONNECTOR REGISTRY:                                                         |
| [Reports & Export]   | 89 Connectors // Truthful status reporting // Pre-flight health checks     |
| [System Admin]       |                                                                             |
+----------------------------------------------------------------------------------------------------+
```

### 1. Command Center (`CommandCenterView.tsx`)
- Mission control overview with live status gauges, active investigation metrics, and direct analytical workspace launch pads.

### 2. Case Dossiers (`CasesView.tsx`)
- Structured case management supporting persistent investigations, classification markings (`UNCLASSIFIED`, `RESTRICTED`, `CONFIDENTIAL`, `SECRET`), analyst assignment, and "Save Active Inv" persistence.

### 3. Gotham Relational Graph (`GothamGraphView.tsx`)
- Network topology visualization with dynamic degree centrality filtering, community cluster coloring, node inspection drawer with raw evidence cards, shortest-path calculation between nodes, and Gephi GEXF export.

### 4. Global Tactical Map (`GlobalMapView.tsx`)
- Geospatial mapping layer integrating live aircraft (OpenSky Network), maritime vessels (AIS), earthquakes (USGS), thermal fires (NASA FIRMS), and coordinate landmark radius markers.

### 5. Chronological Timeline (`TimelineView.tsx`)
- Interactive vertical timeline showing event progression, burst detection warning alerts, and expandable raw metadata cards.

### 6. Threat Intelligence & IOC Posture (`ThreatIntelView.tsx`)
- Threat dashboard displaying aggregate risk score gauge (0-100), severity badge, identified indicators, and international sanctions watchlist screening.

### 7. Structured Entity Database (`EntityDatabaseView.tsx`)
- Searchable and filterable tabular directory of all discovered entities, corroborating sources, confidence ratings, and one-click copy actions.

### 8. Evidence Center & Chain of Custody (`EvidenceCenterView.tsx`)
- Storage infrastructure telemetry (PostgreSQL vs SQLite WAL latency, B2 Cloud vs Local Vault file volume), SHA-256 checksum badges, and file upload to vault.

### 9. AI Intelligence Copilot (`AiAssistantView.tsx`)
- Automated one-click Executive Intelligence Assessment generation, formulated hypotheses with confidence levels, intelligence gap identification, and interactive grounded QA bar.

### 10. Tool Center & Connector Matrix (`ToolCenterView.tsx`)
- Capability matrix for all 89 tools with category tabs, truthful health filters (`operational`, `config_required`, `auth_required`, `subscription_required`, `restricted`, `partial`), and live health check execution.

---

## SECTION G: DEPLOYMENT, CONFIGURATION & OPERATIONS GUIDE

### 1. Windows Local Launch
Double-click `start_pravision.bat` in the project root:
```cmd
start_pravision.bat
```
This batch script:
- Enforces UTF-8 console output (`chcp 65001`, `PYTHONIOENCODING=utf-8`, `PYTHONUTF8=1`).
- Verifies Python virtual environment dependencies in `venv`.
- Launches FastAPI on `127.0.0.1:8000`.
- Automatically opens the default browser at `http://127.0.0.1:8000`.

### 2. Environment Variables Configuration (`.env` or System Environment)

| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `POSTGRES_URL` | *(None — SQLite WAL used)* | PostgreSQL connection string (`postgresql+asyncpg://user:pass@host:5432/db`) |
| `B2_APPLICATION_KEY_ID` | *(None — Local Vault used)* | Backblaze B2 Application Key ID for cloud object storage |
| `B2_APPLICATION_KEY` | *(None — Local Vault used)* | Backblaze B2 Application Secret Key |
| `B2_BUCKET_NAME` | `pravision-evidence-vault` | Backblaze B2 bucket identifier |
| `B2_ENDPOINT_URL` | `https://s3.us-west-004.backblazeb2.com` | Backblaze B2 S3-compatible API endpoint |
| `URLSCAN_API_KEY` | *(Optional)* | Private scan submission for URLScan.io |
| `SECURITYTRAILS_API_KEY`| *(Optional)* | Historical DNS and WHOIS queries |
| `GREYNOISE_API_KEY` | *(Optional)* | Enterprise scanner intelligence (Community API works without key) |
| `ABUSEIPDB_API_KEY` | *(Optional)* | IP reputation score checking |
| `MISP_URL` / `MISP_API_KEY`| *(Optional)* | Trusted MISP instance integration |
| `OPENCTI_URL` / `OPENCTI_TOKEN`| *(Optional)* | OpenCTI threat intelligence GraphQL connection |
| `OPENSANCTIONS_API_KEY` | *(Optional)* | High-rate OpenSanctions watchlist API (Free search works without key) |

### 3. Policy-Restricted Boundaries Enforced
- **Biometric Face Search**: PimEyes, FaceCheck.ID, and FaceSift remain permanently restricted in policy compliance.
- **Deceptive Phishing / Geolocation Lures**: Seeker, R-Fone, and Bash Hot remain disabled.
- **Credential Dumps**: Plaintext password harvesting is prohibited; credential exposure checks (HIBP, h8mail) provide frequency counts without dumping passwords.
- **Network Boundaries**: FastAPI binds to `127.0.0.1:8000` exclusively.

---

## CONCLUSION

PRAVISION Phase 2 is fully implemented, verified, and operational. All Phase 1 defects have been corrected, 24 candidate intelligence tools have been codified into an 89-tool capability matrix with truthful health indicators, the PostgreSQL + Backblaze B2 dual-mode storage engine is verified with SHA-256 chain of custody, the NetworkX and analytical intelligence suite is validated across all modes, and the Gotham-inspired workstation interface is compiled and served.
