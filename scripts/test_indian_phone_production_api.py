"""
PRAVISION — Production API Indian Phone Verification Script
Directly queries https://pravision.pages.dev/api/investigate/universal
"""

import sys
import json
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.auth.auth_service import get_env_auth_credentials

PROD_URL = "https://pravision.pages.dev/api"

def run_tests():
    u, p, _ = get_env_auth_credentials()
    assert u and p, "Missing credentials in .env"

    # Authenticate
    login_req = urllib.request.Request(
        f"{PROD_URL}/auth/login",
        data=json.dumps({"username": u, "password": p}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PRAVISION-ProdTest/2.5"}
    )
    with urllib.request.urlopen(login_req, timeout=15) as resp:
        token = json.loads(resp.read().decode("utf-8"))["access_token"]
    print(f"Authenticated successfully as {u}. Acquired JWT token.")

    test_numbers = [
        "+919820012345",
        "919820012345",
        "09820012345",
        "9820012345"
    ]

    print("\n" + "=" * 80)
    print("PRODUCTION API TEST: INDIAN PHONE NUMBER NORMALIZATION")
    print("Endpoint: https://pravision.pages.dev/api/investigate/universal")
    print("=" * 80)

    results = []

    for num in test_numbers:
        print(f"\nQuerying: {num} ...")
        query_req = urllib.request.Request(
            f"{PROD_URL}/investigate/universal",
            data=json.dumps({"query": num, "type": "phone"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PRAVISION-ProdTest/2.5"
            }
        )
        with urllib.request.urlopen(query_req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            info = data.get("identified_information", {})
            e164 = info.get("E.164 Format")
            country_code = info.get("Country Calling Code")
            country = info.get("Country / Territorial Origin")
            region = info.get("Telecommunications Region")
            line_type = info.get("Line Type")
            valid = info.get("Valid E.164 Allocation")
            status = data.get("status")

            item = {
                "input": num,
                "status": status,
                "e164": e164,
                "country_code": country_code,
                "country": country,
                "region": region,
                "line_type": line_type,
                "valid": valid,
                "headline": data.get("summary", {}).get("headline"),
                "duration": data.get("duration_seconds")
            }
            results.append(item)
            print(f"  Status: {status}")
            print(f"  E.164 Output: {e164}")
            print(f"  Country Calling Code: {country_code}")
            print(f"  Country / Region: {country} | {region}")
            print(f"  Line Type: {line_type}")
            print(f"  Valid E.164 Allocation: {valid}")
            print(f"  Execution Time: {data.get('duration_seconds')}s")

    print("\n" + "=" * 80)
    print("FINAL CONSOLIDATED RESULTS JSON:")
    print(json.dumps(results, indent=2))
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
