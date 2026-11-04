"""
Security Scanner for Production Frontend Assets
Inspects HTML, JavaScript chunks, CSS, JSON, and source maps in frontend/dist.
Checks for presence of any credentials from .env, database URLs, API keys, private keys, or passwords.
"""

import os
import sys
import re
from pathlib import Path
from dotenv import dotenv_values

def main():
    root = Path(__file__).resolve().parent.parent.parent
    env_file = root / ".env"
    env = dotenv_values(env_file)
    dist_dir = root / "frontend" / "dist"

    print("=" * 78)
    print("PRAVISION PRODUCTION FRONTEND SECRET AUDIT & SCANNER")
    print(f"Scanning target: {dist_dir}")
    print("=" * 78)

    if not dist_dir.exists():
        print(f"[FAIL] Dist directory {dist_dir} does not exist.")
        sys.exit(1)

    # Secrets extracted from .env to verify ABSENCE in frontend bundles
    sensitive_targets = {
        "DATABASE_URL": env.get("DATABASE_URL"),
        "DATABASE_URL_UNPOOLED": env.get("DATABASE_URL_UNPOOLED"),
        "AWS_SECRET_ACCESS_KEY": env.get("AWS_SECRET_ACCESS_KEY"),
        "AWS_ACCESS_KEY_ID": env.get("AWS_ACCESS_KEY_ID"),
        "password": env.get("password") or env.get("PRAVISION_AUTH_PASSWORD"),
        "username": env.get("username") or env.get("PRAVISION_AUTH_USERNAME"),
        "JWT_SECRET": env.get("JWT_SECRET") or env.get("PRAVISION_JWT_SECRET"),
    }

    generic_regexes = [
        ("PostgreSQL URI", re.compile(r"postgres(ql)?://[^\s\"\'\`,]+:[^\s\"\'\`,]+@", re.IGNORECASE)),
        ("AWS Key Pattern", re.compile(r"(AKIA|ASIA)[0-9A-Z]{16}")),
        ("Private Key Block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
        ("Hardcoded Password Field", re.compile(r"password\s*[:=]\s*[\"'][^\"']{8,}[\"']", re.IGNORECASE)),
    ]

    files = [f for f in dist_dir.rglob("*") if f.is_file()]
    print(f"Total production files to inspect: {len(files)}")

    findings = []

    for f in files:
        # Check source map files
        if f.suffix == ".map":
            findings.append((f.name, "Public Source Map File Exposed"))

        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            continue

        # 1. Exact string search for configured secrets
        for secret_name, secret_val in sensitive_targets.items():
            if secret_val and len(str(secret_val).strip()) >= 5:
                clean_val = str(secret_val).strip()
                if clean_val in content:
                    findings.append((f.name, f"Configured Secret Leakage: {secret_name}"))

        # 2. Generic regex search
        for pattern_name, regex in generic_regexes:
            match = regex.search(content)
            if match:
                # Discard false positives like CSS or UI placeholders
                matched_text = match.group(0)
                if "placeholder" not in matched_text.lower() and "password" != matched_text:
                    findings.append((f.name, f"Regex Pattern Match: {pattern_name}"))

    print("-" * 78)
    if not findings:
        print("  [AUDIT PASS] ZERO secrets, credentials, database URIs, or passwords found in frontend/dist.")
        print("  [AUDIT PASS] All production JavaScript, CSS, and HTML assets are free of confidential data.")
    else:
        print(f"  [AUDIT FAIL] Found {len(findings)} potential security findings:")
        for fname, desc in findings:
            print(f"    - {fname}: {desc}")

    print("=" * 78)
    if findings:
        sys.exit(1)

if __name__ == "__main__":
    main()
