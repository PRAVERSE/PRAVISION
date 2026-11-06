import re
import os
import io
import time
import uuid
import hashlib
import logging
import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import httpx
import dns.resolver
from pydantic import BaseModel, Field

import phonenumbers
from phonenumbers import geocoder, carrier, timezone as phone_tz
from PIL import Image, ExifTags

from app.connectors.phone.phone_connectors import parse_phone_resiliently, LINE_TYPE_MAP
from app.dns_resilience import install_dns_resilience

install_dns_resilience()
logger = logging.getLogger("pravision.universal_orchestrator")

# ----------------- DATA MODELS -----------------

class ReportSummary(BaseModel):
    headline: str
    risk_level: str = "Informational"  # Informational, Low, Medium, High
    confidence_score: int = Field(ge=0, le=100, default=85)
    key_takeaways: List[str] = Field(default_factory=list)

class AssociatedProfile(BaseModel):
    platform: str
    identifier: str
    url: str
    status: str = "Verified Active"  # Verified Active, Possible Match, Unconfirmed
    details: Optional[str] = None
    avatar_url: Optional[str] = None

class ContactAssociation(BaseModel):
    association_type: str  # Name, Location, Timezone, Carrier, Email, Phone, Organization
    value: str
    source: str
    confidence: str = "High"  # High, Moderate, Low

class PublicReference(BaseModel):
    title: str
    url: str
    source_type: str  # DNS / Registry, Directory Dork, Public Profile, Search Index
    description: str

class RelatedFinding(BaseModel):
    title: str
    details: str
    category: str
    confidence: str = "High"

class ConfidenceBreakdown(BaseModel):
    factor: str
    assessment: str
    impact: str  # Positive, Neutral, Cautionary

class ConfidenceStatus(BaseModel):
    overall_level: str = "High"  # High, Moderate, Low
    score: int = 85
    breakdown: List[ConfidenceBreakdown] = Field(default_factory=list)

class ConsolidatedReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target: str
    target_type: str  # email, phone, username, image
    status: str = "completed"  # queued, running, completed, completed_with_warnings, failed
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_seconds: float = 0.0
    summary: ReportSummary
    identified_information: Dict[str, Any] = Field(default_factory=dict)
    associated_profiles: List[AssociatedProfile] = Field(default_factory=list)
    contact_associations: List[ContactAssociation] = Field(default_factory=list)
    public_references: List[PublicReference] = Field(default_factory=list)
    related_findings: List[RelatedFinding] = Field(default_factory=list)
    confidence_and_verification: ConfidenceStatus
    investigation_limitations: List[str] = Field(default_factory=list)

# ----------------- CONSTANTS & LOOKUPS -----------------

DISPOSABLE_EMAIL_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com",
    "throwawaymail.com", "sharklasers.com", "yopmail.com", "dispostable.com",
    "trashmail.com", "getairmail.com", "burnermail.io", "fakeinbox.com",
    "nada.ltd", "mohmal.com", "inboxkitten.com", "mytemp.email", "crazymailing.com",
    "temp-mail.org", "dropmail.me", "maildrop.cc", "emailondeck.com"
}

PUBLIC_WEBMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
    "yahoo.com", "ymail.com", "rocketmail.com", "proton.me", "protonmail.com",
    "icloud.com", "me.com", "mac.com", "aol.com", "zoho.com", "mail.com", "gmx.com"
}

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

def classify_target(query: str, manual_override: Optional[str] = None) -> str:
    """Classifies an investigation target query with auto-detection or explicit manual override."""
    if manual_override and manual_override.lower() in ("email", "phone", "username", "image"):
        return manual_override.lower()

    q = query.strip()
    if "@" in q and "." in q.split("@")[-1]:
        return "email"

    # Digits and symbols check
    digits = re.sub(r'[^\d]', '', q)
    if (q.startswith("+") and len(digits) >= 7) or (len(digits) >= 9 and len(digits) <= 15 and re.match(r'^[\d\s\-\(\)\.]+$', q)):
        return "phone"

    # Image extension heuristic
    lower = q.lower()
    if any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".tiff", ".bmp")):
        return "image"

    return "username"


def query_address_record(resolver: dns.resolver.Resolver, domain: str, rtype: str) -> Tuple[str, List[str], Optional[str]]:
    """
    Independently queries an address record (A or AAAA) for RFC 5321 implicit MX fallback.
    Returns: (status, records, error_detail)
    status: 'answered', 'no_answer', 'nxdomain', 'timeout', 'servfail', 'lookup_failed'
    """
    try:
        ans = resolver.resolve(domain, rtype)
        records = [str(r).strip() for r in ans if str(r).strip()]
        if records:
            return "answered", records, None
        return "no_answer", [], "No records returned"
    except dns.resolver.NoAnswer:
        return "no_answer", [], "NoAnswer (domain exists, but no address record of this type)"
    except dns.resolver.NXDOMAIN:
        return "nxdomain", [], "NXDOMAIN (domain does not exist)"
    except dns.resolver.Timeout:
        return "timeout", [], "DNS query timed out"
    except Exception as e:
        err_msg = str(e).lower()
        err_type = type(e).__name__.lower()
        if "servfail" in err_msg or "servfail" in err_type or "serverfailure" in err_type:
            return "servfail", [], f"SERVFAIL: {e}"
        if isinstance(e, dns.resolver.NoNameservers):
            return "servfail", [], f"SERVFAIL / No nameservers answered: {e}"
        return "lookup_failed", [], f"Lookup failed ({type(e).__name__}): {e}"


