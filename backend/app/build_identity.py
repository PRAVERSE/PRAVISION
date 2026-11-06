"""
PRAVISION — Build & Deployment Identity Module
Provides reliable, validated Git commit SHA metadata for active deployments.
Never falls back to hardcoded, stale commit hashes.
"""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

HEX_40_REGEX = re.compile(r'^[0-9a-fA-F]{40}$')


def validate_commit_sha(sha: Optional[str]) -> Optional[str]:
    """
    Validates that a string is a strict 40-character hexadecimal Git commit SHA.
    Returns the lowercased 40-character string if valid, or None if invalid.
    """
    if not sha or not isinstance(sha, str):
        return None
    cleaned = sha.strip().lower()
    if HEX_40_REGEX.match(cleaned):
        return cleaned
    return None


def get_build_commit_sha() -> str:
    """
    Resolves the authoritative Git commit SHA for the deployed backend:
    1. Environment variables (PRAVISION_COMMIT_SHA, GIT_COMMIT_SHA, COMMIT_SHA)
    2. Build metadata files (backend/app/build_metadata.json, build_metadata.json, .commit_sha)
    3. Live Git execution (`git rev-parse HEAD`)
    4. If unavailable, returns 'unknown' (never a stale hardcoded SHA).
    """
    # 1. Environment variables
    for env_var in ("PRAVISION_COMMIT_SHA", "GIT_COMMIT_SHA", "COMMIT_SHA", "CF_PAGES_COMMIT_SHA"):
        val = validate_commit_sha(os.environ.get(env_var))
        if val:
            return val

    # 2. Build metadata files
    current_dir = Path(__file__).resolve().parent
    root_dir = current_dir.parent.parent
    metadata_candidates = [
        current_dir / "build_metadata.json",
        root_dir / "build_metadata.json",
        current_dir / ".commit_sha",
        root_dir / ".commit_sha"
    ]

    for path in metadata_candidates:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                if content.startswith("{"):
                    data = json.loads(content)
                    val = validate_commit_sha(data.get("commit_sha") or data.get("commit"))
                    if val:
                        return val
                else:
                    val = validate_commit_sha(content)
                    if val:
                        return val
            except Exception:
                pass

    # 3. Live Git repository execution
    try:
        raw = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root_dir),
            timeout=2,
            stderr=subprocess.DEVNULL
        )
        val = validate_commit_sha(raw.decode("utf-8"))
        if val:
            return val
    except Exception:
        pass

    # 4. Explicit fallback: strictly 'unknown'
    return "unknown"


def generate_build_metadata(output_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Generates a build_metadata.json payload recording current verified commit SHA."""
    sha = get_build_commit_sha()
    from datetime import datetime, timezone
    meta = {
        "commit_sha": sha,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "build_status": "verified" if sha != "unknown" else "unverified"
    }
    if output_dir:
        out_path = Path(output_dir) / "build_metadata.json"
        out_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
