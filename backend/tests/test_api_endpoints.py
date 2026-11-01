import pytest
import httpx
from app.main import app

@pytest.mark.asyncio
async def test_api_endpoints():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Root serves the single page application HTML
        r1 = await client.get("/")
        assert r1.status_code == 200
        assert "<!doctype html>" in r1.text.lower() or "pravision" in r1.text.lower()

        # Settings
        r2 = await client.get("/api/settings")
        assert r2.status_code == 200
        assert r2.json()["app_name"] == "PRAVISION"

        # List Connectors
        r3 = await client.get("/api/connectors")
        assert r3.status_code == 200
        connectors = r3.json()
        assert len(connectors) >= 60

        # Classify input
        r4 = await client.post("/api/classify", json={"input": "investigation_target@example.com"})
        assert r4.status_code == 200
        classification = r4.json()
        assert classification["detected_type"] == "email"

        # Start Investigation
        r5 = await client.post("/api/investigations", json={"target": "target_user_88", "depth": 1})
        assert r5.status_code == 200
        inv_data = r5.json()
        inv_id = inv_data["id"]

        # Results
        r6 = await client.get(f"/api/investigations/{inv_id}/results")
        assert r6.status_code == 200

        # Graph
        r7 = await client.get(f"/api/investigations/{inv_id}/graph")
        assert r7.status_code == 200

        # Export HTML report
        r8 = await client.post("/api/reports/export", json={"format": "html"})
        assert r8.status_code == 200
        assert "PRAVISION" in r8.text

        # Clear Investigation
        r9 = await client.delete(f"/api/investigations/{inv_id}")
        assert r9.status_code == 200
        assert r9.json()["status"] == "cleared"
