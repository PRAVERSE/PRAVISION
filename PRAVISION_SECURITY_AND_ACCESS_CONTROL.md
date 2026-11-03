# PRAVISION — SECURITY ARCHITECTURE & ACCESS CONTROL MANUAL (PHASE 2.5)

**Platform:** PRAVISION — Universal OSINT & Intelligence Platform  
**Document Type:** Security Specification & RBAC Guide  
**Status:** Approved for Production Deployment  
**Revision:** Phase 2.5 Final  

---

## 1. THREAT MODEL & SECURITY PRINCIPLES

PRAVISION is designed to process highly sensitive Open Source Intelligence (OSINT) data, active threat actor indicators, infrastructure footprints, and forensically extracted media. The security architecture enforces four foundational principles:

1. **Least Privilege & Role Segregation:** Access to system configurations, user registries, and case investigations is strictly constrained by role boundaries (`admin`, `case_officer`, `analyst`).
2. **Defensive Cryptography:** Passwords use compute-hardened PBKDF2 iterations; streaming evidence packages use AES-256-GCM authenticated encryption with non-reusable derived nonces; session tokens use HMAC-SHA256 JWTs with unique tracking IDs.
3. **Fail-Closed Case Isolation:** Investigation dossiers are private to their creator by default. Analysts cannot query or discover cases unless explicitly granted access by the case owner or an administrator.
4. **Tamper Evident Auditability:** Every authentication attempt, case creation, membership change, role modification, and archive export produces an immutable audit record linked to the actor's UUID and IP address.

---

## 2. MULTI-USER AUTHENTICATION ARCHITECTURE

### 2.1 Password Hashing & Storage
- **Algorithm:** PBKDF2 (Password-Based Key Derivation Function 2) using HMAC-SHA256.
- **Iteration Count:** **600,000 iterations**, strictly complying with OWASP 2024+ recommendations to resist GPU and ASIC brute-force attacks.
- **Salt Generation:** 16 bytes of cryptographically secure randomness generated via `os.urandom(16)`.
- **Comparison:** Constant-time comparison using `hmac.compare_digest` to prevent timing attacks.
- **Storage Format:** Standard format: `pbkdf2:sha256:600000$<salt_hex>$<hash_hex>`.

### 2.2 Account Lockout Protection
- **Threshold:** **5 consecutive failed login attempts**.
- **Lockout Duration:** **15 minutes** (900 seconds).
- **Behavior:** Once locked, authentication immediately rejects all requests with HTTP 403 Forbidden until the lockout window has elapsed, even if the correct password is submitted.
- **Audit:** All failed attempts and lockout activations generate an audit event with the origin IP address.

### 2.3 JWT Token Issuance & Revocation
- **Specification:** RFC-7519 compliant JSON Web Token.
- **Signing Algorithm:** HMAC-SHA256 (`HS256`) using server-managed 256-bit secret key.
- **Token Claims:**
  - `sub`: User UUID (`id`)
  - `username`: Operator handle
  - `role`: Assigned role (`admin`, `case_officer`, `analyst`)
  - `type`: `access` (60-minute lifetime) or `refresh` (7-day lifetime)
  - `jti`: Unique UUID v4 identifying the specific session token instance
  - `iat`: Epoch timestamp of token generation
  - `exp`: Epoch expiration timestamp
- **Token Revocation (Blacklisting):**
  - Calling `/api/auth/logout` extracts the token's `jti` and registers it in the `revoked_tokens` table.
  - Every subsequent request using that token is instantly rejected with HTTP 401 Unauthorized before executing any route logic.

---

## 3. ROLE-BASED ACCESS CONTROL (RBAC) MATRIX

PRAVISION provisions three distinct user roles:

### 3.1 Role Hierarchy & Permissions

```
                [ Administrator (admin) ]
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
[ Case Officer (case_officer) ]   [ Field Analyst (analyst) ]
```

1. **Administrator (`admin`):**
   - Full global visibility into all cases, investigations, and audit logs.
   - User account lifecycle management: view user directory, activate/suspend user accounts, modify assigned roles.
   - System settings configuration, connector management, and emergency data purge capability.
2. **Case Officer (`case_officer`):**
   - Autonomous creation and leadership of investigations and case dossiers.
   - Full read/write management of owned cases.
   - Authority to grant or revoke case sharing permissions to other officers or analysts.
   - Export and restoration of streaming evidence archives.
   - Restricted from accessing user administration or altering system configurations.
3. **Field Analyst (`analyst`):**
   - Read-only analysis of investigations and cases explicitly shared by a case officer or administrator.
   - Execution of search queries, link graph exploration, and situational map analysis within permitted scope.
   - Restricted from viewing unshared cases (HTTP 403 Forbidden).
   - Restricted from modifying case memberships or promoting user roles.

