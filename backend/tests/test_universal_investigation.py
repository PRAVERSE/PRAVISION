import io
import pytest
import pytest_asyncio
from PIL import Image, ExifTags
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.auth.auth_service import auth_service
from app.intelligence.universal_orchestrator import (
    universal_orchestrator,
    classify_target,
    DISPOSABLE_EMAIL_DOMAINS
)

@pytest.mark.asyncio
async def test_classify_target_logic():
    # Email detection
    assert classify_target("analyst@pravision.org") == "email"
    assert classify_target("test.user+tag@domain.co.uk") == "email"

    # Phone detection with and without +
    assert classify_target("+14155552671") == "phone"
    assert classify_target("14155552671") == "phone"
    assert classify_target("+44 20 7183 8750") == "phone"
    assert classify_target("(415) 555-2671") == "phone"

    # Username detection
    assert classify_target("torvalds") == "username"
    assert classify_target("@octocat") == "username"

    # Image extension detection
    assert classify_target("evidence.jpg") == "image"
    assert classify_target("capture.PNG") == "image"

    # Manual override
    assert classify_target("14155552671", manual_override="username") == "username"
    assert classify_target("user@domain.com", manual_override="email") == "email"


@pytest.mark.asyncio
async def test_email_investigation_valid():
    report = await universal_orchestrator.investigate(query="security@google.com", manual_type="email")
    assert report.target == "security@google.com"
    assert report.target_type == "email"
    assert report.status == "completed"
    assert "Google Workspace / Gmail" in report.summary.headline or "Active" in report.summary.headline
    assert report.summary.confidence_score >= 70
    assert "Target Address" in report.identified_information
    assert report.identified_information["Disposable Mail Service"] == "No (Legitimate Domain)"
    assert len(report.public_references) >= 1
    assert len(report.investigation_limitations) >= 1


@pytest.mark.asyncio
async def test_email_investigation_disposable():
    report = await universal_orchestrator.investigate(query="test_victim@mailinator.com", manual_type="email")
    assert report.target_type == "email"
    assert report.summary.risk_level == "High"
    assert report.identified_information["Disposable Mail Service"] == "Yes (High Risk)"


@pytest.mark.asyncio
async def test_email_investigation_malformed():
    report = await universal_orchestrator.investigate(query="not-an-email", manual_type="email")
    assert report.status == "completed_with_warnings"
    assert report.identified_information["Syntax RFC Compliant"] is False


@pytest.mark.asyncio
async def test_phone_investigation_with_plus():
    report = await universal_orchestrator.investigate(query="+14155552671", manual_type="phone")
    assert report.target_type == "phone"
    assert report.status == "completed"
    assert report.identified_information["E.164 Format"] == "+14155552671"
    assert "San Francisco" in report.identified_information["Telecommunications Region"]
    assert "America/Los_Angeles" in report.identified_information["Timezones"]
    assert report.identified_information["Country Calling Code"] == "+1"
    assert len(report.public_references) >= 2


@pytest.mark.asyncio
async def test_phone_investigation_without_plus():
    # Number entered without leading + must resolve correctly without throwing NumberParseException
    report = await universal_orchestrator.investigate(query="14155552671", manual_type="phone")
    assert report.target_type == "phone"
    assert report.status == "completed"
    assert report.identified_information["E.164 Format"] == "+14155552671"
    assert "San Francisco" in report.identified_information["Telecommunications Region"]


@pytest.mark.asyncio
async def test_phone_investigation_invalid():
    report = await universal_orchestrator.investigate(query="123", manual_type="phone")
    assert report.status == "completed_with_warnings"
    assert "Unrecognized telephone format" in report.identified_information.get("Parse Status", "")


@pytest.mark.asyncio
async def test_username_investigation_valid():
    report = await universal_orchestrator.investigate(query="@torvalds", manual_type="username")
    assert report.target == "@torvalds"
    assert report.target_type == "username"
    assert report.status == "completed"
    assert report.summary.confidence_score >= 60
    assert "Normalized Handle" in report.identified_information
    assert len(report.investigation_limitations) >= 1


