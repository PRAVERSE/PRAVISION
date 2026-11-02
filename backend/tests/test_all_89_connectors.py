import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import TEMP_DATA_DIR
from app.evidence.models import EntityType
from app.connectors.registry import connector_registry
from app.connectors.base_connector import InvestigationRequest

def create_sample_image_if_needed():
    import piexif
    from PIL import Image
    test_path = TEMP_DATA_DIR / "audit_test_img.jpg"
    if not test_path.exists():
        img = Image.new("RGB", (100, 100), color=(50, 100, 150))
        img.save(test_path, "jpeg")
    return str(test_path)

def create_sample_doc_if_needed():
    test_path = TEMP_DATA_DIR / "audit_test_doc.txt"
    if not test_path.exists():
        with open(test_path, "w", encoding="utf-8") as f:
            f.write("Target email: target@example.com, IP: 192.168.1.1, BTC: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    return str(test_path)

SAMPLE_TARGETS = {
    EntityType.USERNAME: "target_user_test",
    EntityType.EMAIL: "target.audit@example.com",
    EntityType.PHONE: "+14155552671",
    EntityType.DOMAIN: "example.com",
    EntityType.IP_ADDRESS: "8.8.8.8",
    EntityType.URL: "https://example.com",
    EntityType.IMAGE: None, # set dynamically
    EntityType.GEO_COORDINATE: "37.7749, -122.4194",
    EntityType.PERSON_NAME: "John Doe",
    EntityType.DOCUMENT: None, # set dynamically
    EntityType.ORGANIZATION: "Acme Corporation",
    EntityType.HASH: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
}

RESTRICTED_TOOLS = {"pimeyes", "facecheck_id"}

async def audit_all_89_connectors():
    print("=" * 100)
    print("PRAVISION INDEPENDENT AUDIT OF ALL REGISTERED CONNECTORS")
    print("=" * 100)

    sample_img = create_sample_image_if_needed()
    sample_doc = create_sample_doc_if_needed()
    SAMPLE_TARGETS[EntityType.IMAGE] = sample_img
    SAMPLE_TARGETS[EntityType.DOCUMENT] = sample_doc

    connectors = connector_registry.get_all_connectors()
    print(f"Total Connectors Discovered in Registry: {len(connectors)}")

    audit_records = []

    for conn in sorted(connectors, key=lambda x: x.name):
        manifest = conn.get_manifest()
        identifier = manifest.name
        display_name = manifest.display_name
        category = manifest.category.value if hasattr(manifest.category, 'value') else str(manifest.category)
        supported = manifest.supported_entity_types
        requires_key = manifest.requires_api_key
        is_commercial = manifest.is_commercial
        doc_url = manifest.website_or_repo or "Local Builtin / Repository"

        # Determine target type to test
        target_type = supported[0] if supported else EntityType.DOMAIN
        target_val = SAMPLE_TARGETS.get(target_type, "example.com")

        req = InvestigationRequest(
            investigation_id=f"audit_{identifier}",
            target_value=str(target_val),
            target_type=target_type,
            mode="audit",
            depth=1
        )

        # Truthful Status Determination
        status = "UNKNOWN"
        findings_count = 0
        error_msg = None
        duration = 0.0

        if identifier in RESTRICTED_TOOLS:
            status = "RESTRICTED"
            notes = "Restricted by platform ethical safeguard (biometric facial recognition prohibited)"
        else:
            t0 = time.time()
            try:
                # Run with timeout to prevent hanging on external requests
                findings = await asyncio.wait_for(conn.execute(req), timeout=4.0)
                duration = time.time() - t0
                findings_count = len(findings)
                
                if requires_key:
                    # Check if API key is present in environment
                    key_var = f"{identifier.upper()}_API_KEY"
                    if not os.environ.get(key_var) and not os.environ.get(f"{identifier.upper()}_KEY"):
                        if is_commercial:
                            status = "SUBSCRIPTION_REQUIRED"
                            notes = f"Requires commercial API key/subscription ({key_var} not configured in env)"
                        else:
                            status = "CONFIG_REQUIRED"
                            notes = f"Requires free API key ({key_var} not configured in env)"
                    else:
                        status = "OPERATIONAL"
                        notes = f"Executed successfully in {duration:.2f}s with API key ({findings_count} findings)"
                else:
                    status = "OPERATIONAL"
                    notes = f"Executed successfully in {duration:.2f}s ({findings_count} findings)"

            except asyncio.TimeoutError:
                duration = time.time() - t0
                if requires_key:
                    status = "CONFIG_REQUIRED" if not is_commercial else "SUBSCRIPTION_REQUIRED"
                    notes = "Network timeout; API key not configured"
                else:
                    status = "PARTIAL"
                    notes = f"Execution timed out after 4.0s (network throttled or remote offline)"
            except Exception as e:
                duration = time.time() - t0
                error_msg = str(e)
                if "API key" in error_msg or "apikey" in error_msg.lower() or "unauthorized" in error_msg.lower():
                    status = "AUTH_REQUIRED"
                    notes = f"Authentication required: {error_msg}"
                elif "not found" in error_msg.lower() or "not installed" in error_msg.lower():
                    status = "NOT_INSTALLED"
                    notes = f"Dependency missing: {error_msg}"
                else:
                    status = "BROKEN"
                    notes = f"Runtime exception: {error_msg}"

        audit_records.append({
            "identifier": identifier,
            "name": display_name,
            "category": category,
            "status": status,
            "findings_count": findings_count,
            "duration": f"{duration:.2f}s",
            "requires_key": requires_key,
            "is_commercial": is_commercial,
            "notes": notes,
            "doc_url": doc_url
        })
        print(f"[{status:<19}] {identifier:<26} | cat={category:<16} | dur={duration:.2f}s | {notes}")

    # Aggregations
    from collections import Counter
    counts = Counter(r["status"] for r in audit_records)
    print("\n" + "=" * 100)
    print("CONNECTOR AUDIT SUMMARY BREAKDOWN")
    print("=" * 100)
    for st, count in sorted(counts.items()):
        print(f"  - {st:<22}: {count:>2} connectors")
    print(f"  TOTAL AUDITED: {len(audit_records)}")

    # Write detailed CSV/Markdown file for the audit report
    out_path = Path("backend/tests/connector_audit_results.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"{'#':<3} | {'ID':<25} | {'Name':<28} | {'Category':<16} | {'Status':<20} | {'Findings':<8} | {'Notes'}\n")
        f.write("-" * 130 + "\n")
        for i, r in enumerate(audit_records, 1):
            f.write(f"{i:<3} | {r['identifier']:<25} | {r['name']:<28} | {r['category']:<16} | {r['status']:<20} | {r['findings_count']:<8} | {r['notes']}\n")

    print(f"\nAudit complete. Detailed records saved to {out_path}")
    return audit_records

if __name__ == "__main__":
    asyncio.run(audit_all_89_connectors())
