"""Smoke tests for the request-id middleware."""


def test_request_id_minted_when_absent(client):
    r = client.get("/")
    assert r.status_code == 200
    rid = r.headers.get("X-Request-ID")
    assert rid is not None
    # uuid4().hex is 32 hex chars
    assert len(rid) == 32
    assert all(c in "0123456789abcdef" for c in rid.lower())


def test_request_id_echoed_when_provided(client):
    r = client.get("/", headers={"X-Request-ID": "client-supplied-trace-1"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == "client-supplied-trace-1"
