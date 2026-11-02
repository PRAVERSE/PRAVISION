import os
import piexif
from PIL import Image
from pathlib import Path
from app.config import TEMP_DATA_DIR
from app.media_forensics.metadata_extractor import metadata_extractor, hash_calculator
from app.media_forensics.forensic_analyzer import forensic_analyzer
from app.connectors.media.media_connectors import ExifToolConnector, FotoForensicsConnector
from app.connectors.base_connector import InvestigationRequest
from app.evidence.models import EntityType

def test_media_forensics_pipeline():
    test_img_path = TEMP_DATA_DIR / "sample_test_photo.jpg"
    
    # Generate image with real EXIF and GPS tags
    img = Image.new("RGB", (300, 300), color=(120, 150, 180))
    zeroth_ifd = {
        piexif.ImageIFD.Make: b"Sony",
        piexif.ImageIFD.Model: b"A7R IV",
        piexif.ImageIFD.Software: b"ILCE-7RM4 v1.20"
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: b"2024:05:20 11:22:33"
    }
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N",
        piexif.GPSIFD.GPSLatitude: ((40, 1), (42, 1), (4600, 100)),
        piexif.GPSIFD.GPSLongitudeRef: "W",
        piexif.GPSIFD.GPSLongitude: ((74, 1), (0, 1), (2100, 100))
    }
    exif_bytes = piexif.dump({"0th": zeroth_ifd, "Exif": exif_ifd, "GPS": gps_ifd})
    img.save(test_img_path, "jpeg", exif=exif_bytes)

    # 1. Metadata Extractor Test
    meta = metadata_extractor.extract(str(test_img_path))
    print("Metadata Result:", meta)
    assert meta["has_exif"] is True
    assert meta["camera_make"] == "Sony"
    assert meta["camera_model"] == "A7R IV"
    assert meta["gps_coordinates"] is not None
    assert meta["gps_coordinates"][0] > 40.0
    assert meta["gps_coordinates"][1] < -70.0

    # 2. Hash Calculator Test
    hashes = hash_calculator.calculate(str(test_img_path))
    print("Hashes Result:", hashes)
    assert len(hashes["sha256"]) == 64
    assert len(hashes["md5"]) == 32
    assert len(hashes["phash"]) > 0

    # 3. ELA Analyzer Test
    ela = forensic_analyzer.analyze_ela(str(test_img_path))
    print("ELA Result:", ela)
    assert ela["is_analyzed"] is True
    assert ela["ela_image_filename"] is not None
    assert (TEMP_DATA_DIR / ela["ela_image_filename"]).exists()

    # 4. ExifToolConnector live execution
    req = InvestigationRequest(
        investigation_id="inv_mode2_test",
        target_value=str(test_img_path),
        target_type=EntityType.IMAGE,
        mode="mode_2_media",
        depth=1
    )
    import asyncio
    async def run_connectors():
        exif_conn = ExifToolConnector()
        findings = await exif_conn.execute(req)
        print(f"ExifToolConnector returned {len(findings)} findings:")
        for f in findings:
            print(f"  - [{f.entity_type.value}] {f.entity_value}: {f.evidence_description}")
        assert len(findings) >= 3 # Hash, Camera, and GPS

        foto_conn = FotoForensicsConnector()
        foto_findings = await foto_conn.execute(req)
        print(f"FotoForensicsConnector returned {len(foto_findings)} findings:")
        for f in foto_findings:
            print(f"  - [{f.entity_type.value}] {f.entity_value}: {f.evidence_description}")
        assert len(foto_findings) == 1

        # Now test full orchestrator on Mode 2
        from app.engine.investigation_orchestrator import orchestrator
        inv = orchestrator.start_investigation(
            target_input=str(test_img_path),
            target_type=EntityType.IMAGE,
            mode="mode_2_media",
            max_depth=1
        )
        # Wait for completion
        while inv.status in ("initialized", "running"):
            await asyncio.sleep(0.3)
        
        orch_findings = orchestrator.get_findings()
        orch_graph = orchestrator.get_graph()
        print(f"Orchestrator Mode 2: status={inv.status}, findings={len(orch_findings)}, nodes={len(orch_graph.nodes)}, edges={len(orch_graph.edges)}")
        for name, st in inv.connector_statuses.items():
            print(f"  [{st.status}] {name} -> {st.findings_count} findings, error={st.error_message}")
        for f in orch_findings:
            print(f"    - Finding: [{f.entity_type.value}] {f.entity_value} (from {f.source_name})")
        assert inv.status == "completed"
        assert len(orch_findings) >= 3

    asyncio.run(run_connectors())

    # Clean up test file
    if test_img_path.exists():
        test_img_path.unlink()
    print("Mode 2 (Media) Verification SUCCESSFUL!")

if __name__ == "__main__":
    test_media_forensics_pipeline()
