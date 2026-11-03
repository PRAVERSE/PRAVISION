# PRAVISION — BACKUP & DISASTER RECOVERY RUNBOOK (PHASE 2.5)

**Platform:** PRAVISION — Universal OSINT & Intelligence Platform  
**Operational Scope:** Data Protection, Encrypted Archives & Disaster Recovery  
**Service Level Targets:** RTO (Recovery Time Objective) < 5 Minutes | RPO (Recovery Point Objective) < 1 Hour  
**Revision:** Phase 2.5 Final Production Runbook  

---

## 1. BACKUP ARCHITECTURE & SCHEDULES

PRAVISION implements a dual-tier backup and archival strategy:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRAVISION DATA REPOSITORIES                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
[ Tier 1: Scheduled Case Backups ]         [ Tier 2: Streaming Archives ]
• Hourly automated scheduler (3600s)       • On-demand multi-GB collections
• AES-256-GCM single/multi-case container  • Chunked streaming tar (64 KB RAM)
• Extension: .pravision_bkp                • Extension: .pravision_archive
• Stored in backend/backups/               • Stored in backend/backups/streaming/
```

### 1.1 Automated Scheduler Operation
- The automated background scheduler runs every **3,600 seconds (1 hour)**.
- It snapshots all modified case dossiers, serializes entity relationship networks, gathers associated cloud/vault evidence files, computes SHA-256 hash chains, and generates a timestamped `.pravision_bkp` archive.
- Verification is automatically performed immediately following creation: if the SHA-256 package checksum or decryption test fails, the backup is marked as corrupted and operator alerts are raised.

---

## 2. STANDARD BACKUP OPERATIONS

### 2.1 Triggering an On-Demand Backup via API
To trigger an immediate backup of all cases:

```bash
curl -X POST http://127.0.0.1:8000/api/backup/run \
  -H "Authorization: Bearer <ADMIN_OR_OFFICER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"scope": "all"}'
```

To backup a single specific case:

```bash
curl -X POST http://127.0.0.1:8000/api/backup/run \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "44071369-2a30-4a7d-ae1b-3a561389f273"}'
```

Response:
```json
{
  "backup_id": "BKP-20261103-142102-efcadb",
  "created_at": "2026-11-03T14:21:06Z",
  "scope": "single_case",
  "total_cases": 1,
  "total_files": 1,
  "size_bytes": 4136,
  "package_sha256": "9fbb784d1d8afd52...",
  "status": "verified"
}
```

### 2.2 Generating a Memory-Bounded Streaming Archive
For multi-gigabyte cases with large forensic media files, use the streaming archive engine:

```bash
curl -X POST http://127.0.0.1:8000/api/archive/create \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"case_id": "44071369-2a30-4a7d-ae1b-3a561389f273"}'
```

Response:
```json
{
  "archive_id": "ARCHIVE_20261103_140619_b1fe4e",
  "file_path": "backend/backups/streaming_archives/ARCHIVE_20261103_140619_b1fe4e.pravision_archive",
  "total_cases": 1,
  "total_evidence_files": 4,
  "chunk_count": 82,
  "encrypted_bytes": 5373952,
  "plaintext_sha256": "3a8c7f..."
}
```

---

## 3. RESTORATION & VERIFICATION PROCEDURES

### 3.1 Step 1: Pre-Flight Integrity Verification (Dry-Run)
Before modifying the live database or overwriting evidence files, execute a dry-run integrity verification:

```bash
curl -X POST http://127.0.0.1:8000/api/archive/restore \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@ARCHIVE_20261103_140619_b1fe4e.pravision_archive" \
  -F "verify_only=true"
```

Expected Response:
```json
{
  "status": "verified",
  "archive_id": "ARCHIVE_20261103_140619_b1fe4e",
  "total_cases": 1,
  "total_files": 4,
  "total_bytes": 5242880
}
```

### 3.2 Step 2: Executing Full Case Restoration
To execute restoration with a case title prefix (e.g. to avoid collisions with existing cases):

```bash
curl -X POST http://127.0.0.1:8000/api/archive/restore \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@ARCHIVE_20261103_140619_b1fe4e.pravision_archive" \
  -F "verify_only=false" \
  -F "prefix=[RESTORED] "
```

Expected Response:
```json
{
  "status": "restored",
  "archive_id": "ARCHIVE_20261103_140619_b1fe4e",
  "cases_restored": 1,
  "files_restored": 4,
  "total_bytes": 5242880
}
```

---

## 4. DISASTER RECOVERY RUNBOOKS

### 4.1 Scenario A: Primary Neon PostgreSQL Failure
**Symptoms:** Database connection errors, `getaddrinfo` failures, or SSL timeout alerts in backend logs.  
**Automated Response:**
1. The backend retry loop makes 3 attempts with 1-second backoff.
2. If Neon remains unreachable, PRAVISION falls back to SQLite WAL mode (`pravision_local.db`).
3. Active investigations continue in memory without crash.

**Manual Operator Recovery:**
1. Check Neon Cloud Console status for the active branch (`production`).
2. If database branch is suspended or scaled to zero, wake compute or restore branch via Neon CLI:
   ```bash
   neon branches list --project-id autumn-rice-92082760
   ```
3. Once compute status returns to `active`, restart the backend service:
   ```bash
   docker restart pravision_app
   ```
4. Verify database health:
   ```bash
   curl http://127.0.0.1:8000/api/storage/status
   ```

### 4.2 Scenario B: Cloud Object Storage (S3) Outage
**Symptoms:** File uploads fail with HTTP 503 or S3 connection timeouts.  
**Automated Response:**
1. `B2StorageService` catches upload failures and switches storage path to the Local Evidence Vault (`data/vault/{investigation_id}/`).
2. Evidence metadata records the local storage URI (`local://...`).
3. SHA-256 integrity hash is recorded in PostgreSQL.

**Operator Remediation:**
1. Once S3 connectivity is restored, run the synchronization script to replicate local evidence files to S3:
   ```bash
   python backend/scripts/sync_vault_to_s3.py
   ```

### 4.3 Scenario C: Complete Host Reconstruction
To rebuild PRAVISION on a brand new workstation or server:

1. Clone git repository and restore environment configurations:
   ```bash
   git clone <REPO_URL>
   cd PRAVISION
   cp .env.example .env
   # Populate DATABASE_URL, S3 credentials, and JWT_SECRET in .env
   ```
2. Build and launch container:
   ```bash
   docker compose up -d --build
   ```
3. Initialize database tables and default multi-user accounts:
   ```bash
   docker compose exec pravision python -c "import asyncio; from app.storage.database import init_db; from app.auth.auth_service import auth_service; asyncio.run(init_db()); asyncio.run(auth_service.seed_default_users())"
   ```
4. Restore latest encrypted backup archive using `curl` as detailed in Section 3.2.
5. Run Playwright verification suite to confirm complete operational readiness:
   ```bash
   npm --prefix frontend test
   ```

