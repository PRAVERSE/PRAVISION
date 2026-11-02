import asyncio
import os
import sys
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import TEMP_DATA_DIR
from app.evidence.models import EntityType
from app.engine.investigation_orchestrator import orchestrator
from app.connectors.registry import connector_registry

# Helper to create a test image if needed for Mode 2
def create_sample_image(filename="mode2_test.jpg"):
    import piexif
    from PIL import Image
    test_path = TEMP_DATA_DIR / filename
    img = Image.new("RGB", (200, 200), color=(100, 140, 180))
    zeroth_ifd = {
        piexif.ImageIFD.Make: b"Canon",
        piexif.ImageIFD.Model: b"EOS R5",
    }
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N",
        piexif.GPSIFD.GPSLatitude: ((51, 1), (30, 1), (2600, 100)),
        piexif.GPSIFD.GPSLongitudeRef: "W",
        piexif.GPSIFD.GPSLongitude: ((0, 1), (7, 1), (3900, 100))
    }
    exif_bytes = piexif.dump({"0th": zeroth_ifd, "GPS": gps_ifd})
    img.save(test_path, "jpeg", exif=exif_bytes)
    return str(test_path)

MODES_TO_TEST = [
    {
        "mode_id": "mode_1_identity",
        "name": "Mode 1: Public Identity & Username",
        "valid_target": "johndoe_osint",
        "valid_type": EntityType.USERNAME,
        "invalid_target": "@@@###$$$",
        "invalid_type": EntityType.USERNAME,
    },
    {
        "mode_id": "mode_2_media",
        "name": "Mode 2: Media, Image & Visual Evidence",
        "valid_target": None, # created dynamically
        "valid_type": EntityType.IMAGE,
        "invalid_target": "non_existent_image_file_987654.jpg",
        "invalid_type": EntityType.IMAGE,
    },
    {
        "mode_id": "mode_3_email",
        "name": "Mode 3: Email Address Intelligence",
        "valid_target": "investigation.target@example.com",
        "valid_type": EntityType.EMAIL,
        "invalid_target": "invalid-email-format-without-at",
        "invalid_type": EntityType.EMAIL,
    },
    {
        "mode_id": "mode_4_phone",
        "name": "Mode 4: Phone & Telephony Intelligence",
        "valid_target": "+14155552671",
        "valid_type": EntityType.PHONE,
        "invalid_target": "000000",
        "invalid_type": EntityType.PHONE,
    },
    {
        "mode_id": "mode_5_website",
        "name": "Mode 5: Website, Domain & Network Infrastructure",
        "valid_target": "example.com",
        "valid_type": EntityType.DOMAIN,
        "invalid_target": "invalid..domain..example",
        "invalid_type": EntityType.DOMAIN,
    },
    {
        "mode_id": "mode_6_organization",
        "name": "Mode 6: Organization & Corporate Assets",
        "valid_target": "192.168.1.1",
        "valid_type": EntityType.IP_ADDRESS,
        "invalid_target": "999.999.999.999",
        "invalid_type": EntityType.IP_ADDRESS,
    },
    {
        "mode_id": "mode_7_global_situational",
        "name": "Mode 7: Global Situational & Geopolitical Intelligence",
        "valid_target": "48.8584, 2.2945", # Eiffel Tower coordinates
        "valid_type": EntityType.GEO_COORDINATE,
        "invalid_target": "999.999, -999.999",
        "invalid_type": EntityType.GEO_COORDINATE,
    },
]

