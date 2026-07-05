"""
Tests for backend/volume/gsc_provider.py's GoogleSearchConsoleProvider (#61)
— real Google Search Console Search Analytics API integration, using a
service-account credential. No real network/Google Cloud calls: HTTP is
mocked (requests.post) and the auth step (_get_access_token) is patched
directly, since exercising the actual JWT-signing/service-account file
logic would require a real credentials file this environment doesn't have.
"""
from unittest.mock import patch, MagicMock

from backend.volume.gsc_provider import GoogleSearchConsoleProvider


def _provider(credential="fake.json", site_url="https://example.com/"):
    p = GoogleSearchConsoleProvider()
    p.set_credential(credential)
    p.set_site_url(site_url)
    return p


def _fake_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def test_no_credential_returns_in_band_error_not_raise():
    p = GoogleSearchConsoleProvider()
    p.set_site_url("https://example.com/")
    result = p.get_query_volumes()
    assert result == {"queries": [], "error": "No service-account credential configured."}


def test_no_site_url_returns_in_band_error_not_raise():
    p = GoogleSearchConsoleProvider()
    p.set_credential("fake.json")
    result = p.get_query_volumes()
    assert result == {"queries": [], "error": "No site URL configured."}


def test_auth_failure_is_reported_in_band():
    p = _provider()
    with patch.object(p, "_get_access_token", side_effect=Exception("bad credentials file")):
        result = p.get_query_volumes()
    assert result["queries"] == []
    assert "Authentication failed" in result["error"]
    assert "bad credentials file" in result["error"]


def test_successful_query_returns_parsed_rows():
    p = _provider()
    api_response = {
        "rows": [
            {"keys": ["best portable generator"], "clicks": 40, "impressions": 500, "ctr": 0.08, "position": 3.2},
            {"keys": ["quiet generator"], "clicks": 10, "impressions": 150, "ctr": 0.067, "position": 5.1},
        ]
    }
    with patch.object(p, "_get_access_token", return_value="fake-token"), \
         patch("backend.volume.gsc_provider.requests.post",
               return_value=_fake_response(200, api_response)) as mock_post:
        result = p.get_query_volumes(days=30)

    assert result["error"] == ""
    assert result["queries"] == [
        {"query": "best portable generator", "clicks": 40, "impressions": 500},
        {"query": "quiet generator", "clicks": 10, "impressions": 150},
    ]
    # Confirm the Authorization header actually carries the token
    _, kwargs = mock_post.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer fake-token"


def test_empty_rows_returns_empty_query_list_not_an_error():
    p = _provider()
    with patch.object(p, "_get_access_token", return_value="fake-token"), \
         patch("backend.volume.gsc_provider.requests.post", return_value=_fake_response(200, {})):
        result = p.get_query_volumes()
    assert result == {"queries": [], "error": ""}


def test_http_error_status_is_reported_in_band():
    p = _provider()
    with patch.object(p, "_get_access_token", return_value="fake-token"), \
         patch("backend.volume.gsc_provider.requests.post",
               return_value=_fake_response(403, text="Permission denied")):
        result = p.get_query_volumes()
    assert result["queries"] == []
    assert "403" in result["error"]
    assert "Permission denied" in result["error"]


def test_network_exception_during_request_is_reported_in_band():
    p = _provider()
    with patch.object(p, "_get_access_token", return_value="fake-token"), \
         patch("backend.volume.gsc_provider.requests.post", side_effect=Exception("connection reset")):
        result = p.get_query_volumes()
    assert result["queries"] == []
    assert "connection reset" in result["error"]


def test_rows_missing_keys_are_skipped_not_crashed_on():
    p = _provider()
    api_response = {"rows": [{"clicks": 5, "impressions": 10}]}  # no "keys" at all
    with patch.object(p, "_get_access_token", return_value="fake-token"), \
         patch("backend.volume.gsc_provider.requests.post",
               return_value=_fake_response(200, api_response)):
        result = p.get_query_volumes()
    assert result == {"queries": [], "error": ""}
