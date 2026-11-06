"""
PRAVISION — Production API Email MX Classification Test Script
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
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(login_req, timeout=35) as resp:
        token = json.loads(resp.read().decode("utf-8"))["access_token"]
    print(f"Authenticated successfully as {u}. Acquired JWT token.")

    test_emails = [
        ("Gmail (Public Webmail)", "test.user@gmail.com"),
        ("Google Corporate Domain (Custom MX)", "security@google.com"),
        ("Proton Mail (Encrypted Webmail)", "contact@proton.me"),
        ("Custom Corporate (OpenAI)", "contact@openai.com"),
        ("Domain Exists But No MX (NoAnswer)", "contact@httpbin.org"),
        ("Non-Existent Domain (NXDOMAIN)", "analyst@this-domain-definitely-does-not-exist-xyz-987.org"),
        ("Malformed Email Syntax", "malformed-address-no-at"),
    ]

    print("\n" + "=" * 80)
    print("PRODUCTION API TEST: EMAIL MX CLASSIFICATION & SUPPRESSION POLICY")
    print("Endpoint: https://pravision.pages.dev/api/investigate/universal")
    print("=" * 80)

    results = []

    for label, email in test_emails:
        print(f"\nTesting: {label} ({email}) ...")
        query_req = urllib.request.Request(
            f"{PROD_URL}/investigate/universal",
            data=json.dumps({"query": email, "type": "email"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0"
            }
        )
        with urllib.request.urlopen(query_req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            info = data.get("identified_information", {})
            mx_status = info.get("MX Routing Status")
            mx_records = info.get("MX Records")
            mx_details = info.get("MX Resolution Details")
            provider = info.get("Mail Provider Classification")
            status = data.get("status")

            item = {
                "label": label,
                "email": email,
                "status": status,
                "provider": provider,
                "mx_routing_status": mx_status,
                "mx_records": mx_records,
                "mx_resolution_details": mx_details,
                "execution_seconds": data.get("duration_seconds")
            }
            results.append(item)
            print(f"  Status: {status}")
            print(f"  Provider: {provider}")
            print(f"  MX Routing Status: {mx_status}")
            print(f"  MX Records: {mx_records}")
            print(f"  MX Resolution Details: {mx_details}")
            print(f"  Execution Time: {data.get('duration_seconds')}s")

    print("\n" + "=" * 80)
    print("FINAL CONSOLIDATED EMAIL MX RESULTS JSON:")
    print(json.dumps(results, indent=2))
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
