import asyncio
import os
import sys
import uuid
import time
import hashlib
import statistics
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db, async_session_maker
from app.storage.b2_storage import b2_storage
from app.storage.case_manager import case_manager
from sqlalchemy import text

async def run_performance_benchmarks():
    print("=" * 80)
    print("PRAVISION PHASE 2.2 — NEON CLOUD PERFORMANCE & LATENCY BENCHMARKS")
    print("=" * 80)

    await init_db()

    # 1. 35 Repeated Database Operations
    print("\n" + "-" * 70)
    print("BENCHMARK 5.1: 35 Repeated Database Operations (Neon Lakebase Postgres)")
    print("-" * 70)

    db_latencies = []
    iterations = 35

    print(f"Executing {iterations} sequential database queries over pooled connection...")
    for i in range(iterations):
        t0 = time.perf_counter()
        async with async_session_maker() as session:
            res = await session.execute(text("SELECT 1;"))
            _ = res.scalar()
        t1 = time.perf_counter()
        db_latencies.append((t1 - t0) * 1000)

    warmup = db_latencies[0]
    eval_latencies = db_latencies[1:]

    avg_lat = statistics.mean(eval_latencies)
    med_lat = statistics.median(eval_latencies)
    sorted_lats = sorted(eval_latencies)
    p95_idx = int(len(sorted_lats) * 0.95)
    p95_lat = sorted_lats[p95_idx]
    min_lat = min(eval_latencies)
    max_lat = max(eval_latencies)
    stdev_lat = statistics.stdev(eval_latencies) if len(eval_latencies) > 1 else 0

    print(f"Neon Postgres Connection Latency Metrics (N={len(eval_latencies)}, Excl. Warmup {warmup:.1f}ms):")
    print(f"  • Min:               {min_lat:.2f} ms")
    print(f"  • Average (Mean):    {avg_lat:.2f} ms")
    print(f"  • Median (p50):      {med_lat:.2f} ms")
    print(f"  • 95th Percentile:   {p95_lat:.2f} ms")
    print(f"  • Maximum:           {max_lat:.2f} ms")
    print(f"  • Std Deviation:     {stdev_lat:.2f} ms")

    # 2. Concurrent Case Operations
    print("\n" + "-" * 70)
    print("BENCHMARK 5.2: Concurrent Database Case Creation (5 Workers)")
    print("-" * 70)

    async def create_bench_case(idx: int):
        t_start = time.perf_counter()
        c = await case_manager.create_case(
            title=f"Concurrent Benchmark Case {idx} - {uuid.uuid4().hex[:4]}",
            description="Testing concurrent connection pool performance",
            created_by="PerfRunner"
        )
        t_end = time.perf_counter()
        return c["id"], (t_end - t_start) * 1000

    t_batch_start = time.perf_counter()
    results = await asyncio.gather(*[create_bench_case(i) for i in range(5)])
    t_batch_end = time.perf_counter()
    total_batch_time = (t_batch_end - t_batch_start) * 1000

    case_ids = [r[0] for r in results]
    op_latencies = [r[1] for r in results]

    print(f"Total concurrent creation time for 5 cases: {total_batch_time:.2f} ms")
    print(f"Average latency per case worker: {statistics.mean(op_latencies):.2f} ms (Min: {min(op_latencies):.2f} ms, Max: {max(op_latencies):.2f} ms)")

    # Clean up benchmark cases
    for cid in case_ids:
        await case_manager.delete_case(cid)
    print("Cleaned up benchmark cases.")

    # 3. Concurrent Object Storage Uploads
    print("\n" + "-" * 70)
    print("BENCHMARK 5.3: Concurrent Evidence Uploads to Neon Object Storage (5 x 256KB)")
    print("-" * 70)

    upload_keys = []
    chunk_256kb = os.urandom(256 * 1024)

    async def upload_worker(idx: int):
        t_start = time.perf_counter()
        res = await b2_storage.upload_evidence(
            data=chunk_256kb,
            filename=f"concurrent_chunk_{idx}.bin",
            content_type="application/octet-stream",
            investigation_id="bench_concurrent"
        )
        t_end = time.perf_counter()
        return res["file_key"], (t_end - t_start) * 1000

    t_up_start = time.perf_counter()
    up_results = await asyncio.gather(*[upload_worker(i) for i in range(5)])
    t_up_end = time.perf_counter()
    total_up_time = (t_up_end - t_up_start) * 1000

    for r in up_results:
        upload_keys.append(r[0])

    print(f"Total time for 5 concurrent 256KB uploads (1.25 MB total): {total_up_time:.2f} ms")
    effective_mb_s = (1.25 / (total_up_time / 1000))
    print(f"Effective Aggregate Upload Throughput: {effective_mb_s:.2f} MB/s")

    # Clean up uploaded concurrent files
    for k in upload_keys:
        await b2_storage.delete_evidence(k)
    print("Cleaned up concurrent test objects.")

    # 4. Large File (5 MB) Upload & Download Benchmark
    print("\n" + "-" * 70)
    print("BENCHMARK 5.4: Large File (5.0 MB) Upload & Download Benchmark")
    print("-" * 70)

    large_size_bytes = 5 * 1024 * 1024  # 5 MB
    print(f"Generating {large_size_bytes / (1024 * 1024):.1f} MB binary payload...")
    large_payload = os.urandom(large_size_bytes)
    large_sha = hashlib.sha256(large_payload).hexdigest()
    print(f"Source SHA-256: {large_sha}")

    # Upload
    t_large_up_start = time.perf_counter()
    large_up_res = await b2_storage.upload_evidence(
        data=large_payload,
        filename="disk_image_dump_5mb.raw",
        content_type="application/octet-stream",
        investigation_id="bench_large"
    )
    t_large_up_end = time.perf_counter()
    large_up_sec = t_large_up_end - t_large_up_start
    large_up_mb_s = (5.0 / large_up_sec)
    print(f"Large File Upload Duration: {large_up_sec:.2f} seconds ({large_up_mb_s:.2f} MB/s)")
    assert large_up_res["file_hash"] == large_sha
    large_key = large_up_res["file_key"]

    # Download
    t_large_dl_start = time.perf_counter()
    dl_data, dl_hash = await b2_storage.download_evidence(large_key)
    t_large_dl_end = time.perf_counter()
    large_dl_sec = t_large_dl_end - t_large_dl_start
    large_dl_mb_s = (5.0 / large_dl_sec)
    print(f"Large File Download Duration: {large_dl_sec:.2f} seconds ({large_dl_mb_s:.2f} MB/s)")
    assert dl_hash == large_sha, "SHA-256 checksum mismatch on large file download!"
    assert len(dl_data) == large_size_bytes
    print(f"Verified bit-for-bit SHA-256 match on 5.0 MB payload.")

    # Cleanup large file
    await b2_storage.delete_evidence(large_key)
    print("Cleaned up large file test object in Neon Object Storage.")

    print("\n" + "=" * 80)
    print("ALL PERFORMANCE BENCHMARKS COMPLETED SUCCESSFULLY.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_performance_benchmarks())