async def run_mode_tests():
    print("=" * 80)
    print("PRAVISION 7-MODE COMPREHENSIVE INDEPENDENT VERIFICATION")
    print("=" * 80)
    
    results = []

    for test_cfg in MODES_TO_TEST:
        mode_id = test_cfg["mode_id"]
        mode_name = test_cfg["name"]
        print(f"\n[TESTING] {mode_name} ({mode_id})")

        # Set up dynamic targets (e.g. image)
        if mode_id == "mode_2_media":
            valid_target = create_sample_image("mode2_verify_photo.jpg")
        else:
            valid_target = test_cfg["valid_target"]
            
        valid_type = test_cfg["valid_type"]
        invalid_target = test_cfg["invalid_target"]
        invalid_type = test_cfg["invalid_type"]

        # --- Subtest A: Valid Target Execution ---
        print(f"  -> Subtest A: Valid Input ('{valid_target}', type={valid_type.value})")
        inv_valid = orchestrator.start_investigation(
            target_input=valid_target,
            target_type=valid_type,
            mode=mode_id,
            max_depth=1
        )
        
        # Wait for completion or timeout
        timeout = 30
        elapsed = 0.0
        while inv_valid.status in ("initialized", "running") and elapsed < timeout:
            await asyncio.sleep(0.3)
            elapsed += 0.3

        assert inv_valid.status == "completed", f"Mode {mode_id} failed to complete in {timeout}s! status={inv_valid.status}"
        findings_valid = orchestrator.get_findings()
        graph_valid = orchestrator.get_graph()
        
        print(f"     Status: {inv_valid.status} ({elapsed:.1f}s)")
        print(f"     Findings: {len(findings_valid)}")
        print(f"     Graph: {len(graph_valid.nodes)} nodes, {len(graph_valid.edges)} edges")
        print(f"     Connectors Run: {len(inv_valid.connector_statuses)}")
        for conn_name, st in inv_valid.connector_statuses.items():
            print(f"       - {conn_name}: status={st.status}, findings={st.findings_count}, err={st.error_message}")

        # Basic assertions for valid execution
        assert len(inv_valid.connector_statuses) > 0, f"No connectors executed for {mode_id}"
        # Verify confidence and provenance
        for f in findings_valid:
            assert f.confidence in [
                "unverified", "low", "moderate", "high", "independently_corroborated"
            ], f"Invalid confidence {f.confidence} in finding {f.id}"
            assert f.source_name, f"Missing source attribution in finding {f.id}"
            assert f.collection_timestamp is not None, f"Missing timestamp in finding {f.id}"

        # --- Subtest B: Invalid Target Containment ---
        print(f"  -> Subtest B: Invalid Input ('{invalid_target}') - Failure Containment")
        inv_invalid = orchestrator.start_investigation(
            target_input=invalid_target,
            target_type=invalid_type,
            mode=mode_id,
            max_depth=1
        )
        elapsed = 0.0
        while inv_invalid.status in ("initialized", "running") and elapsed < timeout:
            await asyncio.sleep(0.3)
            elapsed += 0.3

        print(f"     Invalid Input Status: {inv_invalid.status} (Handled gracefully without crash)")
        assert inv_invalid.status in ("completed", "failed"), f"Unexpected status {inv_invalid.status}"

        # Clean up sample image if created
        if mode_id == "mode_2_media" and Path(valid_target).exists():
            try:
                Path(valid_target).unlink()
            except Exception:
                pass

        results.append({
            "mode_id": mode_id,
            "mode_name": mode_name,
            "valid_status": inv_valid.status,
            "findings_count": len(findings_valid),
            "graph_nodes": len(graph_valid.nodes),
            "graph_edges": len(graph_valid.edges),
            "connectors_executed": len(inv_valid.connector_statuses),
            "invalid_handling": "PASS (Graceful containment)"
        })

    print("\n" + "=" * 80)
    print("7-MODE INDEPENDENT VERIFICATION SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Mode':<32} | {'Status':<10} | {'Findings':<9} | {'Nodes':<6} | {'Edges':<6} | {'Connectors':<11} | {'Invalid Test'}")
    print("-" * 100)
    for r in results:
        print(f"{r['mode_name']:<32} | {r['valid_status']:<10} | {r['findings_count']:<9} | {r['graph_nodes']:<6} | {r['graph_edges']:<6} | {r['connectors_executed']:<11} | {r['invalid_handling']}")

    print("\nALL 7 MODES VERIFIED WITH ZERO CRASHES AND STRICT INTEGRITY.")

if __name__ == "__main__":
    asyncio.run(run_mode_tests())
