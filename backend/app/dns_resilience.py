"""
PRAVISION — Centralized DNS Resilience & Scoped Public Resolver Fallback.

Provides transparent fallback to Cloudflare (1.1.1.1, 1.0.0.1) and Google (8.8.8.8, 8.8.4.4)
public DNS when local ISP recursive DNS servers fail to resolve CNAME chains
or encounter Windows WSAHOST_NOT_FOUND (11001) errors.

Features:
- Idempotent: Can be imported or called multiple times safely without recursive nesting.
- Comprehensive: Properly handles IPv4 (A), IPv6 (AAAA), CNAME chaining, and numeric IP literals.
- Preserves Standard Behavior: Native OS resolver is always attempted first. Flags, socket types,
  and protocols are fully preserved.
- Robust Fallback: If both native and public resolvers fail, the original socket.gaierror is raised unchanged.
"""

import ipaddress
import logging
import socket
from typing import Any, List, Tuple

logger = logging.getLogger("pravision.dns_resilience")

_orig_getaddrinfo = socket.getaddrinfo
_is_installed = False

FALLBACK_NAMESERVERS = ["1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4"]


def _is_ip_literal(host: Any) -> bool:
    """Return True if host is an IPv4 or IPv6 address string."""
    if not isinstance(host, str) or not host.strip():
        return False
    clean = host.strip().strip("[]")
    try:
        ipaddress.ip_address(clean)
        return True
    except ValueError:
        return False


def _resolve_with_public_dns(host: str, family: int) -> List[str]:
    """Resolve host via public DNS resolvers using dnspython."""
    try:
        import dns.resolver
    except ImportError:
        return []

    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = FALLBACK_NAMESERVERS
    resolver.lifetime = 3.0
    resolver.timeout = 2.0

    clean_host = host.strip()
    ips: List[str] = []

    # If IPv6 requested, try AAAA first
    if family == socket.AF_INET6:
        try:
            answers = resolver.resolve(clean_host, "AAAA")
            for rdata in answers:
                ips.append(rdata.to_text())
        except Exception:
            pass
        return ips

    # If IPv4 requested or unspecified (family == 0 or AF_INET)
    try:
        answers = resolver.resolve(clean_host, "A")
        for rdata in answers:
            ips.append(rdata.to_text())
    except Exception:
        pass

    # If unspecified family (0) and no IPv4 answers, try AAAA
    if family == 0 and not ips:
        try:
            answers = resolver.resolve(clean_host, "AAAA")
            for rdata in answers:
                ips.append(rdata.to_text())
        except Exception:
            pass

    return ips


def resilient_getaddrinfo(
    host: Any,
    port: Any,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0
) -> List[Tuple[Any, ...]]:
    """Resilient socket.getaddrinfo wrapper with automated public DNS fallback."""
    # 1. Attempt native OS resolution first
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror as exc:
        # If already an IP address, or not a string hostname, re-raise original error
        if not isinstance(host, str) or not host or _is_ip_literal(host):
            raise exc

        # 2. Attempt fallback resolution via public nameservers
        try:
            resolved_ips = _resolve_with_public_dns(host, family)
            if resolved_ips:
                results = []
                for ip in resolved_ips:
                    target_family = socket.AF_INET6 if ":" in ip else socket.AF_INET
                    effective_family = family if family != 0 else target_family
                    try:
                        res = _orig_getaddrinfo(ip, port, effective_family, type, proto, flags)
                        results.extend(res)
                    except Exception:
                        pass
                if results:
                    return results
        except Exception:
            pass

        # 3. Fallback exhausted; re-raise original native error
        raise exc


def install_dns_resilience() -> bool:
    """Installs the resilient getaddrinfo resolver idempotently."""
    global _is_installed
    if _is_installed:
        return True

    socket.getaddrinfo = resilient_getaddrinfo
    _is_installed = True
    logger.debug("PRAVISION resilient DNS fallback installed.")
    return True

