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
    with urllib.request.urlopen(login_req, timeout=35) as resp:
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
        with urllib.request.urlopen(query_req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            info = data.get("identified_information", {})
            e164 = info.get("E.164 Format")
            country_code = info.get("Country Calling Code")
            region = info.get("Telecommunications Region")
            line_type = info.get("Line Type")
            orig_carrier = info.get("Original Allocation Carrier")
            curr_carrier = info.get("Current Carrier")
            validity = info.get("Numbering-Plan Validity")
            sub_status = info.get("Live Subscriber Status")
            status = data.get("status")

            item = {
                "input": num,
                "status": status,
                "e164": e164,
                "country_code": country_code,
                "region": region,
                "line_type": line_type,
                "original_allocation_carrier": orig_carrier,
                "current_carrier": curr_carrier,
                "numbering_plan_validity": validity,
                "live_subscriber_status": sub_status,
                "headline": data.get("summary", {}).get("headline"),
                "duration": data.get("duration_seconds")
            }
            results.append(item)
            print(f"  Status: {status}")
            print(f"  E.164 Output: {e164}")
            print(f"  Country Calling Code: {country_code}")
            print(f"  Telecommunications Region: {region}")
            print(f"  Line Type: {line_type}")
            print(f"  Original Allocation Carrier: {orig_carrier}")
            print(f"  Current Carrier: {curr_carrier}")
            print(f"  Numbering-Plan Validity: {validity}")
            print(f"  Live Subscriber Status: {sub_status}")
            print(f"  Execution Time: {data.get('duration_seconds')}s")

    print("\n" + "=" * 80)
    print("FINAL CONSOLIDATED RESULTS JSON:")
    print(json.dumps(results, indent=2))
    print("=" * 80)

if __name__ == "__main__":
    run_tests()

