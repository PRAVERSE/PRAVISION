"""
PRAVISION — Build & Deployment Identity Module
Provides reliable, validated Git commit SHA metadata for active deployments.
Prevents identity drift, detects cross-source mismatches (e.g. parent SHA vs current git HEAD),
and ensures consistent verification across /api/version and /api/settings.
"""

import os
import re
import json
import subprocess
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

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


@dataclass
class DeploymentIdentity:
    commit_sha: str
    identity_status: str  # "verified", "mismatch", "unverified", "unavailable"
    sources_agree: bool
    sources: Dict[str, Optional[str]]
    details: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_deployment_identity() -> DeploymentIdentity:
    """
    Cross-verifies all available deployment identity sources:
    1. Environment variables (PRAVISION_COMMIT_SHA, GIT_COMMIT_SHA, COMMIT_SHA, CF_PAGES_COMMIT_SHA)
    2. Build metadata files (build_metadata.json, .commit_sha)
    3. Live Git repository execution (`git rev-parse HEAD`)

    Enforces strict consistency:
    - If two or more available sources disagree (e.g. metadata has parent SHA while Git has HEAD SHA,
      or environment variable differs from build metadata), an explicit 'mismatch' status is exposed
      rather than silently selecting one.
    - If exactly one distinct SHA is present across all available sources, status is 'verified'.
    - If no sources are available, status is 'unavailable' and SHA is 'unknown'.
    """
    sources: Dict[str, Optional[str]] = {
        "environment": None,
        "metadata_file": None,
        "git": None
    }

    # 1. Inspect Environment Variables
    for env_var in ("PRAVISION_COMMIT_SHA", "GIT_COMMIT_SHA", "COMMIT_SHA", "CF_PAGES_COMMIT_SHA"):
        val = validate_commit_sha(os.environ.get(env_var))
        if val:
            sources["environment"] = val
            break

    # 2. Inspect Build Metadata Files
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
                        sources["metadata_file"] = val
                        break
                else:
                    val = validate_commit_sha(content)
                    if val:
                        sources["metadata_file"] = val
                        break
            except Exception:
                pass

    # 3. Inspect Live Git Repository
    try:
        raw = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root_dir),
            timeout=2,
            stderr=subprocess.DEVNULL
        )
        val = validate_commit_sha(raw.decode("utf-8"))
        if val:
            sources["git"] = val
    except Exception:
        pass

    # 4. Cross-Source Consistency Evaluation
    active_sources = {k: v for k, v in sources.items() if v is not None}
    distinct_shas = set(active_sources.values())

    if len(distinct_shas) == 0:
        return DeploymentIdentity(
            commit_sha="unknown",
            identity_status="unavailable",
            sources_agree=False,
            sources=sources,
            details="No authoritative deployment identity sources found (environment, metadata, and git all unavailable)."
        )

    if len(distinct_shas) > 1:
        conflict_desc = ", ".join(f"{k}={v[:10]}..." for k, v in active_sources.items())
        return DeploymentIdentity(
            commit_sha="mismatch",
            identity_status="mismatch",
            sources_agree=False,
            sources=sources,
            details=f"Authoritative identity source conflict detected: {conflict_desc}. Build metadata does not match deployed runtime commit."
        )

    # Exactly 1 consistent SHA across all active sources
    agreed_sha = next(iter(distinct_shas))
    active_names = ", ".join(active_sources.keys())
    return DeploymentIdentity(
        commit_sha=agreed_sha,
        identity_status="verified",
        sources_agree=True,
        sources=sources,
        details=f"Deployment identity verified across active source(s): {active_names}."
    )


def get_build_commit_sha() -> str:
    """Convenience getter returning the resolved commit SHA ('unknown' or 40-char SHA or 'mismatch')."""
    return resolve_deployment_identity().commit_sha


def generate_build_metadata(output_dir: Optional[Path] = None, explicit_sha: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a build_metadata.json payload recording the current verified commit SHA.
    Typically called during the deployment build phase directly from the checked-out commit.
    """
    from datetime import datetime, timezone

    if explicit_sha:
        sha = validate_commit_sha(explicit_sha) or "unknown"
    else:
        # Determine from Git or environment directly to avoid relying on stale files
        current_dir = Path(__file__).resolve().parent
        root_dir = current_dir.parent.parent
        sha = None
        for env_var in ("PRAVISION_COMMIT_SHA", "GIT_COMMIT_SHA", "COMMIT_SHA", "CF_PAGES_COMMIT_SHA"):
            val = validate_commit_sha(os.environ.get(env_var))
            if val:
                sha = val
                break
        if not sha:
            try:
                raw = subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(root_dir),
                    timeout=2,
                    stderr=subprocess.DEVNULL
                )
                sha = validate_commit_sha(raw.decode("utf-8"))
            except Exception:
                pass
        sha = sha or "unknown"

    meta = {
        "commit_sha": sha,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "build_status": "verified" if sha != "unknown" else "unverified"
    }

    target_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parent
    out_path = target_dir / "build_metadata.json"
    out_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta
