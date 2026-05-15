"""Smoke tests for /health and / (root) endpoints."""

from unittest.mock import patch


def test_root_returns_api_running(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["message"] == "API is running"


def test_health_db_ok_redis_ok(client):
    """DB ping always works against in-memory SQLite. Mock Redis success."""
    with patch("main.redis_client") as mock_redis:
        mock_redis.ping.return_value = True
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True


def test_health_redis_down_still_200(client):
    """Redis is best-effort — its failure does NOT make the service unhealthy."""
    with patch("main.redis_client") as mock_redis:
        mock_redis.ping.side_effect = ConnectionError("no redis here")
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is False
    assert "no redis here" in body["checks"]["redis"]["error"]
