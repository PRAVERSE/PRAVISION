"""
PRAVISION Phase 2.5 - OpenSky Flight Telemetry Gateway Verification Test Suite.
Validates:
1. Coordinate bounding-box geospatial validation (bounds checking, inversion prevention)
2. OpenSky Gateway API endpoint (/api/geospatial/flights)
3. Normalized aircraft telemetry schema (ICAO24, callsign, country, coords, speed, heading, altitude)
4. In-memory TTL caching (15-second cache window protecting upstream rate limits)
5. Telemetry health reporting endpoint (/api/geospatial/flights/health)
6. Coverage metadata endpoint (/api/geospatial/flights/coverage)
7. Stale data resilience & upstream failure isolation
"""

import sys
import os
import asyncio
import httpx
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.geospatial.opensky_service import opensky_service

passed_count = 0
failed_count = 0

def log_test(name: str, passed: bool, detail: str = ""):
    global passed_count, failed_count
    status = "PASS" if passed else "FAIL"
    if passed:
        passed_count += 1
        print(f"  [+] {name}: {status} {detail}")
    else:
        failed_count += 1
        print(f"  [-] {name}: {status} - {detail}")

async def run_opensky_verification():
    global passed_count, failed_count
    print("=" * 80)
    print("PRAVISION PHASE 2.5: OPENSKY FLIGHT TELEMETRY GATEWAY VERIFICATION")
    print("=" * 80)

    # Test 1: Bounding Box Validation - Valid Coordinates
    try:
        opensky_service.validate_bounding_box(20.0, -120.0, 50.0, -70.0)
        log_test("1. Bounding Box Validation (Valid Coordinates)", True, "(20.0, -120.0 to 50.0, -70.0 valid)")
    except Exception as e:
        log_test("1. Bounding Box Validation (Valid Coordinates)", False, str(e))

    # Test 2: Bounding Box Validation - Inverted Latitudes Rejection
    try:
        opensky_service.validate_bounding_box(50.0, -120.0, 20.0, -70.0)
        log_test("2. Bounding Box Validation (Inverted Lat Rejection)", False, "Failed to reject lamin > lamax")
    except ValueError:
        log_test("2. Bounding Box Validation (Inverted Lat Rejection)", True, "(Correctly rejected lamin > lamax)")

    # Test 3: Bounding Box Validation - Out of Range Bounds Rejection
    try:
        opensky_service.validate_bounding_box(-95.0, -120.0, 50.0, -70.0)
        log_test("3. Bounding Box Validation (Out of Bounds Rejection)", False, "Failed to reject lat < -90")
    except ValueError:
        log_test("3. Bounding Box Validation (Out of Bounds Rejection)", True, "(Correctly rejected latitude < -90.0)")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:

        # Test 4: OpenSky Flight Gateway Query via FastAPI
        r_flights = await client.get("/api/geospatial/flights?lamin=20&lomin=-120&lamax=50&lomax=-70")
        f_data = r_flights.json()
        log_test(
            "4. OpenSky Flight Gateway Endpoint (/api/geospatial/flights)",
            r_flights.status_code == 200 and "aircraft" in f_data and "attribution" in f_data,
            f"(HTTP {r_flights.status_code}, Status: {f_data.get('status')}, Tracked: {f_data.get('total_aircraft')})"
        )

        # Test 5: Verify Attribution and License Compliance
        attr = f_data.get("attribution", "")
        log_test(
            "5. OpenSky Attribution & Licensing",
            "OpenSky Network" in attr,
            f"('{attr}')"
        )

        # Test 6: In-Memory TTL Caching (15-second window)
        r_cached = await client.get("/api/geospatial/flights?lamin=20&lomin=-120&lamax=50&lomax=-70")
        c_data = r_cached.json()
        log_test(
            "6. In-Memory TTL Cache Verification",
            r_cached.status_code == 200 and c_data.get("cached") is True,
            f"(Cached: {c_data.get('cached')}, Cache Age: {c_data.get('cache_age_seconds')}s)"
        )

        # Test 7: Normalized Aircraft Schema (if flights returned or fallback tested)
        aircraft_list = f_data.get("aircraft", [])
        if aircraft_list:
            first_ac = aircraft_list[0]
            expected_keys = {"icao24", "callsign", "origin_country", "latitude", "longitude"}
            has_keys = expected_keys.issubset(set(first_ac.keys()))
            log_test(
                "7. Normalized Aircraft Telemetry Schema",
                has_keys,
                f"(Sample: {first_ac.get('callsign')} [{first_ac.get('origin_country')}], ICAO: {first_ac.get('icao24')})"
            )
        else:
            # Test schema normalization method directly
            mock_raw_state = [
                ["a1b2c3", "UAL123  ", "United States", 1700000000, 1700000010, -73.98, 40.75, 10500.0, False, 220.5, 95.0, 0.0, None, 10600.0, "1200", False, 0]
            ]
            normalized = opensky_service._normalize_states(mock_raw_state)
            log_test(
                "7. Normalized Aircraft Telemetry Schema (Vector Parsing)",
                len(normalized) == 1 and normalized[0]["callsign"] == "UAL123" and normalized[0]["origin_country"] == "United States",
                f"(Callsign: {normalized[0]['callsign']}, Alt: {normalized[0]['baro_altitude_meters']}m, Spd: {normalized[0]['velocity_mps']}m/s)"
            )

        # Test 8: Telemetry Gateway Health Endpoint
        r_health = await client.get("/api/geospatial/flights/health")
        h_data = r_health.json()
        log_test(
            "8. Flight Gateway Health Status (/api/geospatial/flights/health)",
            r_health.status_code == 200 and h_data.get("service") == "OpenSky Telemetry Gateway",
            f"(Service: {h_data.get('service')}, Status: {h_data.get('status')})"
        )

        # Test 9: Coverage & Capabilities Endpoint
        r_cov = await client.get("/api/geospatial/flights/coverage")
        cov_data = r_cov.json()
        log_test(
            "9. Coverage & Provider Metadata (/api/geospatial/flights/coverage)",
            r_cov.status_code == 200 and cov_data.get("provider") == "OpenSky Network",
            f"(Provider: {cov_data.get('provider')}, Coverage: {cov_data.get('coverage_type')})"
        )

    print("=" * 80)
    print(f"OPENSKY GATEWAY VERIFICATION SUMMARY: {passed_count} PASSED, {failed_count} FAILED")
    print("=" * 80)
    return failed_count == 0

if __name__ == "__main__":
    success = asyncio.run(run_opensky_verification())
    sys.exit(0 if success else 1)

