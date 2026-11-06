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
async def test_email_mx_deterministic_mocking():
    # Case A: Explicit MX Records
    mock_rdata = MagicMock()
    mock_rdata.preference = 10
    mock_rdata.exchange = "mail.customdomain.org."
    with patch("dns.resolver.Resolver.resolve") as mock_resolve:
        mock_resolve.return_value = [mock_rdata]
        report = await universal_orchestrator.investigate("user@customdomain.org", manual_type="email")
        assert report.identified_information["MX Routing Status"] == "resolved"
        assert report.identified_information["Mail Routing Assessment"] == "Explicit MX Configured"
        assert "mail.customdomain.org" in report.identified_information["MX Records"]
        assert "Successfully resolved 1 authoritative MX host(s)" in report.identified_information["MX Resolution Details"]

    # Case B: NoAnswer with A/AAAA address records (RFC 5321 implicit MX candidate)
    def mock_resolve_noanswer_with_a(domain, qtype):
        if qtype == "MX":
            raise dns.resolver.NoAnswer()
        elif qtype == "A":
            return ["93.184.216.34"]
        elif qtype == "AAAA":
            raise dns.resolver.NoAnswer()
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_resolve_noanswer_with_a):
        report = await universal_orchestrator.investigate("user@existingdomain-with-a.org", manual_type="email")
        assert report.identified_information["MX Routing Status"] == "resolved"
        assert report.identified_information["Mail Routing Assessment"] == "Implicit MX Routing May Apply (RFC 5321 Section 5.1)"
        assert "Address Records Found" in report.identified_information["MX Records"]
        assert "RFC 5321 Section 5.1" in report.identified_information["MX Resolution Details"]
        assert "No Explicit MX — Address Records Found" in report.summary.headline
        # Verify it is NOT labeled as inactive
        assert "Inactive Mail Domain" not in report.summary.headline

    # Case C: NoAnswer without A/AAAA address records
    def mock_resolve_noanswer_no_a(domain, qtype):
        raise dns.resolver.NoAnswer()

    with patch("dns.resolver.Resolver.resolve", side_effect=mock_resolve_noanswer_no_a):
        report = await universal_orchestrator.investigate("user@existingdomain-no-records.org", manual_type="email")
        assert report.identified_information["MX Routing Status"] == "resolved"
        assert report.identified_information["Mail Routing Assessment"] == "No MX or Address Records Published"
        assert "None Published (No MX or Address Records)" in report.identified_information["MX Records"]
        assert "neither explicit MX records" in report.identified_information["MX Resolution Details"]
        assert "Domain Lacks Mail Routing Records" in report.summary.headline

    # Case D: Null MX (RFC 7505 - "MX 0 .")
    mock_null_mx = MagicMock()
    mock_null_mx.preference = 0
    mock_null_mx.exchange = "."
    with patch("dns.resolver.Resolver.resolve") as mock_resolve:
        mock_resolve.return_value = [mock_null_mx]
        report = await universal_orchestrator.investigate("user@null-mx-domain.org", manual_type="email")
        assert report.identified_information["MX Routing Status"] == "resolved"
        assert report.identified_information["Mail Routing Assessment"] == "Explicitly Declares No Mail Acceptance (RFC 7505 Null MX)"
        assert "Null MX (RFC 7505 — Does Not Accept Mail)" in report.identified_information["MX Records"]
        assert "Domain Rejects Mail (RFC 7505 Null MX)" in report.summary.headline
        assert report.summary.risk_level == "High"

    # Case E: NXDOMAIN (Queried domain does not exist in DNS)
    with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.NXDOMAIN):
        report = await universal_orchestrator.investigate("user@nonexistent-domain-12345.xyz", manual_type="email")
        assert report.identified_information["MX Routing Status"] == "resolved"
        assert report.identified_information["Mail Routing Assessment"] == "Non-Existent Domain (NXDOMAIN)"
        assert "Domain Does Not Exist (NXDOMAIN)" in report.identified_information["MX Records"]
        assert "does not exist in the Domain Name System" in report.identified_information["MX Resolution Details"]
        # Verify it does not assert unregistered or expired
        assert "unregistered or expired" not in report.identified_information["MX Resolution Details"]
        assert "Non-Existent Mail Domain" in report.summary.headline
        assert report.summary.risk_level == "High"

    # Case F: Timeout / Resolver Failure
    with patch("dns.resolver.Resolver.resolve", side_effect=dns.resolver.Timeout("Query timed out")):
        report = await universal_orchestrator.investigate("user@timeoutdomain.org", manual_type="email")
        assert report.identified_information["MX Routing Status"] == "lookup_failed"
        assert report.identified_information["Mail Routing Assessment"] == "DNS Lookup Failed (Timeout / Transport Error)"
        assert "Lookup Failed (DNS Timeout / Unreachable)" in report.identified_information["MX Records"]
        assert "DNS resolution failed or timed out" in report.identified_information["MX Resolution Details"]

    # Case G: Suppressed by policy (Public consumer webmail like Gmail)
    report_gmail = await universal_orchestrator.investigate("user@gmail.com", manual_type="email")
    assert report_gmail.identified_information["MX Routing Status"] == "suppressed_by_policy"
    assert report_gmail.identified_information["Mail Routing Assessment"] == "Consumer Webmail Domain (Managed Infrastructure)"
    assert "Suppressed by Policy (Webmail Domain)" in report_gmail.identified_information["MX Records"]

    # Case H: Not performed (Malformed email syntax)
    report_bad = await universal_orchestrator.investigate("not-an-email-at-all", manual_type="email")
    assert report_bad.identified_information["MX Routing Status"] == "not_performed"
    assert report_bad.identified_information["Mail Routing Assessment"] == "Not Performed (Invalid RFC 5322 Syntax)"
    assert report_bad.identified_information["MX Records"] == "Not Performed"


@pytest.mark.asyncio
async def test_phone_carrier_terminology_and_validity():
    report = await universal_orchestrator.investigate("+919820012345", manual_type="phone")
    assert report.target_type == "phone"
    assert report.status == "completed"
    
    info = report.identified_information
    # Accurate carrier terminology and authoritative allocation evidence
    assert info["Original Allocation Carrier"] == "Vodafone"
    assert "TRAI / DoT National Numbering Plan" in info["Carrier Allocation Source"]
    assert "Google libphonenumber v9.0.42" in info["Carrier Allocation Source"]
    assert "Regulator Numbering-Plan Allocation" in info["Carrier Data Type"]
    assert info["Current Carrier"] == "Not verified (subject to Mobile Number Portability)"
    assert info["Numbering-Plan Validity"] == "Formally valid ITU-T E.164 allocation"
    assert info["Live Subscriber Status"] == "Not verified (subscriber activity/reachability unverified)"
    
    # Limitations explain Mobile Number Portability (MNP) and offline dataset derivation
    limitations_text = " ".join(report.investigation_limitations)
    assert "Mobile Number Portability" in limitations_text
    assert "TRAI/DoT National Numbering Plan" in limitations_text

