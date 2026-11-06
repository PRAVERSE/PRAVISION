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

