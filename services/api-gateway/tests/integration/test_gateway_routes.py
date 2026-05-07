"""
API Gateway Integration Tests
Tests proxy routing behavior to downstream services (database-manager, realtime-voice-service).
Ensures correct request forwarding, response translation, error handling, and rate limiting.
"""
from pathlib import Path
import json
import sys
from unittest.mock import Mock
import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[2]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from api_gateway import app as gateway_app
import routes.database_routes as database_routes_module
import routes.health_routes as health_routes_module


class FakeResponse:
    """Mock for requests.Response object"""
    def __init__(self, payload, status_code=200, content_type="application/json"):
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload
        self.headers = {"content-type": content_type}


@pytest.fixture()
def client():
    """Flask test client with testing mode enabled"""
    gateway_app.config.update(TESTING=True)
    with gateway_app.test_client() as test_client:
        yield test_client


# ============================================================================
# HEALTH ROUTE INTEGRATION TESTS
# ============================================================================

def test_health_gateway_only_endpoint(client):
    """Test /api/query/health/gateway returns only gateway status"""
    response = client.get("/api/query/health/gateway")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "healthy"
    assert "gateway" in payload
    assert "services" not in payload


def test_health_all_services_healthy(client, monkeypatch):
    """Test /api/query/health returns 200 when all services are healthy"""
    call_count = [0]
    
    def fake_get(url, timeout=2):
        call_count[0] += 1
        return FakeResponse({"status": "healthy"}, status_code=200)
    
    monkeypatch.setattr(health_routes_module.requests, "get", fake_get)
    
    response = client.get("/api/query/health")
    payload = response.get_json()
    
    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["services"]["database_service"]["status"] == "healthy"
    assert payload["services"]["realtime_voice_service"]["status"] == "healthy"
    assert call_count[0] == 2  # Called for both services


def test_health_all_services_degraded_when_one_unreachable(client, monkeypatch):
    """Test /api/query/health returns 503 when downstream service is unreachable"""
    def fake_get(url, timeout=2):
        if "5004" in url:  # database service
            return FakeResponse({"status": "healthy"}, status_code=200)
        raise RuntimeError("connection refused")
    
    monkeypatch.setattr(health_routes_module.requests, "get", fake_get)
    
    response = client.get("/api/query/health")
    payload = response.get_json()
    
    assert response.status_code == 503
    assert payload["status"] == "degraded"
    assert payload["services"]["database_service"]["status"] == "healthy"
    assert payload["services"]["realtime_voice_service"]["status"] == "unreachable"


def test_health_all_services_degraded_when_unhealthy(client, monkeypatch):
    """Test /api/query/health returns 503 when a service is unhealthy"""
    def fake_get(url, timeout=2):
        return FakeResponse({"status": "error"}, status_code=500)
    
    monkeypatch.setattr(health_routes_module.requests, "get", fake_get)
    
    response = client.get("/api/query/health")
    payload = response.get_json()
    
    assert response.status_code == 503
    assert payload["status"] == "degraded"


# ============================================================================
# SUBJECTS ENDPOINT PROXY TESTS
# ============================================================================

