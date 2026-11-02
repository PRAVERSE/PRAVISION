import asyncio
import os
import sys
import uuid
import time
import hashlib
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.b2_storage import b2_storage

async def run_storage_performance_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.3 — OBJECT STORAGE PERFORMANCE AUDIT (NEON S3)")
    print("=" * 80)

    status = b2_storage.get_status()
    print("Storage Engine Status:", status["storage_mode"], f"Bucket: {status['bucket']}")
    assert status["cloud_enabled"] is True

    test_sizes = [
        ("1 KB", 1024),
        ("100 KB", 100 * 1024),
        ("1 MB", 1024 * 1024),
        ("5 MB", 5 * 1024 * 1024),
        ("10 MB", 10 * 1024 * 1024)
    ]

    results = []
    inv_bench_id = f"inv_stor_{uuid.uuid4().hex[:8]}"

    for label, size_bytes in test_sizes:
        print("\n" + "-" * 70)
        print(f"BENCHMARK: {label} ({size_bytes:,} bytes)")
        print("-" * 70)

        # Generate test data
        payload = os.urandom(size_bytes)
        source_sha = hashlib.sha256(payload).hexdigest()
        filename = f"bench_{size_bytes}.raw"

        # 1. Upload
        t0_up = time.perf_counter()
        up_res = await b2_storage.upload_evidence(
            data=payload,
            filename=filename,
            content_type="application/octet-stream",
            investigation_id=inv_bench_id
        )
        t1_up = time.perf_counter()
        up_sec = t1_up - t0_up
        up_mb = size_bytes / (1024 * 1024)
        up_speed_mb_s = up_mb / up_sec if up_sec > 0 else 0
        file_key = up_res["file_key"]
        print(f"  • Upload Duration:   {up_sec:.2f} s ({up_speed_mb_s:.3f} MB/s)")
        assert up_res["file_hash"] == source_sha

        # 2. Download
        t0_dl = time.perf_counter()
        dl_data, dl_sha = await b2_storage.download_evidence(file_key)
        t1_dl = time.perf_counter()
        dl_sec = t1_dl - t0_dl
        dl_speed_mb_s = up_mb / dl_sec if dl_sec > 0 else 0
        print(f"  • Download Duration: {dl_sec:.2f} s ({dl_speed_mb_s:.3f} MB/s)")
        assert dl_sha == source_sha
        assert len(dl_data) == size_bytes
        print(f"  • Integrity Check:   SHA-256 verified bit-for-bit.")

        # 3. Cleanup
        await b2_storage.delete_evidence(file_key)
        print(f"  • Cleaned up S3 key: {file_key}")

        results.append({
            "size_label": label,
            "size_bytes": size_bytes,
            "upload_sec": up_sec,
            "upload_mb_s": up_speed_mb_s,
            "download_sec": dl_sec,
            "download_mb_s": dl_speed_mb_s,
            "sha256_match": dl_sha == source_sha
        })

    # 4. Concurrent Upload Throughput (4 parallel 500KB files)
    print("\n" + "-" * 70)
    print("CONCURRENT UPLOAD THROUGHPUT (4 x 500 KB = 2.0 MB Total)")
    print("-" * 70)

    chunk_500kb = os.urandom(500 * 1024)
    async def upload_task(idx: int):
        t0 = time.perf_counter()
        res = await b2_storage.upload_evidence(
            data=chunk_500kb,
            filename=f"conc_chunk_{idx}.bin",
            content_type="application/octet-stream",
            investigation_id=inv_bench_id
        )
        t1 = time.perf_counter()
        return res["file_key"], (t1 - t0)

    t0_all = time.perf_counter()
    up_tasks = await asyncio.gather(*[upload_task(i) for i in range(4)])
    total_concurrent_sec = time.perf_counter() - t0_all
    concurrent_throughput = 2.0 / total_concurrent_sec

    print(f"Total Concurrent Transfer Time: {total_concurrent_sec:.2f} s")
    print(f"Aggregate Upload Throughput:     {concurrent_throughput:.3f} MB/s")

    for k, _ in up_tasks:
        await b2_storage.delete_evidence(k)
    print("Cleaned up concurrent test objects.")

    print("\n" + "=" * 80)
    print("OBJECT STORAGE PERFORMANCE AUDIT COMPLETED.")
    print("=" * 80)
    return results

if __name__ == "__main__":
    asyncio.run(run_storage_performance_suite())