@pytest.mark.asyncio
async def test_image_investigation_valid_jpeg():
    # Create valid in-memory image
    img = Image.new("RGB", (640, 480), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    img_bytes = buf.getvalue()

    report = await universal_orchestrator.investigate(
        file_bytes=img_bytes,
        filename="recon_target.jpg"
    )

    assert report.target == "recon_target.jpg"
    assert report.target_type == "image"
    assert report.status == "completed"
    assert report.identified_information["Image Format"] == "JPEG"
    assert report.identified_information["Resolution"] == "640 x 480 pixels"
    assert len(report.identified_information["SHA-256 Checksum"]) == 64
    assert len(report.identified_information["MD5 Checksum"]) == 32
    # Verify ethical limitation statement exists
    assert any("facial recognition" in lim.lower() for lim in report.investigation_limitations)


@pytest.mark.asyncio
async def test_image_investigation_corrupted_file():
    corrupted_bytes = b"not-a-valid-image-header"
    report = await universal_orchestrator.investigate(
        file_bytes=corrupted_bytes,
        filename="broken.jpg"
    )
    assert report.status == "failed"
    assert "Corrupted or invalid" in report.summary.headline


@pytest.mark.asyncio
async def test_universal_api_endpoints_and_auth():
    from app.auth.auth_service import create_jwt_token, get_env_auth_credentials
    cfg_user, cfg_pwd, _ = get_env_auth_credentials()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated request to protected universal investigate endpoint -> 401
        unauth_resp = await client.post("/api/investigate/universal", json={"query": "test@example.com"})
        assert unauth_resp.status_code == 401

        # 2. Authenticate using valid token
        token = create_jwt_token(user_id="test-admin-id", username=cfg_user or "admin", role="admin")
        headers = {"Authorization": f"Bearer {token}"}

        # Also test login route if credentials configured
        if cfg_user and cfg_pwd:
            login_resp = await client.post("/api/auth/login", json={
                "username": cfg_user,
                "password": cfg_pwd
            })
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

        # 3. Authenticated JSON query
        auth_resp = await client.post("/api/investigate/universal", headers=headers, json={
            "query": "14155552671",
            "type": "phone"
        })
        assert auth_resp.status_code == 200
        data = auth_resp.json()
        assert data["target_type"] == "phone"
        assert data["status"] == "completed"
        job_id = data["id"]

        # 4. GET /api/investigate/jobs/{job_id}
        job_resp = await client.get(f"/api/investigate/jobs/{job_id}", headers=headers)
        assert job_resp.status_code == 200
        assert job_resp.json()["id"] == job_id

        # 5. GET /api/investigate/history
        history_resp = await client.get("/api/investigate/history", headers=headers)
        assert history_resp.status_code == 200
        assert "history" in history_resp.json()
        assert len(history_resp.json()["history"]) >= 1


import dns.resolver
from unittest.mock import patch, MagicMock
from app.build_identity import (
    validate_commit_sha,
    get_build_commit_sha,
    resolve_deployment_identity,
    generate_build_metadata
)

def test_build_identity_unit():
    valid_sha_1 = "b64ace5664432724530d7f080df1a7fb6b037810"
    valid_sha_parent = "e010a0f8034b1add1882e33ccc26c794a11b079f"
    valid_sha_env = "1111111111111111111111111111111111111111"

    # Strict 40-character regex validation
    assert validate_commit_sha(valid_sha_1) == valid_sha_1
    assert validate_commit_sha(valid_sha_1.upper()) == valid_sha_1
    assert validate_commit_sha("86cf692") is None  # truncated
    assert validate_commit_sha("b64ace5664432724530d7f080df1a7fb6b037810extra") is None  # too long
    assert validate_commit_sha("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz") is None  # non-hex
    assert validate_commit_sha("") is None
    assert validate_commit_sha(None) is None

    # Test 1: Correct metadata SHA matching Git (sources agree)
    with patch.dict("os.environ", {}, clear=True), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("pathlib.Path.read_text", return_value=f'{{"commit_sha": "{valid_sha_1}"}}'), \
         patch("subprocess.check_output", return_value=valid_sha_1.encode("utf-8")):
        ident = resolve_deployment_identity()
        assert ident.identity_status == "verified"
        assert ident.sources_agree is True
        assert ident.commit_sha == valid_sha_1
        assert get_build_commit_sha() == valid_sha_1

    # Test 2: Parent SHA accidentally present in metadata while Git has current commit (mismatch detected!)
    with patch.dict("os.environ", {}, clear=True), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("pathlib.Path.read_text", return_value=f'{{"commit_sha": "{valid_sha_parent}"}}'), \
         patch("subprocess.check_output", return_value=valid_sha_1.encode("utf-8")):
        ident = resolve_deployment_identity()
        assert ident.identity_status == "mismatch"
        assert ident.sources_agree is False
        assert ident.commit_sha == "mismatch"
        assert "conflict detected" in ident.details
        assert get_build_commit_sha() == "mismatch"

    # Test 3: Environment variable and metadata disagreement (mismatch detected!)
    with patch.dict("os.environ", {"PRAVISION_COMMIT_SHA": valid_sha_env}), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("pathlib.Path.read_text", return_value=f'{{"commit_sha": "{valid_sha_1}"}}'), \
         patch("subprocess.check_output", side_effect=Exception("No git")):
        ident = resolve_deployment_identity()
        assert ident.identity_status == "mismatch"
        assert ident.sources_agree is False
        assert ident.commit_sha == "mismatch"

    # Test 4: Git unavailable (e.g. Docker container without .git), reads metadata
    with patch.dict("os.environ", {}, clear=True), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("pathlib.Path.read_text", return_value=f'{{"commit_sha": "{valid_sha_1}"}}'), \
         patch("subprocess.check_output", side_effect=Exception("No git")):
        ident = resolve_deployment_identity()
        assert ident.identity_status == "verified"
        assert ident.sources_agree is True
        assert ident.commit_sha == valid_sha_1

    # Test 5: Invalid or missing SHA (all sources fail/empty)
    with patch.dict("os.environ", {}, clear=True), \
         patch("pathlib.Path.is_file", return_value=False), \
         patch("subprocess.check_output", side_effect=Exception("No git")):
        ident = resolve_deployment_identity()
        assert ident.identity_status == "unavailable"
        assert ident.sources_agree is False
        assert ident.commit_sha == "unknown"


@pytest.mark.asyncio
async def test_email_mx_and_routing_assessments():
    # 1. Ordinary MX records (explicit_mx)
    mock_ord_mx = MagicMock()
    mock_ord_mx.preference = 10
    mock_ord_mx.exchange = "mail.customdomain.org."
    with patch("dns.resolver.Resolver.resolve", return_value=[mock_ord_mx]):
        report = await universal_orchestrator.investigate("user@customdomain.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "answered"
        assert info["MX Routing Status"] == "resolved"
        assert info["Mail Routing Assessment"] == "explicit_mx"
        assert info["Mail Routing Description"] == "Explicit MX Configured"
        assert "mail.customdomain.org" in info["MX Records"]
        assert "Successfully resolved 1 authoritative MX host(s)" in info["MX Resolution Details"]

    # 2. Valid single-record Null MX (null_mx)
    mock_null_mx = MagicMock()
    mock_null_mx.preference = 0
    mock_null_mx.exchange = "."
    with patch("dns.resolver.Resolver.resolve", return_value=[mock_null_mx]):
        report = await universal_orchestrator.investigate("user@null-mx-domain.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "answered"
        assert info["MX Routing Status"] == "resolved"
        assert info["Mail Routing Assessment"] == "null_mx"
        assert "Null MX (RFC 7505" in info["MX Records"]
        assert "Domain Rejects Mail (RFC 7505 Null MX)" in report.summary.headline
        assert report.summary.risk_level == "High"

    # 3. Mixed Null MX and ordinary MX records (malformed_configuration)
    mock_null = MagicMock()
    mock_null.preference = 0
    mock_null.exchange = "."
    mock_ordinary = MagicMock()
    mock_ordinary.preference = 10
    mock_ordinary.exchange = "mail.example.com."
    with patch("dns.resolver.Resolver.resolve", return_value=[mock_null, mock_ordinary]):
        report = await universal_orchestrator.investigate("user@mixed-mx-domain.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "answered"
        assert info["MX Routing Status"] == "resolved"
        assert info["Mail Routing Assessment"] == "malformed_configuration"
        assert "Protocol Violation: Mixed Null MX and Ordinary MX" in info["Mail Routing Description"]
        assert "Malformed Configuration" in info["MX Records"]
        assert "mail.example.com" in info["MX Resolution Details"]
        assert report.summary.risk_level == "High"

    # 4. Both address lookups returning NoAnswer (no_route)
    def mock_noanswer_both(domain, qtype):
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_noanswer_both):
        report = await universal_orchestrator.investigate("user@existingdomain-no-records.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "answered"
        assert info["MX Routing Status"] == "resolved"
        assert info["Mail Routing Assessment"] == "no_route"
        assert info["Mail Routing Description"] == "No MX or Address Records Published"
        assert "None Published (No MX or Address Records)" in info["MX Records"]

    # 5. Clean A/AAAA address resolution after MX NoAnswer (implicit_mx_candidate)
    def mock_noanswer_clean_a(domain, qtype):
        if qtype == "MX":
            raise dns.resolver.NoAnswer()
        elif qtype == "A":
            return ["93.184.216.34"]
        elif qtype == "AAAA":
            raise dns.resolver.NoAnswer()
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_noanswer_clean_a):
        report = await universal_orchestrator.investigate("user@domain-with-a.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "answered"
        assert info["MX Routing Status"] == "resolved"
        assert info["Mail Routing Assessment"] == "implicit_mx_candidate"
        assert "RFC 5321 Section 5.1" in info["Mail Routing Description"]
        assert "93.184.216.34" in info["MX Resolution Details"]

    # 6. A lookup timeout after MX NoAnswer (unverified)
    def mock_a_timeout(domain, qtype):
        if qtype == "MX":
            raise dns.resolver.NoAnswer()
        elif qtype == "A":
            raise dns.resolver.Timeout("A query timed out")
        elif qtype == "AAAA":
            raise dns.resolver.NoAnswer()
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_a_timeout):
        report = await universal_orchestrator.investigate("user@a-timeout.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "lookup_failed"
        assert info["Mail Routing Assessment"] == "unverified"
        assert "Lookup Failed" in info["MX Records"]

    # 7. AAAA lookup timeout after MX NoAnswer (unverified)
    def mock_aaaa_timeout(domain, qtype):
        if qtype == "MX":
            raise dns.resolver.NoAnswer()
        elif qtype == "A":
            raise dns.resolver.NoAnswer()
        elif qtype == "AAAA":
            raise dns.resolver.Timeout("AAAA query timed out")
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_aaaa_timeout):
        report = await universal_orchestrator.investigate("user@aaaa-timeout.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "lookup_failed"
        assert info["Mail Routing Assessment"] == "unverified"

    # 8. A lookup SERVFAIL (unverified)
    def mock_a_servfail(domain, qtype):
        if qtype == "MX":
            raise dns.resolver.NoAnswer()
        elif qtype == "A":
            raise dns.resolver.NoNameservers("Server failure: SERVFAIL")
        elif qtype == "AAAA":
            raise dns.resolver.NoAnswer()
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_a_servfail):
        report = await universal_orchestrator.investigate("user@a-servfail.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "lookup_failed"
        assert info["Mail Routing Assessment"] == "unverified"

    # 9. AAAA lookup SERVFAIL (unverified)
    def mock_aaaa_servfail(domain, qtype):
        if qtype == "MX":
            raise dns.resolver.NoAnswer()
        elif qtype == "A":
            raise dns.resolver.NoAnswer()
        elif qtype == "AAAA":
            raise dns.resolver.NoNameservers("Server failure: SERVFAIL")
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_aaaa_servfail):
        report = await universal_orchestrator.investigate("user@aaaa-servfail.org", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "lookup_failed"
        assert info["Mail Routing Assessment"] == "unverified"

    # 10. One successful address lookup and one failed address lookup (partial/unverified)
    def mock_partial_address(domain, qtype):
        if qtype == "MX":
            raise dns.resolver.NoAnswer()
        elif qtype == "A":
            return ["93.184.216.34"]
        elif qtype == "AAAA":
            raise dns.resolver.Timeout("AAAA lookup timed out")
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_partial_address):
        report = await universal_orchestrator.investigate("user@partial-addr.org", manual_type="email")
        info = report.identified_information
        # One succeeded, one failed -> overall assessment is unverified, but discovered address is recorded
        assert info["DNS Query Status"] == "lookup_failed"
        assert info["Mail Routing Assessment"] == "unverified"
        assert "Partial Address Resolution" in info["Mail Routing Description"]
        assert "93.184.216.34" in info["MX Records"]
        assert "93.184.216.34" in info["MX Resolution Details"]
        assert "unverified" in info["MX Resolution Details"].lower()

    # 11. NXDOMAIN (non-existent domain)
    with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
        report = await universal_orchestrator.investigate("user@nonexistent-domain-12345.xyz", manual_type="email")
        info = report.identified_information
        assert info["DNS Query Status"] == "answered"
        assert info["Mail Routing Assessment"] == "nxdomain"
        assert "Domain Does Not Exist (NXDOMAIN)" in info["MX Records"]

    # 12. Suppressed by policy (Public webmail e.g. Gmail)
    report_gmail = await universal_orchestrator.investigate("user@gmail.com", manual_type="email")
    info_gmail = report_gmail.identified_information
    assert info_gmail["DNS Query Status"] == "suppressed_by_policy"
    assert info_gmail["MX Routing Status"] == "suppressed_by_policy"
    assert info_gmail["Mail Routing Assessment"] == "suppressed_by_policy"

    # 13. Not performed (Malformed syntax)
    report_bad = await universal_orchestrator.investigate("not-an-email-syntax", manual_type="email")
    info_bad = report_bad.identified_information
    assert info_bad["DNS Query Status"] == "not_performed"
    assert info_bad["MX Routing Status"] == "not_performed"
    assert info_bad["Mail Routing Assessment"] == "not_performed"

    # Limitation clause check
    assert any("DNS mail routing verification confirms authoritative DNS record publication only" in lim for lim in report.investigation_limitations)


@pytest.mark.asyncio
async def test_indian_phone_carrier_attribution_and_circles():
    # Test multiple Indian mobile prefixes with different allocation metadata
    test_cases = [
        ("+919820012345", "Vodafone"),
        ("+919845012345", "Airtel"),
        ("+919422012345", "BSNL MOBILE"),
    ]

    for number, expected_carrier in test_cases:
        report = await universal_orchestrator.investigate(number, manual_type="phone")
        assert report.target_type == "phone"
        assert report.status == "completed"

        info = report.identified_information
        # Accurate carrier attribution
        assert info["Original Allocation Carrier"] == expected_carrier
        assert info["Carrier Allocation Source"] == "Google libphonenumber v9.0.42 (offline carrier mapping dataset)"
        assert "Historical/original prefix allocation metadata" in info["Carrier Data Type"]
        assert "not a live regulator lookup" in info["Carrier Data Type"]
        assert info["Current Carrier"] == "Not verified (subject to Mobile Number Portability)"
        assert info["Numbering-Plan Validity"] == "Formally valid ITU-T E.164 allocation"
        assert info["Live Subscriber Status"] == "Not verified (subscriber activity/reachability unverified)"

        # Circle attribution: mobile circle mapping is unavailable in offline dataset
        assert info["Telecom Circle / LSA"] == "Not verified (mobile telecom circle mapping unavailable in offline dataset)"
        assert "Mumbai" not in info["Telecom Circle / LSA"]

    # Verify limitations mention Google libphonenumber v9.0.42 and circle disclaimer
    limitations_text = " ".join(report.investigation_limitations)
    assert "Google libphonenumber v9.0.42 (offline dataset)" in limitations_text
    assert "Mobile Number Portability" in limitations_text
    assert "Mobile telecom circle / LSA assignments are not mapped in the offline numbering database" in limitations_text

