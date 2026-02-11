"""Integration tests for the cnmn server Portkey gateway."""

import json
import os
import pytest
import requests_mock as rmock

# Patch env before importing server
for var in ('PORTKEY_API_KEY', 'PORTKEY_SLUG_ANTHROPIC', 'PORTKEY_SLUG_OPENAI',
            'PORTKEY_SLUG_GOOGLE', 'AUTH_USERNAME', 'AUTH_PASSWORD'):
    os.environ.pop(var, None)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure a clean env for every test."""
    for var in ('PORTKEY_API_KEY', 'PORTKEY_SLUG_ANTHROPIC', 'PORTKEY_SLUG_OPENAI',
                'PORTKEY_SLUG_GOOGLE', 'AUTH_USERNAME',
                'AUTH_PASSWORD', 'RENDER', 'PRODUCTION'):
        monkeypatch.delenv(var, raising=False)


def _make_app(monkeypatch, portkey_key='', slugs=None):
    """Create a fresh Flask test client with the given env config.

    slugs: dict mapping provider -> slug, e.g. {'anthropic': 'my-anthropic'}
    """
    import server

    monkeypatch.setattr(server, 'PORTKEY_API_KEY', portkey_key)
    monkeypatch.setattr(server, 'PROVIDER_SLUGS', slugs if slugs else {})
    monkeypatch.setattr(server, 'AUTH_USERNAME', '')
    monkeypatch.setattr(server, 'AUTH_PASSWORD', '')

    server.app.config['TESTING'] = True
    return server.app.test_client(), server


# ------------------------------------------------------------------
# /api/models
# ------------------------------------------------------------------

PORTKEY_URL = 'https://api.portkey.ai/v1/chat/completions'
FAKE_PORTKEY_KEY = 'pk-live-xxxxxxxxxxxxxxxxxxxx1'


class TestModelsEndpoint:
    def test_no_portkey_key_returns_empty_models(self, monkeypatch):
        client, _ = _make_app(monkeypatch, portkey_key='')
        resp = client.get('/api/models')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['models'] == {}
        assert data['portkey'] is False
        assert data['rules'] is True

    def test_returns_only_models_with_slugs(self, monkeypatch):
        """Only models whose provider has a slug are returned."""
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'anthropic': 'my-anthropic'})
        resp = client.get('/api/models')
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['portkey'] is True
        # Only anthropic models
        assert 'claude-opus-4-6' in data['models']
        assert 'claude-sonnet-4-5-20250929' in data['models']
        assert 'claude-haiku-4-5-20251001' in data['models']
        # No openai or google
        assert 'gpt-4o' not in data['models']
        assert 'gemini-2.0-flash' not in data['models']

    def test_multiple_slugs_returns_multiple_providers(self, monkeypatch):
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'anthropic': 'my-ant', 'openai': 'my-oai'})
        resp = client.get('/api/models')
        data = resp.get_json()
        assert 'claude-opus-4-6' in data['models']
        assert 'gpt-4o' in data['models']
        assert 'gemini-2.0-flash' not in data['models']


# ------------------------------------------------------------------
# /api/chat — validation
# ------------------------------------------------------------------

class TestChatValidation:
    def test_missing_prompt(self, monkeypatch):
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'openai': 'oai'})
        resp = client.post('/api/chat', json={'model': 'gpt-4o'})
        assert resp.status_code == 400
        assert 'No prompt' in resp.get_json()['error']

    def test_unknown_model(self, monkeypatch):
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'openai': 'oai'})
        resp = client.post('/api/chat',
                           json={'model': 'does-not-exist', 'prompt': 'hi'})
        assert resp.status_code == 400
        assert 'Unknown model' in resp.get_json()['error']

    def test_no_portkey_key(self, monkeypatch):
        client, _ = _make_app(monkeypatch, portkey_key='')
        resp = client.post('/api/chat',
                           json={'model': 'gpt-4o', 'prompt': 'hi'})
        assert resp.status_code == 400
        assert 'not configured' in resp.get_json()['error']

    def test_no_slug_for_provider(self, monkeypatch):
        """Requesting a model whose provider has no slug -> clear 400 error."""
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'anthropic': 'my-ant'})
        resp = client.post('/api/chat',
                           json={'model': 'gpt-4o', 'prompt': 'hi'})
        assert resp.status_code == 400
        error = resp.get_json()['error']
        assert 'openai' in error.lower()
        assert 'PORTKEY_SLUG_OPENAI' in error


# ------------------------------------------------------------------
# /api/chat — Portkey calls with mocked HTTP
# ------------------------------------------------------------------

class TestChatPortkeyCall:
    def test_anthropic_model_uses_slug_in_model_field(self, monkeypatch):
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'anthropic': 'my-anthropic'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, json={
                'choices': [{'message': {'content': 'Hello from Claude'}}]
            })

            resp = client.post('/api/chat', json={
                'model': 'claude-haiku-4-5-20251001',
                'prompt': 'say hello',
            })

            assert resp.status_code == 200
            assert resp.get_json()['content'] == 'Hello from Claude'

            # Verify model field uses @slug/model format
            body = m.last_request.json()
            assert body['model'] == '@my-anthropic/claude-haiku-4-5-20251001'

            # Only x-portkey-api-key header — no virtual-key or provider headers
            sent_headers = m.last_request.headers
            assert sent_headers['x-portkey-api-key'] == FAKE_PORTKEY_KEY
            assert 'x-portkey-virtual-key' not in sent_headers
            assert 'x-portkey-provider' not in sent_headers
            assert 'Authorization' not in sent_headers

    def test_openai_model_uses_slug(self, monkeypatch):
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'openai': 'prod-openai'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, json={
                'choices': [{'message': {'content': 'Hello from GPT'}}]
            })

            resp = client.post('/api/chat', json={
                'model': 'gpt-4o',
                'prompt': 'say hello',
            })

            assert resp.status_code == 200
            body = m.last_request.json()
            assert body['model'] == '@prod-openai/gpt-4o'

    def test_google_model_uses_slug(self, monkeypatch):
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'google': 'my-google'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, json={
                'choices': [{'message': {'content': 'Hello from Gemini'}}]
            })

            resp = client.post('/api/chat', json={
                'model': 'gemini-2.0-flash',
                'prompt': 'say hello',
            })

            assert resp.status_code == 200
            body = m.last_request.json()
            assert body['model'] == '@my-google/gemini-2.0-flash'

    def test_portkey_error_forwarded(self, monkeypatch):
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'openai': 'oai'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, status_code=500,
                   json={'error': 'Internal Server Error'})

            resp = client.post('/api/chat', json={
                'model': 'gpt-4o-mini',
                'prompt': 'test',
            })

            assert resp.status_code == 500
            assert 'Portkey API error' in resp.get_json()['error']

    def test_request_body_format(self, monkeypatch):
        """Verify the full OpenAI-compatible request body sent to Portkey."""
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'google': 'gemini-prod'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, json={
                'choices': [{'message': {'content': 'ok'}}]
            })

            client.post('/api/chat', json={
                'model': 'gemini-2.0-flash',
                'prompt': 'test prompt',
            })

            body = m.last_request.json()
            assert body['model'] == '@gemini-prod/gemini-2.0-flash'
            assert body['messages'] == [{'role': 'user', 'content': 'test prompt'}]
            assert body['max_tokens'] == 1024
            assert body['temperature'] == 0.7

    def test_custom_max_tokens(self, monkeypatch):
        """Client can specify max_tokens in the request body."""
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'anthropic': 'my-ant'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, json={
                'choices': [{'message': {'content': 'ok'}}]
            })

            client.post('/api/chat', json={
                'model': 'claude-haiku-4-5-20251001',
                'prompt': 'test',
                'max_tokens': 4096,
            })

            body = m.last_request.json()
            assert body['max_tokens'] == 4096

    def test_max_tokens_capped_at_8192(self, monkeypatch):
        """max_tokens is capped at 8192."""
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'anthropic': 'my-ant'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, json={
                'choices': [{'message': {'content': 'ok'}}]
            })

            client.post('/api/chat', json={
                'model': 'claude-haiku-4-5-20251001',
                'prompt': 'test',
                'max_tokens': 99999,
            })

            body = m.last_request.json()
            assert body['max_tokens'] == 8192

    def test_max_tokens_invalid_uses_default(self, monkeypatch):
        """Invalid max_tokens falls back to 1024."""
        client, _ = _make_app(monkeypatch,
                              portkey_key=FAKE_PORTKEY_KEY,
                              slugs={'anthropic': 'my-ant'})

        with rmock.Mocker() as m:
            m.post(PORTKEY_URL, json={
                'choices': [{'message': {'content': 'ok'}}]
            })

            client.post('/api/chat', json={
                'model': 'claude-haiku-4-5-20251001',
                'prompt': 'test',
                'max_tokens': 'not-a-number',
            })

            body = m.last_request.json()
            assert body['max_tokens'] == 1024


# ------------------------------------------------------------------
# /api/puzzle-dates
# ------------------------------------------------------------------

class TestPuzzleDates:
    def test_missing_puzzles_dir_returns_empty(self, monkeypatch, tmp_path):
        client, srv = _make_app(monkeypatch)
        # Point __file__'s directory to a temp dir with no puzzles/ subdir
        monkeypatch.setattr(srv.os.path, 'dirname',
                            lambda f: str(tmp_path))
        resp = client.get('/api/puzzle-dates')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_sorted_dates_ignoring_non_matching(self, monkeypatch, tmp_path):
        client, srv = _make_app(monkeypatch)
        puzzles_dir = tmp_path / 'puzzles'
        puzzles_dir.mkdir()
        (puzzles_dir / '2026-02-10.json').write_text('{}')
        (puzzles_dir / '2026-02-12.json').write_text('{}')
        (puzzles_dir / '2026-02-11.json').write_text('{}')
        (puzzles_dir / 'not-a-date.json').write_text('{}')
        (puzzles_dir / '2026-02-09.txt').write_text('')

        monkeypatch.setattr(srv.os.path, 'dirname',
                            lambda f: str(tmp_path))
        resp = client.get('/api/puzzle-dates')
        assert resp.status_code == 200
        assert resp.get_json() == ['2026-02-10', '2026-02-11', '2026-02-12']


# ------------------------------------------------------------------
# portkey_model_name unit tests
# ------------------------------------------------------------------

class TestPortkeyModelName:
    def test_formats_with_slug(self, monkeypatch):
        _, srv = _make_app(monkeypatch,
                           portkey_key=FAKE_PORTKEY_KEY,
                           slugs={'anthropic': 'my-ant', 'openai': 'my-oai'})

        assert srv.portkey_model_name('claude-opus-4-6') == '@my-ant/claude-opus-4-6'
        assert srv.portkey_model_name('gpt-4o') == '@my-oai/gpt-4o'

    def test_provider_has_slug(self, monkeypatch):
        _, srv = _make_app(monkeypatch,
                           portkey_key=FAKE_PORTKEY_KEY,
                           slugs={'anthropic': 'my-ant'})

        assert srv.provider_has_slug('anthropic') is True
        assert srv.provider_has_slug('openai') is False
        assert srv.provider_has_slug('google') is False

