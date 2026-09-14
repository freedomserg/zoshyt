"""GET /health відповідає 200 без БД (юніт-тест через ASGI, без мережі)."""

from httpx import ASGITransport, AsyncClient

from zoshyt.api.app import create_app


async def test_health_ok() -> None:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