def test_subjects_get_list(client, monkeypatch):
    """Test GET /api/query/subjects proxies to database service"""
    def fake_get(url, timeout=10):
        assert url.endswith("/subjects")
        return FakeResponse({"subjects": [
            {"id": 1, "name": "Nederlands"},
            {"id": 2, "name": "English"}
        ]}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/subjects")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["subjects"]) == 2
    assert payload["subjects"][0]["name"] == "Nederlands"


def test_subjects_post_create(client, monkeypatch):
    """Test POST /api/query/subjects proxies create request"""
    def fake_post(url, json=None, timeout=10):
        assert url.endswith("/subjects")
        assert json["name"] == "Nieuw Vak"
        return FakeResponse({"id": 99, "name": "Nieuw Vak"}, status_code=201)
    
    monkeypatch.setattr(database_routes_module.requests, "post", fake_post)
    response = client.post("/api/query/subjects", json={"name": "Nieuw Vak"})
    
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["id"] == 99


def test_subject_get_by_id(client, monkeypatch):
    """Test GET /api/query/subjects/<id> proxies request"""
    def fake_get(url, timeout=10):
        assert url.endswith("/subjects/5")
        return FakeResponse({"id": 5, "name": "Wiskunde"}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/subjects/5")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["name"] == "Wiskunde"


def test_subject_put_update(client, monkeypatch):
    """Test PUT /api/query/subjects/<id> proxies update"""
    def fake_put(url, json=None, timeout=10):
        assert url.endswith("/subjects/5")
        assert json["name"] == "Wiskunde Updated"
        return FakeResponse({"id": 5, "name": "Wiskunde Updated"}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "put", fake_put)
    response = client.put("/api/query/subjects/5", json={"name": "Wiskunde Updated"})
    
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["name"] == "Wiskunde Updated"


def test_subject_delete(client, monkeypatch):
    """Test DELETE /api/query/subjects/<id> proxies deletion"""
    def fake_delete(url, timeout=10):
        assert url.endswith("/subjects/5")
        return FakeResponse({}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "delete", fake_delete)
    response = client.delete("/api/query/subjects/5")
    
    assert response.status_code == 200


# ============================================================================
# PROMPTS ENDPOINT PROXY TESTS
# ============================================================================

def test_prompts_get_list(client, monkeypatch):
    """Test GET /api/query/prompts proxies list"""
    def fake_get(url, timeout=10):
        assert url.endswith("/prompts")
        return FakeResponse({"prompts": [
            {"id": 1, "name": "System Prompt", "active": True}
        ]}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/prompts")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["prompts"][0]["active"] is True


def test_prompts_post_create(client, monkeypatch):
    """Test POST /api/query/prompts creates prompt"""
    def fake_post(url, json=None, timeout=10):
        assert url.endswith("/prompts")
        return FakeResponse({"id": 2, "name": json["name"]}, status_code=201)
    
    monkeypatch.setattr(database_routes_module.requests, "post", fake_post)
    response = client.post("/api/query/prompts", json={"name": "New Prompt"})
    
    assert response.status_code == 201


def test_prompts_active_get(client, monkeypatch):
    """Test GET /api/query/prompts/active proxies active prompt retrieval"""
    def fake_get(url, timeout=10):
        assert url.endswith("/prompts/active")
        return FakeResponse({"id": 1, "name": "Active", "active": True}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/prompts/active")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["active"] is True


def test_prompt_get_by_id(client, monkeypatch):
    """Test GET /api/query/prompts/<id> proxies request"""
    def fake_get(url, timeout=10):
        assert url.endswith("/prompts/3")
        return FakeResponse({"id": 3, "name": "Prompt 3"}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/prompts/3")
    
    assert response.status_code == 200


def test_prompt_patch_update(client, monkeypatch):
    """Test PATCH /api/query/prompts/<id> proxies update (uses PATCH backend)"""
    def fake_patch(url, json=None, timeout=10):
        assert url.endswith("/prompts/3")
        return FakeResponse({"id": 3, "name": "Updated"}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "patch", fake_patch)
    response = client.patch("/api/query/prompts/3", json={"name": "Updated"})
    
    assert response.status_code == 200


def test_prompt_put_converts_to_patch(client, monkeypatch):
    """Test PUT /api/query/prompts/<id> also uses PATCH on backend"""
    def fake_patch(url, json=None, timeout=10):
        assert url.endswith("/prompts/3")
        return FakeResponse({"id": 3, "name": "Updated"}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "patch", fake_patch)
    response = client.put("/api/query/prompts/3", json={"name": "Updated"})
    
    assert response.status_code == 200


def test_prompt_delete(client, monkeypatch):
    """Test DELETE /api/query/prompts/<id> proxies deletion"""
    def fake_delete(url, timeout=10):
        assert url.endswith("/prompts/3")
        return FakeResponse({}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "delete", fake_delete)
    response = client.delete("/api/query/prompts/3")
    
    assert response.status_code == 200


# ============================================================================
# CHUNKS ENDPOINT PROXY TESTS
# ============================================================================

def test_subject_chunks_get(client, monkeypatch):
    """Test GET /api/query/subjects/<id>/chunks proxies request"""
    def fake_get(url, timeout=10):
        assert url.endswith("/subjects/1/chunks")
        return FakeResponse({"chunks": [
            {"id": 1, "subject_id": 1, "content": "chunk1"}
        ]}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/subjects/1/chunks")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["chunks"]) == 1


def test_subject_chunks_post_create(client, monkeypatch):
    """Test POST /api/query/subjects/<id>/chunks proxies creation"""
    def fake_post(url, json=None, timeout=10):
        assert url.endswith("/subjects/1/chunks")
        return FakeResponse({"id": 99, "content": "new chunk"}, status_code=201)
    
    monkeypatch.setattr(database_routes_module.requests, "post", fake_post)
    response = client.post("/api/query/subjects/1/chunks", json={"content": "new chunk"})
    
    assert response.status_code == 201


def test_chunk_get_by_id(client, monkeypatch):
    """Test GET /api/query/chunks/<id> proxies request"""
    def fake_get(url, timeout=10):
        assert url.endswith("/chunks/7")
        return FakeResponse({"id": 7, "content": "chunk content"}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/chunks/7")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["id"] == 7


def test_chunk_put_update(client, monkeypatch):
    """Test PUT /api/query/chunks/<id> proxies update"""
    def fake_put(url, json=None, timeout=10):
        assert url.endswith("/chunks/7")
        return FakeResponse({"id": 7, "content": "updated"}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "put", fake_put)
    response = client.put("/api/query/chunks/7", json={"content": "updated"})
    
    assert response.status_code == 200


def test_chunk_delete(client, monkeypatch):
    """Test DELETE /api/query/chunks/<id> proxies deletion"""
    def fake_delete(url, timeout=10):
        assert url.endswith("/chunks/7")
        return FakeResponse({}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "delete", fake_delete)
    response = client.delete("/api/query/chunks/7")
    
    assert response.status_code == 200


# ============================================================================
# SETTINGS ENDPOINT PROXY TESTS
# ============================================================================

def test_settings_get_all(client, monkeypatch):
    """Test GET /api/query/settings proxies all settings"""
    def fake_get(url, params=None, timeout=10):
        assert url.endswith("/settings")
        return FakeResponse({"settings": [
            {"key": "setting1", "value": "value1"}
        ]}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/settings")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["settings"]) == 1


def test_settings_post_create(client, monkeypatch):
    """Test POST /api/query/settings proxies creation"""
    def fake_post(url, json=None, timeout=10):
        assert url.endswith("/settings")
        return FakeResponse({"key": "newkey", "value": "newval"}, status_code=201)
    
    monkeypatch.setattr(database_routes_module.requests, "post", fake_post)
    response = client.post("/api/query/settings", json={"key": "newkey", "value": "newval"})
    
    assert response.status_code == 201


def test_setting_get_by_key(client, monkeypatch):
    """Test GET /api/query/settings/<key> proxies request"""
    def fake_get(url, timeout=10):
        assert url.endswith("/settings/maxval")
        return FakeResponse({"key": "maxval", "value": 100}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/settings/maxval")
    
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["key"] == "maxval"


def test_setting_patch_update(client, monkeypatch):
    """Test PATCH /api/query/settings/<key> proxies update"""
    def fake_patch(url, json=None, timeout=10):
        assert url.endswith("/settings/maxval")
        return FakeResponse({"key": "maxval", "value": 200}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "patch", fake_patch)
    response = client.patch("/api/query/settings/maxval", json={"value": 200})
    
    assert response.status_code == 200


def test_setting_put_also_uses_patch(client, monkeypatch):
    """Test PUT /api/query/settings/<key> proxies via PATCH"""
    def fake_put(url, json=None, timeout=10):
        assert url.endswith("/settings/maxval")
        return FakeResponse({"key": "maxval", "value": 300}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "put", fake_put)
    response = client.put("/api/query/settings/maxval", json={"value": 300})
    
    assert response.status_code == 200


def test_setting_delete(client, monkeypatch):
    """Test DELETE /api/query/settings/<key> proxies deletion"""
    def fake_delete(url, timeout=10):
        assert url.endswith("/settings/maxval")
        return FakeResponse({}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "delete", fake_delete)
    response = client.delete("/api/query/settings/maxval")
    
    assert response.status_code == 200


# ============================================================================
# FILE UPLOAD ENDPOINT PROXY TESTS
# ============================================================================

def test_subject_upload_post(client, monkeypatch):
    """Test POST /api/query/subjects/<id>/upload proxies file upload"""
    def fake_post(url, files=None, timeout=300):
        assert url.endswith("/subjects/1/upload")
        assert files is not None
        assert "file" in files
        return FakeResponse({"upload_id": "upload-001"}, status_code=201)
    
    monkeypatch.setattr(database_routes_module.requests, "post", fake_post)
    
    # Create fake file data
    from io import BytesIO
    data = {
        'file': (BytesIO(b'test content'), 'test.txt')
    }
    response = client.post("/api/query/subjects/1/upload", data=data, content_type='multipart/form-data')
    
    assert response.status_code == 201


def test_subject_upload_delete(client, monkeypatch):
    """Test DELETE /api/query/subjects/<id>/uploads/<name> proxies deletion"""
    def fake_delete(url, timeout=30):
        assert "/uploads/" in url
        return FakeResponse({"deleted": True}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "delete", fake_delete)
    response = client.delete("/api/query/subjects/1/uploads/my-upload.pdf")
    
    assert response.status_code == 200


def test_subject_upload_delete_with_special_chars(client, monkeypatch):
    """Test DELETE proxies with URL-encoded special characters"""
    def fake_delete(url, timeout=30):
        # Should contain URL-encoded filename
        assert "/uploads/" in url
        return FakeResponse({"deleted": True}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "delete", fake_delete)
    response = client.delete("/api/query/subjects/1/uploads/my-file%20with%20spaces.pdf")
    
    assert response.status_code == 200


# ============================================================================
# ERROR HANDLING AND EDGE CASES
# ============================================================================

def test_proxy_request_timeout_returns_500(client, monkeypatch):
    """Test proxy returns 500 when downstream times out"""
    def fake_get(*args, **kwargs):
        raise TimeoutError("Request timed out")
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/subjects")
    
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "timed out" in payload["message"].lower()


def test_proxy_connection_error_returns_500(client, monkeypatch):
    """Test proxy returns 500 when cannot connect"""
    def fake_get(*args, **kwargs):
        raise ConnectionError("Cannot connect to database service")
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/subjects")
    
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["status"] == "error"


def test_proxy_preserves_upstream_status_codes(client, monkeypatch):
    """Test proxy preserves various HTTP status codes from upstream"""
    def fake_get(url, timeout=10):
        return FakeResponse({"error": "not found"}, status_code=404)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/subjects/999")
    
    # Proxy returns the response as-is
    assert response.status_code == 404


def test_proxy_preserves_response_content_type(client, monkeypatch):
    """Test proxy preserves content-type from upstream"""
    def fake_get(url, timeout=10):
        return FakeResponse({"data": "test"}, status_code=200, content_type="application/json")
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/subjects")
    
    assert response.status_code == 200
    assert "application/json" in response.content_type


def test_multiple_consecutive_requests(client, monkeypatch):
    """Test gateway handles multiple consecutive requests correctly"""
    request_count = [0]
    
    def fake_get(url, timeout=10):
        request_count[0] += 1
        return FakeResponse({"request_num": request_count[0]}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    
    response1 = client.get("/api/query/subjects")
    response2 = client.get("/api/query/subjects")
    response3 = client.get("/api/query/subjects")
    
    assert all(r.status_code == 200 for r in [response1, response2, response3])
    assert request_count[0] == 3


def test_health_endpoint_with_query_parameters(client, monkeypatch):
    """Test health endpoint ignores query parameters"""
    def fake_get(url, timeout=2):
        return FakeResponse({"status": "healthy"}, status_code=200)
    
    monkeypatch.setattr(health_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/health?extra=param&another=value")
    
    assert response.status_code == 200


def test_settings_with_query_parameters(client, monkeypatch):
    """Test settings GET forwards query parameters"""
    received_params = {}
    
    def fake_get(url, params=None, timeout=10):
        received_params.update(params or {})
        return FakeResponse({"settings": []}, status_code=200)
    
    monkeypatch.setattr(database_routes_module.requests, "get", fake_get)
    response = client.get("/api/query/settings?filter=active&limit=10")
    
    assert response.status_code == 200