### 3.2 Granular Case Ownership & Sharing
- Every case created stores an `owner_id` (the creating user's UUID).
- Multi-user collaboration is controlled via the `case_memberships` table:
  - `case_id`: UUID of the target case.
  - `user_id`: UUID of the collaborator.
  - `permission`: `read` (read-only analytical access) or `write` (evidence addition and annotation).
  - `granted_by`: UUID of the officer who authorized access.
  - `granted_at`: Timestamp of permission grant.
- **Authorization Enforcement (`verify_case_access`):**
  - When accessing `/api/cases/{case_id}`, the system validates:
    1. Is the user an `admin`? (Granted)
    2. Is `case.owner_id == user.id`? (Granted)
    3. Does a valid row exist in `case_memberships` matching `user.id` with required permission? (Granted)
    4. Otherwise: **HTTP 403 Forbidden** is raised, and an unauthorized access warning is logged.

---

## 4. STREAMING EVIDENCE ARCHIVE CRYPTOGRAPHY

PRAVISION Phase 2.5 implements streaming chunked AES-256-GCM encryption for multi-gigabyte evidence collections (`.pravision_archive`):

```
+--------------------------------------------------------------------------+
|                      PRAVISION ARCHIVE CONTAINER                         |
+--------------------------------------------------------------------------+
| Magic Header: b"PVARC\x01" (6 Bytes)                                     |
| Base Nonce: 12 Bytes Cryptographic Randomness                            |
| Chunk Size: 4 Bytes Big-Endian Integer (65,536 Bytes = 64 KB)            |
+--------------------------------------------------------------------------+
| CHUNK 0:                                                                 |
|   Index: 0x00000000 (4B) | Ciphertext Len: (4B) | Ciphertext + GCM Tag   |
+--------------------------------------------------------------------------+
| CHUNK 1:                                                                 |
|   Index: 0x00000001 (4B) | Ciphertext Len: (4B) | Ciphertext + GCM Tag   |
+--------------------------------------------------------------------------+
| ...                                                                      |
+--------------------------------------------------------------------------+
| EOF MARKER:                                                              |
|   Index: 0xFFFFFFFF (4B) | Ciphertext Len: 0x00000000 (4B)               |
+--------------------------------------------------------------------------+
```

### 4.1 Nonce Derivation & Nonce-Reuse Prevention
Standard AES-GCM requires that a key and nonce pair is never used more than once. In large files split across thousands of chunks, generating naive random nonces risks birthday collisions. PRAVISION resolves this by deriving a unique deterministic nonce for each chunk:

$$\text{ChunkNonce}_i = \text{HMAC-SHA256}(K, \text{BaseNonce} \parallel i)[0..11]$$

This guarantees that:
- Every chunk uses a provably unique 96-bit nonce.
- Nonce reordering or replay attacks alter the derived nonce and cause immediate authentication tag rejection.
- Chunks cannot be truncated or dropped without failing the sequence counter verification.

### 4.2 Tamper & Path Traversal Protections
- **Bit-Flip Resistance:** Modifying any byte within a chunk's ciphertext triggers a cryptographic tag mismatch in `AESGCM.decrypt()`, aborting extraction before writing files to disk.
- **Path Traversal Guards:** Before extracting any member from the decrypted tarball, PRAVISION checks the filename:
  - If the path begins with `/`, contains `..`, or uses Windows drive letters, extraction is aborted with `Security violation: Path traversal detected`.

---

## 5. AUDIT LOGGING & COMPLIANCE SPECIFICATION

All security-relevant actions are recorded in the relational `audit_logs` table:

```sql
CREATE TABLE audit_logs (
    id VARCHAR(36) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user VARCHAR(64) NOT NULL,
    actor_id VARCHAR(36),
    action VARCHAR(64) NOT NULL,
    target_type VARCHAR(64),
    target_id VARCHAR(64),
    outcome VARCHAR(32) DEFAULT 'success',
    details JSONB,
    ip_address VARCHAR(45)
);
```

### 5.1 Tracked Security Events
- `user_login`: Recorded on successful and failed authentications.
- `user_logout`: Recorded on token revocation.
- `create_case`: Recorded when an officer provisions a case.
- `share_case`: Recorded when access is granted to an analyst.
- `revoke_case_share`: Recorded when access is revoked.
- `set_user_status`: Recorded when an admin activates or disables an account.
- `set_user_role`: Recorded when an admin modifies user privileges.
- `create_streaming_archive`: Recorded on archive export.
- `restore_streaming_archive`: Recorded on archive restoration.

