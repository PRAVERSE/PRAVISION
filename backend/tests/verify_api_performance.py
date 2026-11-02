import asyncio
import sys
import uuid
import time
import statistics
import httpx
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app

async def run_api_performance_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.3 — API & WORKSTATION RESPONSIVENESS BENCHMARKS")
    print("=" * 80)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as client:
        # Pre-warm app
        warmup = await client.get("/api/settings")
        assert warmup.status_code == 200

        endpoints = [
            ("Root SPA Serving", "GET", "/", None),
            ("Classifier (Email)", "POST", "/api/classify", {"input": "analyst.delta@target.corp"}),
            ("Classifier (IP)", "POST", "/api/classify", {"input": "198.51.100.22"}),
            ("Connector Registry (89 manifests)", "GET", "/api/connectors", None),
            ("Document Intel Scanner", "POST", "/api/intelligence/document/scan", {
                "text": "Officer contact john.doe@agency.mil on IP 10.20.30.40 and BTC 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
            }),
            ("Storage Status Ping", "GET", "/api/storage/status", None),
            ("Entity Resolution Engine", "GET", "/api/intelligence/entity-resolution", None),
            ("Graph Analytics (NetworkX)", "GET", "/api/intelligence/graph-analytics", None),
            ("Timeline Synthesis", "GET", "/api/intelligence/timeline", None),
            ("Contextual Assistant (/api/intelligence/ask)", "POST", "/api/intelligence/ask", {"query": "List key findings"}),
            ("Case Pagination (/api/cases?limit=10&offset=0)", "GET", "/api/cases?limit=10&offset=0", None),
        ]

        print(f"\nBenchmarking {len(endpoints)} Core API Endpoints (3 iterations each):")
        print(f"{'Endpoint':<45} | {'Min (ms)':<10} | {'Avg (ms)':<10} | {'Max (ms)':<10}")
        print("-" * 85)

        for name, method, path, payload in endpoints:
            durations = []
            for _ in range(3):
                t0 = time.perf_counter()
                if method == "GET":
                    res = await client.get(path)
                elif method == "POST":
                    res = await client.post(path, json=payload)
                t1 = time.perf_counter()
                assert res.status_code == 200, f"Endpoint {path} failed with {res.status_code}"
                durations.append((t1 - t0) * 1000)

            min_d = min(durations)
            avg_d = statistics.mean(durations)
            max_d = max(durations)
            print(f"{name:<45} | {min_d:<10.2f} | {avg_d:<10.2f} | {max_d:<10.2f}")

        # Benchmark Full CRUD Lifecycle of a Case Dossier via API
        print("\n" + "-" * 70)
        print("BENCHMARK: Case Dossier Full Lifecycle via API (Create -> Get -> Delete)")
        print("-" * 70)

        # 1. Create Case
        t0_c = time.perf_counter()
        res_create = await client.post("/api/cases", json={
            "title": f"API Perf Case - {uuid.uuid4().hex[:6]}",
            "description": "Benchmark case created via API test",
            "classification": "CONFIDENTIAL",
            "tags": ["api_bench"]
        })
        t1_c = time.perf_counter()
        assert res_create.status_code == 200
        case_id = res_create.json()["id"]
        create_api_ms = (t1_c - t0_c) * 1000
        print(f"  • POST /api/cases (Create):    {create_api_ms:.2f} ms")

        # 2. Get Single Case
        t0_g = time.perf_counter()
        res_get = await client.get(f"/api/cases/{case_id}")
        t1_g = time.perf_counter()
        assert res_get.status_code == 200
        get_api_ms = (t1_g - t0_g) * 1000
        print(f"  • GET /api/cases/{{id}} (Fetch):   {get_api_ms:.2f} ms")

        # 3. Delete Case
        t0_d = time.perf_counter()
        res_del = await client.delete(f"/api/cases/{case_id}")
        t1_d = time.perf_counter()
        assert res_del.status_code == 200
        del_api_ms = (t1_d - t0_d) * 1000
        print(f"  • DELETE /api/cases/{{id}} (Del):  {del_api_ms:.2f} ms")

        total_lifecycle_ms = create_api_ms + get_api_ms + del_api_ms
        print(f"  • Total Full Lifecycle:        {total_lifecycle_ms:.2f} ms")

        print("\n" + "=" * 80)
        print("API RESPONSIVENESS BENCHMARKS COMPLETED SUCCESSFULLY.")
        print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_api_performance_suite())

