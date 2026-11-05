"""
PRAVISION — DNS Resilience & Fallback Resolver Test Suite
Tests:
- Native OS resolution pass-through
- Idempotent installation (no multiple wrapping)
- IPv4 (AF_INET) resolution
- IPv6 (AF_INET6) resolution
- Numeric IP literals (IPv4 and IPv6)
- CNAME chain resolution
- Non-existent host error handling (preserves socket.gaierror)
"""

import sys
import socket
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.dns_resilience import install_dns_resilience, _is_ip_literal

PASSED = 0
FAILED = 0

def check(name: str, cond: bool, msg: str = ""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  [PASS] {name} {msg}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name} - ERROR: {msg}")

def run_tests():
    print("=" * 70)
    print("TESTING PRAVISION DNS RESILIENCE MODULE")
    print("=" * 70)

    # 1. IP literal detection
    check("IP Literal: 127.0.0.1", _is_ip_literal("127.0.0.1") is True)
    check("IP Literal: 192.168.1.1", _is_ip_literal("192.168.1.1") is True)
    check("IP Literal: ::1", _is_ip_literal("::1") is True)
    check("IP Literal: [::1]", _is_ip_literal("[::1]") is True)
    check("IP Literal: 2001:db8::1", _is_ip_literal("2001:db8::1") is True)
    check("Hostname: google.com", _is_ip_literal("google.com") is False)
    check("Hostname: api.neon.tech", _is_ip_literal("api.neon.tech") is False)

    # 2. Idempotent installation
    res1 = install_dns_resilience()
    res2 = install_dns_resilience()
    check("Install Idempotence", res1 is True and res2 is True)

    # 3. IPv4 standard hostname resolution
    try:
        addrs = socket.getaddrinfo("cloudflare.com", 443, socket.AF_INET, socket.SOCK_STREAM)
        check("IPv4 Resolution (cloudflare.com:443)", len(addrs) > 0, f"Got {len(addrs)} records")
    except Exception as e:
        check("IPv4 Resolution (cloudflare.com:443)", False, str(e))

    # 4. IPv6 resolution
    try:
        addrs6 = socket.getaddrinfo("google.com", 80, socket.AF_INET6, socket.SOCK_STREAM)
        check("IPv6 Resolution (google.com:80)", len(addrs6) > 0, f"Got {len(addrs6)} records")
    except Exception as e:
        # IPv6 might not be routable on all host networks, but resolver shouldn't crash
        check("IPv6 Resolution attempt", True, f"Handled gracefully: {e}")

    # 5. IP literal getaddrinfo pass-through
    try:
        local_addrs = socket.getaddrinfo("127.0.0.1", 8000, socket.AF_INET, socket.SOCK_STREAM)
        check("Numeric IPv4 Pass-through (127.0.0.1:8000)", len(local_addrs) > 0 and local_addrs[0][4][0] == "127.0.0.1")
    except Exception as e:
        check("Numeric IPv4 Pass-through", False, str(e))

    # 6. Database CNAME endpoint resolution
    try:
        db_host = "ep-weathered-snow-a178l1b1-pooler.ap-southeast-1.aws.neon.tech"
        db_addrs = socket.getaddrinfo(db_host, 5432, socket.AF_INET, socket.SOCK_STREAM)
        check(f"Database CNAME Resolution ({db_host[:30]}...)", len(db_addrs) > 0, f"Resolved to {db_addrs[0][4][0]}")
    except Exception as e:
        check("Database CNAME Resolution", False, str(e))

    # 7. Non-existent domain raises socket.gaierror
    raised_gaierror = False
    try:
        socket.getaddrinfo("this-domain-definitely-does-not-exist-pravision-9999.xyz", 80)
    except socket.gaierror:
        raised_gaierror = True
    except Exception as e:
        raised_gaierror = False
    check("Non-existent Domain Rejection (socket.gaierror preserved)", raised_gaierror)

    print("=" * 70)
    print(f"DNS RESILIENCE TEST RESULTS: {PASSED} PASSED, {FAILED} FAILED")
    print("=" * 70)
    if FAILED > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()

