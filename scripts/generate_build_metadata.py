"""
PRAVISION — Deployment Build Metadata Generator
Executed during deployment build to stamp the exact checked-out Git commit SHA
and ensure zero discrepancy across environment, build files, and runtime endpoints.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.build_identity import generate_build_metadata, resolve_deployment_identity

def main():
    meta = generate_build_metadata(output_dir=ROOT_DIR / "backend" / "app")
    ident = resolve_deployment_identity()
    print("=" * 70)
    print("PRAVISION BUILD METADATA GENERATED")
    print(f"  Target file:     backend/app/build_metadata.json")
    print(f"  Commit SHA:      {ident.commit_sha}")
    print(f"  Identity Status: {ident.identity_status}")
    print(f"  Sources Agree:   {ident.sources_agree}")
    print(f"  Details:         {ident.details}")
    print("=" * 70)

if __name__ == "__main__":
    main()

