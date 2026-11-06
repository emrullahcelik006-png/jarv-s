import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
async def test_ui_index_served():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "J.A.R.V.I.S" in res.text


@pytest.mark.asyncio
async def test_api_system_status_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/system/status")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "providers" in data
        assert "metrics" in data
