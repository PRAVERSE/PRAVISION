import asyncio
from app.storage.database import init_db, check_db_health
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage

async def main():
    print("Testing init_db()...")
    await init_db()
    
    health = await check_db_health()
    print("Database Health Check:", health)

    # Test B2 / Local storage status
    status = b2_storage.get_status()
    print("Storage Status:", status)

    # Test Case creation and listing
    print("Creating test case...")
    c = await case_manager.create_case(
        title="Operation Vanguard",
        description="Test case verification for Gotham platform",
        created_by="Lead Analyst",
        classification="RESTRICTED",
        tags=["threat_intel", "test"]
    )
    print("Created Case:", c)

    cases = await case_manager.list_cases()
    print(f"Total Cases in DB: {len(cases)}")
    assert len(cases) >= 1

    # Test B2 / Local vault file upload and SHA-256 integrity verification
    test_data = b"PRAVISION FORENSIC EVIDENCE ARTIFACT VERIFICATION"
    upload_res = await b2_storage.upload_evidence(test_data, "forensic_log.txt", "text/plain")
    print("Upload Result:", upload_res)

    download_bytes, downloaded_hash = await b2_storage.download_evidence(upload_res["file_key"])
    assert downloaded_hash == upload_res["file_hash"]
    assert download_bytes == test_data
    print("Downloaded and verified SHA-256 integrity:", downloaded_hash)

    # Clean up test case
    await case_manager.delete_case(c["id"])
    print("Deleted test case. Verified complete CRUD and storage lifecycle.")

if __name__ == "__main__":
    asyncio.run(main())

