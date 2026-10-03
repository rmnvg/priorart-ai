"""SerpApi response cache and search budget profiles (offline)."""
import importlib
from unittest.mock import Mock

import pytest

from app import config
from app.serpapi_client import CachedClient, SearchOffline, request_key


@pytest.fixture
def make_client(tmp_path):
    def make(response=None, **kwargs):
        client = CachedClient("test-key", tmp_path / "responses", **kwargs)
        client._client = Mock()
        client._client.search = Mock(return_value=response or {"organic_results": [{"title": "A"}]})
        return client
    return make


def test_identical_request_is_paid_for_once(make_client):
    client = make_client()
    first = client.search(engine="google_patents", q="dryer", scholar=True)
    second = client.search(scholar=True, q="dryer", engine="google_patents")
    assert first == second == {"organic_results": [{"title": "A"}]}
    assert client._client.search.call_count == 1


def test_different_request_is_a_miss(make_client):
    client = make_client()
    client.search(engine="google_patents", q="dryer")
    client.search(engine="google_patents", q="dryer", country="IN")
    assert client._client.search.call_count == 2


def test_saved_responses_survive_a_new_client(make_client):
    make_client().search(engine="google", q="clay fridge")
    fresh = make_client()
    assert fresh.search(engine="google", q="clay fridge") == {"organic_results": [{"title": "A"}]}
    fresh._client.search.assert_not_called()


def test_error_payload_is_never_replayed(make_client):
    client = make_client(response={"error": "Your account has run out of searches."})
    client.search(engine="google", q="x")
    client.search(engine="google", q="x")
    assert client._client.search.call_count == 2


def test_offline_refuses_to_spend_a_search(make_client):
    make_client().search(engine="google", q="cached")
    offline = make_client(offline=True)
    assert offline.search(engine="google", q="cached")
    with pytest.raises(SearchOffline):
        offline.search(engine="google", q="not cached")
    offline._client.search.assert_not_called()


def test_disabled_cache_always_calls(make_client):
    client = make_client(enabled=False)
    client.search(engine="google", q="x")
    client.search(engine="google", q="x")
    assert client._client.search.call_count == 2
    assert not client.cache_dir.exists()


def test_api_key_is_not_part_of_the_key():
    assert request_key({"q": "x", "api_key": "a"}) == request_key({"q": "x", "api_key": "b"})


@pytest.fixture
def reload_config(monkeypatch):
    names = ["SEARCH_PROFILE", "REFINEMENT_QUERIES", "DEEP_DIVE_TOP_N", "CITATION_FOLLOWUPS", "ENABLE_TRENDS"]

    def reload(**env):
        for name in names:
            monkeypatch.delenv(name, raising=False)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        return importlib.reload(config)

    yield reload
    for name in names:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(config)


def test_full_profile_is_the_documented_17(reload_config):
    assert reload_config().MAX_SEARCHES_PER_ANALYSIS == 17


def test_lean_profile_costs_12(reload_config):
    cfg = reload_config(SEARCH_PROFILE="lean")
    assert (cfg.DEEP_DIVE_TOP_N, cfg.CITATION_FOLLOWUPS, cfg.ENABLE_TRENDS) == (5, 1, False)
    assert cfg.MAX_SEARCHES_PER_ANALYSIS == 12


def test_explicit_setting_overrides_profile(reload_config):
    assert reload_config(SEARCH_PROFILE="lean", DEEP_DIVE_TOP_N="3").DEEP_DIVE_TOP_N == 3


def test_unknown_profile_fails_loudly(reload_config):
    with pytest.raises(ValueError):
        reload_config(SEARCH_PROFILE="cheap")