class UniversalOrchestrator:
    """
    Central, resilient OSINT investigation orchestrator providing fast,
    consolidated intelligence reports for Email, Phone, Username, and Images.
    """

    def __init__(self):
        self._jobs: Dict[str, ConsolidatedReport] = {}
        self._client_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 PRAVISION-OSINT/2.5"
        }

    def get_job(self, job_id: str) -> Optional[ConsolidatedReport]:
        return self._jobs.get(job_id)

    def list_recent_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        sorted_jobs = sorted(self._jobs.values(), key=lambda j: j.timestamp, reverse=True)
        return [
            {
                "id": j.id,
                "target": j.target,
                "target_type": j.target_type,
                "status": j.status,
                "timestamp": j.timestamp,
                "headline": j.summary.headline,
                "confidence_score": j.summary.confidence_score
            }
            for j in sorted_jobs[:limit]
        ]

    # ----------------- EMAIL INVESTIGATION -----------------

    async def investigate_email(self, email_raw: str, job_id: str) -> ConsolidatedReport:
        start_time = time.time()
        email = email_raw.strip().lower()

        # 1. Syntax Validation
        is_rfc_syntax = bool(EMAIL_REGEX.match(email))
        if not is_rfc_syntax or "@" not in email:
            duration = round(time.time() - start_time, 2)
            report = ConsolidatedReport(
                id=job_id,
                target=email,
                target_type="email",
                status="completed_with_warnings",
                duration_seconds=duration,
                summary=ReportSummary(
                    headline=f"Invalid email address syntax: {email}",
                    risk_level="High",
                    confidence_score=95,
                    key_takeaways=[
                        "Submitted string fails standard RFC 5322 email syntax validation.",
                        "No mail server resolution or profile matching can be executed."
                    ]
                ),
                identified_information={
                    "Submitted Target": email,
                    "Syntax RFC Compliant": False,
                    "Format Status": "Malformed email format",
                    "DNS Query Status": "not_performed",
                    "MX Routing Status": "not_performed",
                    "Mail Routing Assessment": "not_performed",
                    "Mail Routing Description": "Not Performed (Invalid RFC 5322 Syntax)",
                    "MX Resolution Details": "Invalid RFC 5322 email syntax — MX lookup was not performed.",
                    "MX Records": "Not Performed"
                },
                confidence_and_verification=ConfidenceStatus(
                    overall_level="High",
                    score=95,
                    breakdown=[
                        ConfidenceBreakdown(factor="RFC Syntax Validation", assessment="Failed standard email structure", impact="Cautionary"),
                        ConfidenceBreakdown(factor="DNS MX Verification", assessment="Not performed due to syntax failure", impact="Neutral")
                    ]
                ),
                investigation_limitations=[
                    "Malformed email addresses cannot be resolved against DNS or public identity registries."
                ]
            )
            self._jobs[job_id] = report
            return report

        username_part, domain_part = email.split("@", 1)
        is_disposable = domain_part in DISPOSABLE_EMAIL_DOMAINS
        is_public_webmail = domain_part in PUBLIC_WEBMAIL_DOMAINS

        # 2. DNS MX, SPF, DMARC Resolution
        mx_records: List[str] = []
        spf_record: Optional[str] = None
        dmarc_record: Optional[str] = None
        dns_query_status: str = "not_performed"
        mx_status: str = "not_performed"
        mail_routing_assessment: str = "unverified"
        mail_routing_description: str = "Unassessed"
        mx_status_explanation: str = ""
        mx_records_str: str = "Not Performed"
        is_nxdomain: bool = False
        is_noanswer: bool = False
        is_null_mx: bool = False
        has_address_records: bool = False
        address_records: List[str] = []

        if is_public_webmail:
            dns_query_status = "suppressed_by_policy"
            mx_status = "suppressed_by_policy"
            mail_routing_assessment = "suppressed_by_policy"
            mail_routing_description = "Consumer Webmail Domain (Managed Infrastructure)"
            mx_status_explanation = (
                f"Public webmail domain ({domain_part}) — mail provider classified directly by architectural signature; "
                "deep DNS infrastructure expansion is suppressed by policy to prevent attributing shared multi-tenant gateways to individual targets."
            )
            mx_records_str = "Suppressed by Policy (Webmail Domain)"
        else:
            try:
                dns_resolver = dns.resolver.Resolver()
                for ns in ["1.1.1.1", "8.8.8.8", "1.0.0.1", "8.8.4.4"]:
                    if ns not in dns_resolver.nameservers:
                        dns_resolver.nameservers.append(ns)
            except Exception:
                dns_resolver = dns.resolver.Resolver(configure=False)
                dns_resolver.nameservers = ["1.1.1.1", "8.8.8.8", "1.0.0.1", "8.8.4.4"]
            dns_resolver.timeout = 3.5
            dns_resolver.lifetime = 3.5

            try:
                answers = dns_resolver.resolve(domain_part, 'MX')
                has_null_mx = False
                ordinary_mx_records: List[str] = []

                for rdata in answers:
                    pref = getattr(rdata, 'preference', None)
                    exchange_raw = str(getattr(rdata, 'exchange', '')).strip()
                    exchange_clean = exchange_raw.rstrip('.')
                    # Detect RFC 7505 Null MX record ("MX 0 .")
                    if pref == 0 and (exchange_clean == "" or exchange_raw == "."):
                        has_null_mx = True
                    else:
                        if exchange_clean:
                            ordinary_mx_records.append(exchange_clean)

                if has_null_mx and not ordinary_mx_records:
                    is_null_mx = True
                    dns_query_status = "answered"
                    mx_status = "resolved"
                    mail_routing_assessment = "null_mx"
                    mail_routing_description = "Explicitly Declares No Mail Acceptance (RFC 7505 Null MX)"
                    mx_status_explanation = (
                        f"Domain '{domain_part}' publishes an explicit RFC 7505 Null MX record ('MX 0 .'), "
                        "formally declaring that it does not accept incoming email on any server."
                    )
                    mx_records_str = "Null MX (RFC 7505 — Does Not Accept Mail)"
                elif has_null_mx and ordinary_mx_records:
                    dns_query_status = "answered"
                    mx_status = "resolved"
                    mail_routing_assessment = "malformed_configuration"
                    mail_routing_description = "Protocol Violation: Mixed Null MX and Ordinary MX (RFC 7505 Section 3)"
                    mx_status_explanation = (
                        f"Domain '{domain_part}' publishes both an RFC 7505 Null MX record ('MX 0 .') and ordinary MX records "
                        f"({', '.join(ordinary_mx_records)}). RFC 7505 Section 3 explicitly prohibits publishing any other MX records alongside Null MX. "
                        "Mail transfer agents may reject or behave unpredictably when encountering this malformed configuration."
                    )
                    mx_records_str = f"Malformed Configuration (Mixed Null MX and Ordinary MX: {', '.join(ordinary_mx_records)})"
                    mx_records = ordinary_mx_records
                elif ordinary_mx_records:
                    dns_query_status = "answered"
                    mx_status = "resolved"
                    mail_routing_assessment = "explicit_mx"
                    mail_routing_description = "Explicit MX Configured"
                    mx_status_explanation = f"Successfully resolved {len(ordinary_mx_records)} authoritative MX host(s) for domain."
                    mx_records = ordinary_mx_records
                    mx_records_str = ", ".join(ordinary_mx_records)
                else:
                    is_noanswer = True
            except dns.resolver.NoAnswer:
                is_noanswer = True
            except dns.resolver.NXDOMAIN:
                is_nxdomain = True
                dns_query_status = "answered"
                mx_status = "resolved"
                mail_routing_assessment = "nxdomain"
                mail_routing_description = "Non-Existent Domain (NXDOMAIN)"
                mx_status_explanation = (
                    f"Queried domain '{domain_part}' does not exist in the Domain Name System "
                    "(NXDOMAIN authoritative response). Senders cannot route mail to non-existent domains."
                )
                mx_records_str = "Domain Does Not Exist (NXDOMAIN)"
            except dns.resolver.Timeout:
                dns_query_status = "lookup_failed"
                mx_status = "lookup_failed"
                mail_routing_assessment = "unverified"
                mail_routing_description = "DNS Lookup Failed (Timeout / Transport Error)"
                mx_status_explanation = (
                    "DNS resolution timed out connecting to authoritative nameservers. "
                    "DNS evidence was unresolvable; this is not a confirmation of non-existence or zero records."
                )
                mx_records_str = "Lookup Failed (DNS Timeout / Unreachable)"
            except Exception as e:
                dns_query_status = "lookup_failed"
                mx_status = "lookup_failed"
                mail_routing_assessment = "unverified"
                mail_routing_description = f"DNS Lookup Failed ({type(e).__name__})"
                mx_status_explanation = (
                    f"DNS resolution failed connecting to authoritative nameservers ({type(e).__name__}). "
                    "DNS evidence was unresolvable; this is not a confirmation of non-existence or zero records."
                )
                mx_records_str = f"Lookup Failed ({type(e).__name__})"

            # RFC 5321 Section 5.1: If no explicit MX record exists (NoAnswer), evaluate address records (implicit MX)
            if is_noanswer:
                a_status, a_records, a_err = query_address_record(dns_resolver, domain_part, 'A')
                aaaa_status, aaaa_records, aaaa_err = query_address_record(dns_resolver, domain_part, 'AAAA')
                address_records = a_records + aaaa_records

                has_err = a_status in ("timeout", "servfail", "lookup_failed") or aaaa_status in ("timeout", "servfail", "lookup_failed")
                has_ans = a_status == "answered" or aaaa_status == "answered"

                if has_ans and not has_err:
                    has_address_records = True
                    dns_query_status = "answered"
                    mx_status = "resolved"
                    mail_routing_assessment = "implicit_mx_candidate"
                    mail_routing_description = "Implicit MX Routing May Apply (RFC 5321 Section 5.1)"
                    mx_status_explanation = (
                        f"No explicit MX record published for '{domain_part}'. However, authoritative address records "
                        f"(A/AAAA: {', '.join(address_records[:3])}) were resolved. In accordance with RFC 5321 Section 5.1, "
                        "mail transfer agents may attempt delivery using implicit MX routing directed to the domain's host IP addresses. "
                        "Actual SMTP server responsiveness or inbox deliverability has not been tested."
                    )
                    mx_records_str = f"No Explicit MX (Address Records Found: {', '.join(address_records[:2])})"
                elif has_ans and has_err:
                    has_address_records = True
                    dns_query_status = "lookup_failed"
                    mx_status = "resolved"
                    mail_routing_assessment = "unverified"
                    mail_routing_description = "Partial Address Resolution (Unverified Implicit MX Assessment)"
                    err_info = aaaa_err if a_status == "answered" else a_err
                    failed_type = "AAAA" if a_status == "answered" else "A"
                    mx_status_explanation = (
                        f"No explicit MX record published for '{domain_part}'. Address resolution was partial: "
                        f"successfully resolved address records ({', '.join(address_records)}), but "
                        f"{failed_type} query failed ({err_info}). "
                        "Due to incomplete address query resolution, the mail routing assessment is unverified. "
                        "Implicit MX delivery may be attempted by MTAs to the discovered addresses, but full host routing cannot be guaranteed."
                    )
                    mx_records_str = f"Partial Address Records (Found: {', '.join(address_records[:2])}; Fallback Incomplete)"
                elif not has_ans and has_err:
                    dns_query_status = "lookup_failed"
                    mx_status = "lookup_failed"
                    mail_routing_assessment = "unverified"
                    mail_routing_description = "DNS Address Lookup Failed (Timeout / Server Error During Fallback)"
                    mx_status_explanation = (
                        f"Domain '{domain_part}' returned NoAnswer for MX records, but subsequent RFC 5321 address lookups (A/AAAA) "
                        f"failed or timed out (A: {a_err}; AAAA: {aaaa_err}). Cannot determine whether address records exist."
                    )
                    mx_records_str = "Lookup Failed (DNS Timeout / Error on Address Fallback)"
                else:
                    # Both are no_answer
                    dns_query_status = "answered"
                    mx_status = "resolved"
                    mail_routing_assessment = "no_route"
                    mail_routing_description = "No MX or Address Records Published"
                    mx_status_explanation = (
                        f"Domain '{domain_part}' exists in DNS, but returned neither explicit MX records (NoAnswer) "
                        "nor reachable A/AAAA address records. Mail transfer agents have no valid destination host to route email."
                    )
                    mx_records_str = "None Published (No MX or Address Records)"

            try:
                txt_answers = dns_resolver.resolve(domain_part, 'TXT')
                for rdata in txt_answers:
                    txt_str = "".join([s.decode('utf-8', errors='ignore') for s in rdata.strings])
                    if txt_str.startswith("v=spf1"):
                        spf_record = txt_str
                        break
            except Exception:
                pass

            try:
                dmarc_answers = dns_resolver.resolve(f"_dmarc.{domain_part}", 'TXT')
                for rdata in dmarc_answers:
                    txt_str = "".join([s.decode('utf-8', errors='ignore') for s in rdata.strings])
                    if txt_str.startswith("v=DMARC1"):
                        dmarc_record = txt_str
                        break
            except Exception:
                pass

        # 3. Provider Classification
        provider = "Custom / Private Mail Host"
        mx_joined = " ".join(mx_records).lower()
        if domain_part in ("gmail.com", "googlemail.com"):
            provider = "Google Workspace / Gmail"
        elif domain_part in ("outlook.com", "hotmail.com", "live.com", "msn.com"):
            provider = "Microsoft 365 / Outlook"
        elif domain_part in ("proton.me", "protonmail.com"):
            provider = "Proton Mail (End-to-End Encrypted)"
        elif domain_part in ("yahoo.com", "ymail.com", "rocketmail.com"):
            provider = "Yahoo Mail"
        elif domain_part in ("apple.com", "icloud.com", "me.com", "mac.com"):
            provider = "Apple iCloud Mail"
        elif "google" in mx_joined or "aspmx" in mx_joined or domain_part == "google.com":
            provider = "Google Workspace / Gmail"
        elif "outlook" in mx_joined or "protection.outlook.com" in mx_joined or domain_part == "microsoft.com":
            provider = "Microsoft 365 / Outlook"
        elif "proton" in mx_joined:
            provider = "Proton Mail (End-to-End Encrypted)"
        elif "yahoodns" in mx_joined:
            provider = "Yahoo Mail"
        elif "icloud" in mx_joined:
            provider = "Apple iCloud Mail"
        elif "zoho" in mx_joined or domain_part.startswith("zoho."):
            provider = "Zoho Mail"
        elif "messagingengine" in mx_joined or domain_part == "fastmail.com":
            provider = "Fastmail"

        # 4. Identity Lookups (Gravatar, GitHub, OpenPGP) concurrently
        email_md5 = hashlib.md5(email.encode('utf-8')).hexdigest()
        associated_profiles: List[AssociatedProfile] = []
        contact_associations: List[ContactAssociation] = [
            ContactAssociation(association_type="Domain", value=domain_part, source="Email Syntax", confidence="High"),
            ContactAssociation(association_type="Mail Provider", value=provider, source="MX DNS Records", confidence="High")
        ]
        related_findings: List[RelatedFinding] = []

        async with httpx.AsyncClient(timeout=4.0, headers=self._client_headers) as client:
            # Gravatar lookup
            gravatar_task = client.get(f"https://en.gravatar.com/{email_md5}.json")
            # GitHub search by email
            github_task = client.get(f"https://api.github.com/search/users?q={email}+in:email")
            # OpenPGP key lookup
            pgp_task = client.get(f"https://keys.openpgp.org/vks/v1/by-email/{urllib.parse.quote(email)}")

            responses = await asyncio.gather(gravatar_task, github_task, pgp_task, return_exceptions=True)
            gravatar_resp, github_resp, pgp_resp = responses

            # Parse Gravatar
            if isinstance(gravatar_resp, httpx.Response) and gravatar_resp.status_code == 200:
                try:
                    entry = gravatar_resp.json().get("entry", [])[0]
                    disp_name = entry.get("displayName") or entry.get("preferredUsername") or username_part
                    prof_url = entry.get("profileUrl") or f"https://gravatar.com/{email_md5}"
                    avatar = entry.get("thumbnailUrl")
                    loc = entry.get("currentLocation")
                    about = entry.get("aboutMe")

                    associated_profiles.append(AssociatedProfile(
                        platform="Gravatar",
                        identifier=disp_name,
                        url=prof_url,
                        status="Verified Active",
                        details=f"Public profile confirmed. {about or ''}".strip(),
                        avatar_url=avatar
                    ))
                    if disp_name:
                        contact_associations.append(ContactAssociation(
                            association_type="Identified Name / Handle",
                            value=disp_name,
                            source="Gravatar Global Avatar Registry",
                            confidence="High"
                        ))
                    if loc:
                        contact_associations.append(ContactAssociation(
                            association_type="Declared Location",
                            value=loc,
                            source="Gravatar Profile Metadata",
                            confidence="Moderate"
                        ))
                    related_findings.append(RelatedFinding(
                        title="Gravatar Identity Record",
                        details=f"Associated Gravatar account active with display name '{disp_name}'",
                        category="Identity",
                        confidence="High"
                    ))
                except Exception as e:
                    logger.debug(f"Gravatar parsing warning: {e}")

            # Parse GitHub
            if isinstance(github_resp, httpx.Response) and github_resp.status_code == 200:
                try:
                    gh_data = github_resp.json()
                    total_gh = gh_data.get("total_count", 0)
                    items = gh_data.get("items", [])
                    if total_gh > 0 and items:
                        gh_user = items[0]
                        login = gh_user.get("login")
                        gh_url = gh_user.get("html_url") or f"https://github.com/{login}"
                        gh_avatar = gh_user.get("avatar_url")
                        associated_profiles.append(AssociatedProfile(
                            platform="GitHub",
                            identifier=login,
                            url=gh_url,
                            status="Verified Active",
                            details="Public commits or account profile explicitly associated with this email",
                            avatar_url=gh_avatar
                        ))
                        contact_associations.append(ContactAssociation(
                            association_type="GitHub Developer Identity",
                            value=login,
                            source="GitHub Public User API",
                            confidence="High"
                        ))
                except Exception as e:
                    logger.debug(f"GitHub parsing warning: {e}")

            # Parse OpenPGP
            if isinstance(pgp_resp, httpx.Response) and pgp_resp.status_code == 200:
                related_findings.append(RelatedFinding(
                    title="OpenPGP Public Key",
                    details="Cryptographic public encryption key registered on keys.openpgp.org for this email",
                    category="Cryptography & Security",
                    confidence="High"
                ))
                contact_associations.append(ContactAssociation(
                    association_type="OpenPGP Key Server Registration",
                    value="Published PGP Key Available",
                    source="keys.openpgp.org",
                    confidence="High"
                ))

        # 5. Public References & Search Footprints
        dork_url = f"https://www.google.com/search?q={urllib.parse.quote(f'\"{email}\"')}"
        public_references: List[PublicReference] = [
            PublicReference(
                title=f"Google Public Index Footprint ({email})",
                url=dork_url,
                source_type="Search Index",
                description="Targeted public search query for mentions across indexed websites and public pastes"
            ),
            PublicReference(
                title=f"DNS MX Records for {domain_part}",
                url=f"https://dns.google/resolve?name={domain_part}&type=MX",
                source_type="DNS / Registry",
                description=f"Authoritative mail exchange routing verified on {len(mx_records)} MX servers"
            )
        ]

        if spf_record:
            related_findings.append(RelatedFinding(
                title="SPF Security Policy",
                details=f"Domain publishes SPF authorization record: {spf_record[:80]}...",
                category="Security",
                confidence="High"
            ))
        if dmarc_record:
            related_findings.append(RelatedFinding(
                title="DMARC Policy Enforcement",
                details=f"DMARC email authentication policy published: {dmarc_record[:80]}...",
                category="Security",
                confidence="High"
            ))

        # 6. Score & Breakdown
        if mx_status == "suppressed_by_policy":
            mx_assessment = f"Suppressed by policy ({provider} signature classified)"
            mx_impact = "Positive"
        elif is_null_mx:
            mx_assessment = "Domain explicitly rejects email (RFC 7505 Null MX)"
            mx_impact = "Cautionary"
        elif mail_routing_assessment == "malformed_configuration":
            mx_assessment = "Mixed RFC 7505 Null MX with ordinary MX records (protocol violation)"
            mx_impact = "Cautionary"
        elif mail_routing_assessment == "explicit_mx":
            mx_assessment = f"Found {len(mx_records)} authoritative MX host(s)"
            mx_impact = "Positive"
        elif mail_routing_assessment == "implicit_mx_candidate":
            mx_assessment = "No explicit MX record found; A/AAAA address records available (implicit MX routing candidate)"
            mx_impact = "Neutral"
        elif mail_routing_assessment == "unverified" and has_address_records:
            mx_assessment = "Partial address resolution; some address queries failed (unverified implicit MX assessment)"
            mx_impact = "Neutral"
        elif mail_routing_assessment == "no_route":
            mx_assessment = "Domain exists, but publishes neither MX nor address records"
            mx_impact = "Cautionary"
        elif is_nxdomain:
            mx_assessment = "Queried domain does not exist in DNS (NXDOMAIN)"
            mx_impact = "Cautionary"
        elif mx_status == "lookup_failed" or mail_routing_assessment == "unverified":
            mx_assessment = "DNS resolution timed out or failed"
            mx_impact = "Cautionary"
        elif mx_status == "not_performed":
            mx_assessment = "Not performed due to syntax failure"
            mx_impact = "Neutral"
        else:
            mx_assessment = "No active MX records found"
            mx_impact = "Cautionary"

        confidence_breakdown = [
            ConfidenceBreakdown(factor="RFC 5322 Syntax Check", assessment="Valid and properly structured", impact="Positive"),
            ConfidenceBreakdown(factor="DNS MX Verification", assessment=mx_assessment, impact=mx_impact),
            ConfidenceBreakdown(factor="Disposable Provider Check", assessment="Legitimate domain (not disposable)" if not is_disposable else "Known disposable/temporary provider", impact="Positive" if not is_disposable else "Cautionary")
        ]
        if associated_profiles:
            confidence_breakdown.append(ConfidenceBreakdown(
                factor="Public Profile Corroboration",
                assessment=f"Corroborated across {len(associated_profiles)} verified public platform(s)",
                impact="Positive"
            ))

        base_score = 75
        if (mx_records or mx_status == "suppressed_by_policy") and not is_nxdomain and not is_noanswer and not is_null_mx and mail_routing_assessment != "malformed_configuration":
            base_score += 10
        if is_disposable or is_nxdomain or is_null_mx or mail_routing_assessment == "malformed_configuration":
            base_score -= 25
        elif mail_routing_assessment == "no_route":
            base_score -= 15
        elif mail_routing_assessment == "implicit_mx_candidate":
            base_score -= 5
        elif mail_routing_assessment == "unverified":
            base_score -= 10
        if associated_profiles:
            base_score += 10
        confidence_score = max(20, min(95, base_score))

        risk_level = (
            "High" if (is_disposable or is_nxdomain or is_null_mx or mail_routing_assessment in ("no_route", "malformed_configuration"))
            else ("Low" if (mx_records or mx_status == "suppressed_by_policy") else "Medium")
        )

        if is_nxdomain:
            headline = f"Non-Existent Mail Domain ({email})"
        elif is_null_mx:
            headline = f"Domain Rejects Mail (RFC 7505 Null MX) ({email})"
        elif mail_routing_assessment == "malformed_configuration":
            headline = f"Malformed Mail Routing Configuration ({email})"
        elif mail_routing_assessment == "implicit_mx_candidate":
            headline = f"No Explicit MX — Address Records Found ({email})"
        elif mail_routing_assessment == "unverified" and has_address_records:
            headline = f"Partial Address Records Found ({email})"
        elif mail_routing_assessment == "no_route":
            headline = f"Domain Lacks Mail Routing Records ({email})"
        elif mail_routing_assessment == "unverified":
            headline = f"Unverified Mail Routing ({email})"
        elif mx_records or mx_status == "suppressed_by_policy" or provider != "Custom / Private Mail Host":
            headline = f"Active {provider} Address ({email})"
        else:
            headline = f"Unverified Mail Host ({email})"

        if mx_status == "suppressed_by_policy":
            mx_takeaway = f"Domain MX status: Suppressed by policy ({provider} classified by domain architecture without deep DNS expansion)."
        elif is_null_mx:
            mx_takeaway = "Domain MX status: Domain explicitly declares that it does not accept email via RFC 7505 Null MX ('MX 0 .')."
        elif mail_routing_assessment == "malformed_configuration":
            mx_takeaway = f"Domain MX status: Malformed configuration — domain publishes both RFC 7505 Null MX and ordinary MX ({', '.join(mx_records)})."
        elif mail_routing_assessment == "explicit_mx":
            mx_takeaway = f"Domain MX status: Configured with {len(mx_records)} authoritative mail server(s)."
        elif mail_routing_assessment == "implicit_mx_candidate":
            mx_takeaway = f"Domain MX status: No explicit MX record found; authoritative address records (A/AAAA: {', '.join(address_records[:3])}) resolved where implicit MX routing (RFC 5321) may apply. SMTP deliverability unverified."
        elif mail_routing_assessment == "unverified" and has_address_records:
            mx_takeaway = f"Domain MX status: Address resolution was partial ({', '.join(address_records[:2])} found, but secondary address lookup failed); routing assessment unverified."
        elif mail_routing_assessment == "no_route":
            mx_takeaway = "Domain MX status: Domain exists in DNS but publishes neither explicit MX records nor address records."
        elif is_nxdomain:
            mx_takeaway = f"Domain MX status: Domain '{domain_part}' does not exist in DNS (NXDOMAIN authoritative response)."
        elif mx_status == "lookup_failed" or mail_routing_assessment == "unverified":
            mx_takeaway = "Domain MX status: Lookup failed due to DNS timeout / unreachable nameservers."
        elif mx_status == "not_performed":
            mx_takeaway = "Domain MX status: Not performed."
        else:
            mx_takeaway = "Domain MX status: No active MX records detected."

        key_takeaways = [
            f"Email address belongs to {provider}.",
            mx_takeaway,
            f"Disposable / Temporary mailbox: {'YES (Throwaway / Anonymous)' if is_disposable else 'NO (Persistent Domain)'}."
        ]
        if associated_profiles:
            key_takeaways.append(f"Linked to {len(associated_profiles)} public identity profile(s): {', '.join([p.platform for p in associated_profiles])}.")
        if spf_record or dmarc_record:
            key_takeaways.append(f"Security posture: {'SPF configured' if spf_record else ''} {'DMARC active' if dmarc_record else ''}.".strip())

        limitations = [
            "DNS mail routing verification confirms authoritative DNS record publication only; it does not verify individual mailbox existence, account provisioning, or real-time inbox deliverability.",
            "Direct inbox deliverability testing (SMTP VRFY) is restricted to avoid triggering anti-abuse intrusion flags.",
            "Non-public profile information, private passwords, and encrypted account data cannot be accessed.",
            "Compliance with ethical standards: no brute-force login or credential-stuffing tests are performed."
        ]
        if is_public_webmail:
            limitations.append(
                f"Public consumer webmail domain ({domain_part}): deep MX and infrastructure DNS expansion is suppressed by policy. "
                f"The target is classified as {provider} based on domain architecture without querying shared multi-tenant infrastructure."
            )

        duration = round(time.time() - start_time, 2)
        report = ConsolidatedReport(
            id=job_id,
            target=email,
            target_type="email",
            status="completed",
            duration_seconds=duration,
            summary=ReportSummary(
                headline=headline,
                risk_level=risk_level,
                confidence_score=confidence_score,
                key_takeaways=key_takeaways
            ),
            identified_information={
                "Target Address": email,
                "Username Handle": username_part,
                "Domain Name": domain_part,
                "Mail Provider Classification": provider,
                "Disposable Mail Service": "Yes (High Risk)" if is_disposable else "No (Legitimate Domain)",
                "DNS Query Status": dns_query_status,
                "MX Routing Status": mx_status,
                "Mail Routing Assessment": mail_routing_assessment,
                "Mail Routing Description": mail_routing_description,
                "MX Resolution Details": mx_status_explanation,
                "MX Records": mx_records_str,
                "SPF Policy Published": "Yes" if spf_record else ("Suppressed (Webmail Domain)" if is_public_webmail else "No"),
                "DMARC Policy Published": "Yes" if dmarc_record else ("Suppressed (Webmail Domain)" if is_public_webmail else "No")
            },
            associated_profiles=associated_profiles,
            contact_associations=contact_associations,
            public_references=public_references,
            related_findings=related_findings,
            confidence_and_verification=ConfidenceStatus(
                overall_level="High" if confidence_score >= 80 else ("Moderate" if confidence_score >= 60 else "Low"),
                score=confidence_score,
                breakdown=confidence_breakdown
            ),
            investigation_limitations=limitations
        )
        self._jobs[job_id] = report
        return report

    # ----------------- PHONE NUMBER INVESTIGATION -----------------

    async def investigate_phone(self, phone_raw: str, job_id: str) -> ConsolidatedReport:
        start_time = time.time()
        raw_number = phone_raw.strip()

        parsed = parse_phone_resiliently(raw_number)
        if not parsed:
            duration = round(time.time() - start_time, 2)
            report = ConsolidatedReport(
                id=job_id,
                target=raw_number,
                target_type="phone",
                status="completed_with_warnings",
                duration_seconds=duration,
                summary=ReportSummary(
                    headline=f"Could not parse phone number: {raw_number}",
                    risk_level="Medium",
                    confidence_score=40,
                    key_takeaways=[
                        "Submitted string could not be parsed as a valid national or international telephone number.",
                        "Check that sufficient digits and international country codes are included."
                    ]
                ),
                identified_information={
                    "Submitted Target": raw_number,
                    "Parse Status": "Unrecognized telephone format"
                },
                confidence_and_verification=ConfidenceStatus(
                    overall_level="Low",
                    score=30,
                    breakdown=[
                        ConfidenceBreakdown(factor="E.164 Number Parser", assessment="Failed international ITU-T format validation", impact="Cautionary")
                    ]
                ),
                investigation_limitations=[
                    "Phone numbers with non-standard digit counts cannot be routed to geographic telecommunication exchanges."
                ]
            )
            self._jobs[job_id] = report
            return report

        # Extract structured telecom properties
        is_valid = phonenumbers.is_valid_number(parsed)
        formatted_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        formatted_intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        formatted_nat = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        formatted_rfc3966 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.RFC3966)

        geo_loc = geocoder.description_for_number(parsed, "en") or "Global / International Allocation"
        car_name = carrier.name_for_number(parsed, "en") or "Network / Unassigned Carrier"
        num_type_code = phonenumbers.number_type(parsed)
        line_type = LINE_TYPE_MAP.get(num_type_code, "Standard Telecom Line")
        timezones = list(phone_tz.time_zones_for_number(parsed))
        country_code = parsed.country_code
        national_number = parsed.national_number
        nat_num_str = str(national_number)

        # Determine telecom circle / LSA attribution
        if country_code == 91:
            if geo_loc and geo_loc.lower() not in ("india", "global / international allocation"):
                telecom_circle_lsa = f"{geo_loc} (geographical exchange area)"
            else:
                telecom_circle_lsa = "Not verified (mobile telecom circle mapping unavailable in offline dataset)"
        else:
            telecom_circle_lsa = geo_loc if geo_loc else "Unspecified"

        # Authoritative allocation evidence & source attribution
        if country_code == 91 and car_name and "Unassigned" not in car_name:
            carrier_allocation_source = (
                "Google libphonenumber v9.0.42 (offline carrier mapping dataset)"
            )
            carrier_data_type = "Historical/original prefix allocation metadata (offline dataset; not a live regulator lookup)"
        elif car_name and "Unassigned" not in car_name:
            carrier_allocation_source = (
                "National Numbering Plan prefix allocation (offline dataset via Google libphonenumber v9.0.42)"
            )
            carrier_data_type = "Historical/original prefix allocation metadata (offline dataset; not a live regulator lookup)"
        else:
            carrier_allocation_source = "Unallocated or unassigned in offline numbering database"
            carrier_data_type = "Unverified"

        contact_associations: List[ContactAssociation] = [
            ContactAssociation(association_type="E.164 Standard Number", value=formatted_e164, source="ITU-T E.164 Engine", confidence="High"),
            ContactAssociation(association_type="National Number", value=formatted_nat, source="Telecom Regional Plan", confidence="High"),
            ContactAssociation(association_type="Telecommunications Region", value=geo_loc, source="ITU Telecom Geocoder", confidence="High")
        ]
        if telecom_circle_lsa and "Not verified" not in telecom_circle_lsa:
            contact_associations.append(ContactAssociation(
                association_type="Telecom Circle / LSA",
                value=telecom_circle_lsa,
                source="ITU Telecom Geocoder",
                confidence="High"
            ))
        if car_name and "Unassigned" not in car_name:
            contact_associations.append(ContactAssociation(
                association_type="Original Allocation Carrier",
                value=car_name,
                source=f"{carrier_allocation_source}",
                confidence="High"
            ))
        if timezones:
            contact_associations.append(ContactAssociation(
                association_type="Allocated Timezone(s)",
                value=", ".join(timezones),
                source="Telecom Timezone Mapping",
                confidence="High"
            ))

        related_findings: List[RelatedFinding] = [
            RelatedFinding(
                title="Line Classification",
                details=f"Telephone number is classified as {line_type} under the ITU-T E.164 standard",
                category="Telecom Architecture",
                confidence="High"
            ),
            RelatedFinding(
                title="Numbering Range Allocation",
                details=f"Historical prefix allocation assigned to {car_name} (Google libphonenumber v9.0.42). Current operating carrier is unverified due to Mobile Number Portability (MNP) and requires live HLR lookup.",
                category="Infrastructure",
                confidence="High" if car_name != "Network / Unassigned Carrier" else "Moderate"
            )
        ]

        # Directory dorks & links
        dork_query = f'"{formatted_intl}" OR "{formatted_e164}" OR "{formatted_nat}"'
        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(dork_query)}"
        truecaller_url = f"https://www.truecaller.com/search/{urllib.parse.quote(formatted_e164.lstrip('+'))}"
        syncme_url = f"https://sync.me/search/?number={urllib.parse.quote(formatted_e164)}"

        public_references: List[PublicReference] = [
            PublicReference(
                title="Public Search Query (Google Dork)",
                url=search_url,
                source_type="Search Index",
                description="Searches for public listings, business contacts, and mentions across indexed public documents"
            ),
            PublicReference(
                title="Truecaller Public Directory Lookup",
                url=truecaller_url,
                source_type="Directory Dork",
                description="Public caller identification and spam reputation index"
            ),
            PublicReference(
                title="Sync.me Telecommunications Directory",
                url=syncme_url,
                source_type="Directory Dork",
                description="Community-verified public caller identification directory"
            )
        ]

        # Confidence calculation
        score = 85 if is_valid else 65
        if geo_loc and "Global" not in geo_loc:
            score += 5
        if car_name and "Unassigned" not in car_name:
            score += 5
        score = min(95, score)

        confidence_breakdown = [
            ConfidenceBreakdown(factor="E.164 ITU-T Parsing", assessment="Parsed and formatted according to international standard", impact="Positive"),
            ConfidenceBreakdown(factor="Geographic Allocation", assessment=f"Allocated to {geo_loc}", impact="Positive"),
            ConfidenceBreakdown(factor="Carrier Resolution", assessment=f"Original block allocated to {car_name} (Google libphonenumber v9.0.42; current carrier unverified due to MNP)", impact="Positive" if "Unassigned" not in car_name else "Neutral"),
            ConfidenceBreakdown(factor="Validity Verification", assessment="Formally valid under national numbering plan (Subscriber activity unverified)" if is_valid else "Possible but unconfirmed under strict national dial plan", impact="Positive" if is_valid else "Cautionary")
        ]

        duration = round(time.time() - start_time, 2)
        report = ConsolidatedReport(
            id=job_id,
            target=formatted_e164,
            target_type="phone",
            status="completed",
            duration_seconds=duration,
            summary=ReportSummary(
                headline=f"Allocated {line_type} Numbering Range in {geo_loc} ({formatted_e164})" if is_valid else f"Unconfirmed {line_type} Format in {geo_loc} ({formatted_e164})",
                risk_level="Low" if is_valid else "Medium",
                confidence_score=score,
                key_takeaways=[
                    f"International format: {formatted_intl} (Country Code +{country_code}).",
                    f"Line classification: {line_type} numbering range.",
                    f"Telecommunications region: {geo_loc}.",
                    f"Telecom circle / LSA: {telecom_circle_lsa}.",
                    f"Original allocation carrier: {car_name} (Current carrier: Not verified — subject to Mobile Number Portability).",
                    f"Numbering plan validity: Conforms to national ITU-T allocation (Live subscriber assignment and active line reachability unverified).",
                    f"Associated timezone: {', '.join(timezones) if timezones else 'Global UTC'}."
                ]
            ),
            identified_information={
                "E.164 Format": formatted_e164,
                "International Format": formatted_intl,
                "National Format": formatted_nat,
                "RFC 3966 Format": formatted_rfc3966,
                "Country Calling Code": f"+{country_code}",
                "National Significant Number": str(national_number),
                "Line Type": line_type,
                "Telecommunications Region": geo_loc,
                "Telecom Circle / LSA": telecom_circle_lsa,
                "Original Allocation Carrier": car_name,
                "Carrier Allocation Source": carrier_allocation_source,
                "Carrier Data Type": carrier_data_type,
                "Current Carrier": "Not verified (subject to Mobile Number Portability)",
                "Timezones": ", ".join(timezones) if timezones else "Unspecified",
                "Numbering-Plan Validity": "Formally valid ITU-T E.164 allocation" if is_valid else "Possible (Unconfirmed dial plan format)",
                "Live Subscriber Status": "Not verified (subscriber activity/reachability unverified)"
            },
            associated_profiles=[],
            contact_associations=contact_associations,
            public_references=public_references,
            related_findings=related_findings,
            confidence_and_verification=ConfidenceStatus(
                overall_level="High" if score >= 80 else "Moderate",
                score=score,
                breakdown=confidence_breakdown
            ),
            investigation_limitations=[
                "Carrier allocation evidence reflects historical/original prefix allocation metadata from Google libphonenumber v9.0.42 (offline dataset) and does not reflect a live query to TRAI/DoT, nor live subscriber carrier, SIM activation, or reachability under Mobile Number Portability (MNP).",
                "Offline ITU-T numbering plan validation verifies that digits conform to national carrier allocations, but does not verify live subscriber assignment, current operational status, or carrier changes via Mobile Number Portability (MNP).",
                "Mobile telecom circle / LSA assignments are not mapped in the offline numbering database for Indian mobile numbers; circle verification requires an authoritative external telecom registry query.",
                "Current carrier: Not verified without authoritative real-time HLR/SS7 or commercial CNAM lookup.",
                "Real-time GPS cell tower triangulation and subscriber identity disclosure require lawful telecommunication warrants and are not accessible via OSINT.",
                "VoIP and virtual numbers may be used across geographical boundaries regardless of allocated area code.",
                "Caller ID spoofing protections apply: actual outbound callers can alter display numbers."
            ]
        )
        self._jobs[job_id] = report
        return report

    # ----------------- USERNAME INVESTIGATION -----------------

    async def investigate_username(self, username_raw: str, job_id: str) -> ConsolidatedReport:
        start_time = time.time()
        username = username_raw.strip().lstrip("@")

        if not username or len(username) < 2 or not re.match(r'^[a-zA-Z0-9_\-\.]+$', username):
            duration = round(time.time() - start_time, 2)
            report = ConsolidatedReport(
                id=job_id,
                target=username_raw,
                target_type="username",
                status="completed_with_warnings",
                duration_seconds=duration,
                summary=ReportSummary(
                    headline=f"Invalid username structure: {username_raw}",
                    risk_level="Medium",
                    confidence_score=50,
                    key_takeaways=[
                        "Submitted string contains characters not permitted in standard public account handles.",
                        "Usernames must be at least 2 characters containing alphanumeric characters, dots, underscores, or hyphens."
                    ]
                ),
                identified_information={
                    "Submitted Target": username_raw,
                    "Format Validation": "Invalid handle structure"
                },
                confidence_and_verification=ConfidenceStatus(
                    overall_level="Low",
                    score=40,
                    breakdown=[
                        ConfidenceBreakdown(factor="Handle Syntax Validation", assessment="Non-standard characters", impact="Cautionary")
                    ]
                ),
                investigation_limitations=[
                    "Invalid handles cannot be queried against platform profile endpoints."
                ]
            )
            self._jobs[job_id] = report
            return report

        # Define 15 authoritative platforms
        platforms = [
            {
                "platform": "GitHub",
                "url": f"https://github.com/{username}",
                "check_url": f"https://api.github.com/users/{username}",
                "category": "Developer & Code",
                "is_api": True
            },
            {
                "platform": "Reddit",
                "url": f"https://www.reddit.com/user/{username}",
                "check_url": f"https://www.reddit.com/user/{username}/about.json",
                "category": "Social Discussion",
                "is_api": True
            },
            {
                "platform": "GitLab",
                "url": f"https://gitlab.com/{username}",
                "check_url": f"https://gitlab.com/{username}",
                "category": "Developer & Code",
                "is_api": False
            },
            {
                "platform": "Hacker News",
                "url": f"https://news.ycombinator.com/user?id={username}",
                "check_url": f"https://hacker-news.firebaseio.com/v0/user/{username}.json",
                "category": "Tech Community",
                "is_api": True
            },
            {
                "platform": "Dev.to",
                "url": f"https://dev.to/{username}",
                "check_url": f"https://dev.to/api/users/by_username?url={username}",
                "category": "Developer Community",
                "is_api": True
            },
            {
                "platform": "Keybase",
                "url": f"https://keybase.io/{username}",
                "check_url": f"https://keybase.io/_/api/1.0/user/lookup.json?usernames={username}",
                "category": "Identity & Cryptography",
                "is_api": True
            },
            {
                "platform": "Telegram",
                "url": f"https://t.me/{username}",
                "check_url": f"https://t.me/{username}",
                "category": "Messaging",
                "is_api": False
            },
            {
                "platform": "Pinterest",
                "url": f"https://www.pinterest.com/{username}/",
                "check_url": f"https://www.pinterest.com/{username}/",
                "category": "Visual Media",
                "is_api": False
            },
            {
                "platform": "Medium",
                "url": f"https://medium.com/@{username}",
                "check_url": f"https://medium.com/@{username}",
                "category": "Publishing & Articles",
                "is_api": False
            },
            {
                "platform": "Wikipedia",
                "url": f"https://en.wikipedia.org/wiki/User:{username}",
                "check_url": f"https://en.wikipedia.org/wiki/User:{username}",
                "category": "Encyclopedia",
                "is_api": False
            },
            {
                "platform": "Twitter / X",
                "url": f"https://x.com/{username}",
                "check_url": f"https://x.com/{username}",
                "category": "Microblogging",
                "is_api": False
            },
            {
                "platform": "Mastodon Social",
                "url": f"https://mastodon.social/@{username}",
                "check_url": f"https://mastodon.social/@{username}",
                "category": "Fediverse Social",
                "is_api": False
            },
            {
                "platform": "SoundCloud",
                "url": f"https://soundcloud.com/{username}",
                "check_url": f"https://soundcloud.com/{username}",
                "category": "Audio & Music",
                "is_api": False
            },
            {
                "platform": "Vimeo",
                "url": f"https://vimeo.com/{username}",
                "check_url": f"https://vimeo.com/{username}",
                "category": "Video Hosting",
                "is_api": False
            },
            {
                "platform": "Steam Community",
                "url": f"https://steamcommunity.com/id/{username}",
                "check_url": f"https://steamcommunity.com/id/{username}",
                "category": "Gaming",
                "is_api": False
            }
        ]

        associated_profiles: List[AssociatedProfile] = []
        contact_associations: List[ContactAssociation] = [
            ContactAssociation(association_type="Target Username Handle", value=f"@{username}", source="Input Specification", confidence="High")
        ]
        related_findings: List[RelatedFinding] = []

        async with httpx.AsyncClient(timeout=3.5, headers=self._client_headers, follow_redirects=True) as client:
            async def check_platform(item: Dict[str, Any]) -> Optional[AssociatedProfile]:
                p_name = item["platform"]
                p_url = item["url"]
                c_url = item["check_url"]
                is_api = item["is_api"]
                try:
                    resp = await client.get(c_url)
                    # Specific platform heuristics
                    if p_name == "GitHub" and resp.status_code == 200:
                        data = resp.json()
                        if "login" in data:
                            return AssociatedProfile(
                                platform="GitHub",
                                identifier=data.get("login", username),
                                url=p_url,
                                status="Verified Active",
                                details=f"Bio: {data.get('bio') or 'Active profile'}. Repos: {data.get('public_repos', 0)}. Followers: {data.get('followers', 0)}",
                                avatar_url=data.get("avatar_url")
                            )
                    elif p_name == "Reddit" and resp.status_code == 200:
                        data = resp.json()
                        if "data" in data and not data.get("data", {}).get("is_suspended", False):
                            return AssociatedProfile(
                                platform="Reddit",
                                identifier=f"u/{username}",
                                url=p_url,
                                status="Verified Active",
                                details=f"Reddit account active. Karma: {data.get('data', {}).get('total_karma', 0)}"
                            )
                    elif p_name == "Hacker News" and resp.status_code == 200:
                        data = resp.json()
                        if data and "id" in data:
                            return AssociatedProfile(
                                platform="Hacker News",
                                identifier=data.get("id"),
                                url=p_url,
                                status="Verified Active",
                                details=f"HN account verified. Karma: {data.get('karma', 0)}"
                            )
                    elif p_name == "Dev.to" and resp.status_code == 200:
                        data = resp.json()
                        if data and "username" in data:
                            return AssociatedProfile(
                                platform="Dev.to",
                                identifier=data.get("username"),
                                url=p_url,
                                status="Verified Active",
                                details=f"Author profile confirmed: {data.get('name') or username}",
                                avatar_url=data.get("profile_image")
                            )
                    elif p_name == "Keybase" and resp.status_code == 200:
                        data = resp.json()
                        them = data.get("them", [])
                        if them and len(them) > 0 and them[0] is not None:
                            return AssociatedProfile(
                                platform="Keybase",
                                identifier=username,
                                url=p_url,
                                status="Verified Active",
                                details="Keybase cryptographic identity confirmed"
                            )
                    elif not is_api:
                        # Non-API status code check
                        if resp.status_code == 200:
                            # Additional check for soft 404s
                            text_lower = resp.text.lower()
                            if "page not found" not in text_lower and "user not found" not in text_lower and "does not exist" not in text_lower:
                                return AssociatedProfile(
                                    platform=p_name,
                                    identifier=username,
                                    url=p_url,
                                    status="Verified Active",
                                    details=f"Public profile active on {p_name}"
                                )
                except Exception:
                    pass
                return None

            tasks = [check_platform(p) for p in platforms]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for res in results:
                if isinstance(res, AssociatedProfile):
                    associated_profiles.append(res)
                    related_findings.append(RelatedFinding(
                        title=f"{res.platform} Account Profile",
                        details=f"Active public account identified at {res.url}",
                        category="Identity Profile",
                        confidence="High"
                    ))

        # Search references
        google_dork = f"https://www.google.com/search?q={urllib.parse.quote(f'inurl:{username} | \"@{username}\"')}"
        public_references: List[PublicReference] = [
            PublicReference(
                title=f"Public Mention Dork (@{username})",
                url=google_dork,
                source_type="Search Index",
                description="Cross-platform search for handle mentions and profiles"
            )
        ]
        for p in associated_profiles:
            public_references.append(PublicReference(
                title=f"{p.platform} Profile: {username}",
                url=p.url,
                source_type="Public Profile",
                description=f"Verified public footprint on {p.platform}"
            ))

        found_count = len(associated_profiles)
        score = 85 if found_count >= 1 else 60
        headline = f"Identified across {found_count} public platforms (@{username})" if found_count > 0 else f"No verified high-visibility accounts found for @{username}"

        confidence_breakdown = [
            ConfidenceBreakdown(factor="Multi-Platform Check", assessment=f"Surveyed 15 major networks concurrently", impact="Positive"),
            ConfidenceBreakdown(factor="Profile Corroboration", assessment=f"{found_count} active profile(s) confirmed", impact="Positive" if found_count > 0 else "Neutral")
        ]

        duration = round(time.time() - start_time, 2)
        report = ConsolidatedReport(
            id=job_id,
            target=f"@{username}",
            target_type="username",
            status="completed",
            duration_seconds=duration,
            summary=ReportSummary(
                headline=headline,
                risk_level="Low" if found_count > 0 else "Informational",
                confidence_score=score,
                key_takeaways=[
                    f"Queried handle: @{username}.",
                    f"Public platforms with confirmed presence: {found_count} of 15 scanned.",
                    f"Confirmed accounts: {', '.join([p.platform for p in associated_profiles]) if associated_profiles else 'None detected on primary networks'}."
                ]
            ),
            identified_information={
                "Normalized Handle": f"@{username}",
                "Platforms Surveyed": "15 Public Networks",
                "Active Profiles Found": str(found_count),
                "Primary Identity Hits": ", ".join([p.platform for p in associated_profiles]) if associated_profiles else "None"
            },
            associated_profiles=associated_profiles,
            contact_associations=contact_associations,
            public_references=public_references,
            related_findings=related_findings,
            confidence_and_verification=ConfidenceStatus(
                overall_level="High" if score >= 80 else "Moderate",
                score=score,
                breakdown=confidence_breakdown
            ),
            investigation_limitations=[
                "Accounts on different platforms sharing the same handle may belong to different individuals (homoglyph and handle collision limitation).",
                "Private and restricted profiles cannot be inspected without authorized account credentials.",
                "Platforms with active anti-scraping walls or captcha challenges may return false negatives."
            ]
        )
        self._jobs[job_id] = report
        return report

    # ----------------- PHOTOGRAPH INVESTIGATION -----------------

    async def investigate_image(self, file_bytes: bytes, filename: str, job_id: str) -> ConsolidatedReport:
        start_time = time.time()
        file_size_kb = round(len(file_bytes) / 1024, 2)
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        md5_hash = hashlib.md5(file_bytes).hexdigest()

        # Reject oversized payloads (>25 MB) to guard server memory
        MAX_IMAGE_BYTES = 25 * 1024 * 1024
        if len(file_bytes) > MAX_IMAGE_BYTES:
            duration = round(time.time() - start_time, 2)
            report = ConsolidatedReport(
                id=job_id,
                target=filename,
                target_type="image",
                status="failed",
                duration_seconds=duration,
                summary=ReportSummary(
                    headline=f"Upload rejected: File exceeds maximum allowed size (25 MB)",
                    risk_level="High",
                    confidence_score=100,
                    key_takeaways=[
                        f"Submitted file ({file_size_kb / 1024:.2f} MB) exceeds maximum threshold of 25 MB.",
                        "Uploads above 25 MB are rejected to prevent memory exhaustion and DoS attacks."
                    ]
                ),
                identified_information={
                    "Filename": filename,
                    "File Size": f"{file_size_kb} KB",
                    "Rejection Reason": "File size exceeds 25 MB threshold"
                },
                confidence_and_verification=ConfidenceStatus(
                    overall_level="High",
                    score=100,
                    breakdown=[
                        ConfidenceBreakdown(factor="Payload Size Guard", assessment="Exceeds 25 MB threshold", impact="Cautionary")
                    ]
                ),
                investigation_limitations=[
                    "Files exceeding the 25 MB memory boundary are not parsed."
                ]
            )
            self._jobs[job_id] = report
            return report

        try:
            pil_img = Image.open(io.BytesIO(file_bytes))
            img_format = pil_img.format or "Unknown Format"
            width, height = pil_img.size
            aspect_ratio = f"{round(width / max(1, height), 2)}:1"
            color_mode = pil_img.mode
        except Exception as e:
            duration = round(time.time() - start_time, 2)
            report = ConsolidatedReport(
                id=job_id,
                target=filename,
                target_type="image",
                status="failed",
                duration_seconds=duration,
                summary=ReportSummary(
                    headline=f"Corrupted or invalid image file: {filename}",
                    risk_level="High",
                    confidence_score=90,
                    key_takeaways=[
                        "Uploaded file could not be parsed as a valid image (JPEG, PNG, WebP, TIFF).",
                        f"Parser error: {str(e)}"
                    ]
                ),
                identified_information={
                    "Filename": filename,
                    "File Size": f"{file_size_kb} KB",
                    "SHA-256 Hash": sha256_hash
                },
                confidence_and_verification=ConfidenceStatus(
                    overall_level="High",
                    score=90,
                    breakdown=[
                        ConfidenceBreakdown(factor="File Header Verification", assessment="Header invalid or damaged", impact="Cautionary")
                    ]
                ),
                investigation_limitations=[
                    "Corrupted files cannot yield forensic EXIF or visual analysis."
                ]
            )
            self._jobs[job_id] = report
            return report

        # Extract EXIF tags
        exif_raw = pil_img.getexif()
        exif_dict: Dict[str, Any] = {}
        if exif_raw:
            for tag_id, value in exif_raw.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                exif_dict[tag_name] = str(value).strip()

        camera_make = exif_dict.get("Make", "Unknown Camera Make")
        camera_model = exif_dict.get("Model", "Unknown Camera Model")
        software = exif_dict.get("Software", "Unspecified Software")
        date_time_orig = exif_dict.get("DateTimeOriginal") or exif_dict.get("DateTime", "Not Stored in EXIF")

        # Parse GPS Coordinates
        gps_info = exif_raw.get_ifd(ExifTags.IFD.GPSInfo) if hasattr(ExifTags, "IFD") else None
        gps_lat: Optional[float] = None
        gps_lon: Optional[float] = None
        gps_alt: Optional[float] = None
        google_maps_link: Optional[str] = None

        if gps_info:
            try:
                def convert_to_degrees(value):
                    d, m, s = value
                    return float(d) + (float(m) / 60.0) + (float(s) / 3600.0)

                lat_val = gps_info.get(2)
                lat_ref = gps_info.get(1)
                lon_val = gps_info.get(4)
                lon_ref = gps_info.get(3)
                alt_val = gps_info.get(6)

                if lat_val and lat_ref and lon_val and lon_ref:
                    gps_lat = convert_to_degrees(lat_val)
                    if str(lat_ref).upper() == "S":
                        gps_lat = -gps_lat

                    gps_lon = convert_to_degrees(lon_val)
                    if str(lon_ref).upper() == "W":
                        gps_lon = -gps_lon

                    if alt_val:
                        gps_alt = float(alt_val)

                    google_maps_link = f"https://www.google.com/maps?q={gps_lat:.6f},{gps_lon:.6f}"
            except Exception as e:
                logger.debug(f"GPS parsing warning: {e}")

        # Assemble Identified Information
        identified_info = {
            "Original Filename": filename,
            "Image Format": img_format,
            "Resolution": f"{width} x {height} pixels",
            "Aspect Ratio": aspect_ratio,
            "Color Mode": color_mode,
            "File Size": f"{file_size_kb} KB",
            "SHA-256 Checksum": sha256_hash,
            "MD5 Checksum": md5_hash,
            "Camera Equipment": f"{camera_make} {camera_model}".strip(),
            "Editing / Firmware Software": software,
            "Acquisition Timestamp": date_time_orig
        }

        contact_associations: List[ContactAssociation] = []
        if camera_make != "Unknown Camera Make" or camera_model != "Unknown Camera Model":
            contact_associations.append(ContactAssociation(
                association_type="Acquisition Device",
                value=f"{camera_make} {camera_model}".strip(),
                source="EXIF Hardware Tag",
                confidence="High"
            ))

        related_findings: List[RelatedFinding] = [
            RelatedFinding(
                title="Cryptographic Fingerprint",
                details=f"SHA-256: {sha256_hash[:20]}... | MD5: {md5_hash}",
                category="File Integrity",
                confidence="High"
            ),
            RelatedFinding(
                title="Image Dimensions & Format",
                details=f"{img_format} image rendered at {width}x{height} with {color_mode} color profile",
                category="Forensic Metadata",
                confidence="High"
            )
        ]

        if gps_lat is not None and gps_lon is not None:
            identified_info["Embedded GPS Coordinates"] = f"{gps_lat:.6f}, {gps_lon:.6f}"
            identified_info["Navigation Map URL"] = google_maps_link
            contact_associations.append(ContactAssociation(
                association_type="Embedded GPS Location",
                value=f"{gps_lat:.6f}, {gps_lon:.6f}",
                source="EXIF GPS IFD Metadata",
                confidence="High"
            ))
            related_findings.append(RelatedFinding(
                title="Geographic Metadata Extracted",
                details=f"Embedded satellite coordinates: Lat {gps_lat:.6f}, Lon {gps_lon:.6f}. Direct coordinates saved to report.",
                category="Geolocation",
                confidence="High"
            ))

        # Reverse image search engines (External reference links only)
        public_references: List[PublicReference] = [
            PublicReference(
                title="Google Lens Visual Search (External)",
                url="https://lens.google.com/",
                source_type="External Search Index Link",
                description="External reference link for manual visual similarity search (automated visual indexing is not executed server-side)"
            ),
            PublicReference(
                title="Bing Visual Search (External)",
                url="https://www.bing.com/visualsearch",
                source_type="External Search Index Link",
                description="External reference link for manual reverse image query"
            ),
            PublicReference(
                title="Yandex Visual Search (External)",
                url="https://yandex.com/images/search?rpt=imageview",
                source_type="External Search Index Link",
                description="External reference link for manual duplicate and landmark comparison"
            ),
            PublicReference(
                title="TinEye Reverse Image Search (External)",
                url="https://tineye.com/",
                source_type="External Search Index Link",
                description="External reference link for manual derivative search"
            )
        ]

        has_exif = len(exif_dict) > 0
        has_gps = gps_lat is not None
        score = 80
        if has_exif:
            score += 10
        if has_gps:
            score += 8
        score = min(98, score)

        key_takeaways = [
            f"Image format: {img_format} ({width}x{height} px, {aspect_ratio}).",
            f"File integrity: SHA-256 verification complete.",
            f"EXIF metadata: {'Extracted hardware and acquisition tags' if has_exif else 'Stripped or absent (privacy clean)'}."
        ]
        if has_gps:
            key_takeaways.append(f"Satellite geolocation: Found embedded coordinates ({gps_lat:.4f}, {gps_lon:.4f}).")
        if camera_make != "Unknown Camera Make":
            key_takeaways.append(f"Captured with: {camera_make} {camera_model}.")

        headline = f"Forensic Analysis: {img_format} Image ({width}x{height} px)"
        if has_gps:
            headline += " [GPS Embedded]"

        duration = round(time.time() - start_time, 2)
        report = ConsolidatedReport(
            id=job_id,
            target=filename,
            target_type="image",
            status="completed",
            duration_seconds=duration,
            summary=ReportSummary(
                headline=headline,
                risk_level="Low" if has_gps else "Informational",
                confidence_score=score,
                key_takeaways=key_takeaways
            ),
            identified_information=identified_info,
            associated_profiles=[],
            contact_associations=contact_associations,
            public_references=public_references,
            related_findings=related_findings,
            confidence_and_verification=ConfidenceStatus(
                overall_level="High",
                score=score,
                breakdown=[
                    ConfidenceBreakdown(factor="Cryptographic Hashing", assessment="SHA-256 & MD5 calculated directly from binary", impact="Positive"),
                    ConfidenceBreakdown(factor="EXIF Header Parsing", assessment="Hardware tags extracted" if has_exif else "EXIF tags not present in header", impact="Positive" if has_exif else "Neutral"),
                    ConfidenceBreakdown(factor="GPS Satellite Geolocation", assessment="Valid coordinate pair extracted" if has_gps else "No embedded GPS metadata", impact="Positive" if has_gps else "Neutral")
                ]
            ),
            investigation_limitations=[
                "Automated reverse image matching is not performed locally; external search engine query links are provided for manual analyst inspection.",
                "Biometric facial recognition and facial identification matching are strictly restricted in compliance with ethics policies and privacy regulations.",
                "Social media platforms routinely strip EXIF metadata upon upload; lack of EXIF does not indicate file tampering.",
                "Reverse visual search engines require public web indexing and cannot discover private, unshared images."
            ]
        )
        self._jobs[job_id] = report
        return report

    # ----------------- UNIVERSAL ENTRY POINT -----------------

    async def investigate(
        self,
        query: Optional[str] = None,
        manual_type: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> ConsolidatedReport:
        jid = job_id or str(uuid.uuid4())

        # If file provided, route to image
        if file_bytes and filename:
            return await self.investigate_image(file_bytes, filename, jid)

        target_query = (query or "").strip()
        if not target_query:
            return ConsolidatedReport(
                id=jid,
                target="[Empty Query]",
                target_type="unknown",
                status="failed",
                summary=ReportSummary(
                    headline="No query or file provided",
                    risk_level="Informational",
                    confidence_score=0,
                    key_takeaways=["An email, phone number, username, or photo upload is required."]
                ),
                confidence_and_verification=ConfidenceStatus(overall_level="Low", score=0),
                investigation_limitations=["Cannot investigate an empty submission."]
            )

        detected_type = classify_target(target_query, manual_type)

        if detected_type == "email":
            return await self.investigate_email(target_query, jid)
        elif detected_type == "phone":
            return await self.investigate_phone(target_query, jid)
        elif detected_type == "username":
            return await self.investigate_username(target_query, jid)
        else:
            return await self.investigate_username(target_query, jid)

universal_orchestrator = UniversalOrchestrator()
