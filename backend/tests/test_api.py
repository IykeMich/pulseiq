"""API tests: the app runs in-process, with live/stream writes redirected to a temp directory."""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from src import config

    monkeypatch.setattr(config, "LIVE_RAW_PATH", tmp_path / "live" / "events.jsonl")
    monkeypatch.setattr(config, "LIVE_PROCESSED_PATH", tmp_path / "live_enriched.jsonl")
    import api.main

    api_module = importlib.reload(api.main)
    with TestClient(api_module.app) as test_client:
        test_client.api = api_module
        yield test_client


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_analyze_returns_guide_shape(client):
    body = client.post("/api/v1/analyze", json={"text": "Payment failed and support never replied."}).json()
    assert body["sentiment"]["label"] == "negative"
    assert set(body) >= {"review_id", "sentiment", "emotion", "intent", "topics", "aspects", "model_version"}
    assert {"payment", "customer_support"} <= set(body["topics"])


def test_analyze_validates_input(client):
    assert client.post("/api/v1/analyze", json={"text": ""}).status_code == 422
    assert client.post("/api/v1/analyze", json={"text": "x" * 2001}).status_code == 422


def test_batch_summary(client):
    body = client.post("/api/v1/batch", json={"reviews": [{"text": "Love it"}, {"text": "Terrible delivery"}]}).json()
    assert body["count"] == 2
    assert sum(body["summary"]["sentiment"].values()) == 2


def test_metrics_and_filters(client):
    sentiment = client.get("/api/v1/metrics/sentiment?days=30&product=RideGo").json()
    assert sentiment["current"]["reviews"] > 0
    assert client.get("/api/v1/metrics/topics?all=true").json()["topics"][0]["mentions"] > 0
    assert client.get("/api/v1/trends?days=14&granularity=week").status_code == 200
    assert client.get("/api/v1/issues/not-an-aspect").status_code == 404
    assert client.get("/api/v1/issues/delivery").json()["recommended_action"]


def test_feedback_search_and_detail(client):
    page = client.get("/api/v1/feedback?all=true&sentiment=negative&aspect=payment&page_size=5").json()
    assert page["total"] > 0 and len(page["items"]) == 5
    assert all("payment" in item["topics"] for item in page["items"])
    review_id = page["items"][0]["review_id"]
    assert client.get(f"/api/v1/feedback/{review_id}").json()["review_id"] == review_id
    assert client.get("/api/v1/feedback/missing").status_code == 404


def test_live_feedback_flows_through_the_stream(client):
    """Guide Phase 8: submitted feedback is analyzed asynchronously and shows up in the analytics."""
    before = client.get("/api/v1/stream/status").json()["version"]
    response = client.post("/api/v1/feedback", json={"text": "My card was charged twice!", "product": "RideGo"})
    assert response.status_code == 202
    assert client.api.state.stream.wait_until_idle()
    status = client.get("/api/v1/stream/status").json()
    assert status["version"] == before + 1 and status["processed"] == 1
    event = client.get("/api/v1/stream/recent").json()["events"][0]
    assert event["status"] == "processed" and event["sentiment"] == "negative"
    found = client.get(f"/api/v1/feedback?all=true&source=live").json()
    assert found["total"] == 1


def test_stream_replay_and_reset(client):
    client.post("/api/v1/stream/replay", json={"count": 20, "interval_ms": 0})
    client.api.state.replay_thread.join(timeout=10)
    assert client.api.state.stream.wait_until_idle()
    assert client.get("/api/v1/stream/status").json()["processed"] == 20
    reset = client.post("/api/v1/stream/reset").json()
    assert reset["processed"] == 0 and reset["replay"]["position"] == 0


def test_any_website_can_call_the_api_by_default(client):
    """No CORS_ORIGINS set: a frontend on any domain (custom domain, LAN address) is allowed."""
    for origin in ["https://pulseiq.vercel.app", "https://pulseiq.example.com", "http://192.168.1.20:3006"]:
        preflight = client.options("/api/v1/metrics/sentiment", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type",
        })
        assert preflight.status_code == 200
        response = client.get("/health", headers={"Origin": origin})
        assert response.headers["access-control-allow-origin"] in {"*", origin}
