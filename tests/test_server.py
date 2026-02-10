"""Integration tests for the cnmn server Portkey gateway."""

import json
import os
import pytest
import requests_mock as rmock

# Patch env before importing server
for var in ('PORTKEY_API_KEY', 'PORTKEY_SLUG_ANTHROPIC', 'PORTKEY_SLUG_OPENAI',
            'PORTKEY_SLUG_GOOGLE', 'UNSPLASH_ACCESS_KEY', 'AUTH_USERNAME',
            'AUTH_PASSWORD'):
    os.environ.pop(var, None)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure a clean env for every test."""
    for var in ('PORTKEY_API_KEY', 'PORTKEY_SLUG_ANTHROPIC', 'PORTKEY_SLUG_OPENAI',
                'PORTKEY_SLUG_GOOGLE', 'UNSPLASH_ACCESS_KEY', 'AUTH_USERNAME',
                'AUTH_PASSWORD', 'RENDER', 'PRODUCTION'):
        monkeypatch.delenv(var, raising=False)


def _make_app(monkeypatch, portkey_key='', slugs=None, unsplash_key=''):
    """Create a fresh Flask test client with the given env config.

    slugs: dict mapping provider -> slug, e.g. {'anthropic': 'my-anthropic'}
    """
    import server

    monkeypatch.setattr(server, 'PORTKEY_API_KEY', portkey_key)
    monkeypatch.setattr(server, 'PROVIDER_SLUGS', slugs if slugs else {})
    monkeypatch.setattr(server, 'UNSPLASH_ACCESS_KEY', unsplash_key)
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


# ------------------------------------------------------------------
# /api/unsplash/search
# ------------------------------------------------------------------

UNSPLASH_SEARCH_URL = 'https://api.unsplash.com/search/photos'
FAKE_UNSPLASH_KEY = 'test-unsplash-key-123'

FAKE_UNSPLASH_RESPONSE = {
    'total': 1,
    'results': [{
        'id': 'abc123',
        'urls': {
            'thumb': 'https://images.unsplash.com/photo-abc?w=200',
            'small': 'https://images.unsplash.com/photo-abc?w=400',
            'regular': 'https://images.unsplash.com/photo-abc?w=1080',
        },
        'alt_description': 'a sunset over mountains',
        'user': {
            'name': 'Jane Doe',
            'username': 'janedoe',
            'links': {'html': 'https://unsplash.com/@janedoe'},
        },
    }],
}


class TestUnsplashSearch:
    def test_search_returns_results(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)

        with rmock.Mocker() as m:
            m.get(UNSPLASH_SEARCH_URL, json=FAKE_UNSPLASH_RESPONSE)

            resp = client.get('/api/unsplash/search?query=sunset')
            data = resp.get_json()

            assert resp.status_code == 200
            assert data['total'] == 1
            assert len(data['results']) == 1
            result = data['results'][0]
            assert result['id'] == 'abc123'
            assert result['thumb'] == 'https://images.unsplash.com/photo-abc?w=200'
            assert result['credit']['name'] == 'Jane Doe'
            assert result['credit']['username'] == 'janedoe'

    def test_search_sends_auth_header(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)

        with rmock.Mocker() as m:
            m.get(UNSPLASH_SEARCH_URL, json=FAKE_UNSPLASH_RESPONSE)

            client.get('/api/unsplash/search?query=sunset')

            assert m.last_request.headers['Authorization'] == f'Client-ID {FAKE_UNSPLASH_KEY}'

    def test_search_no_query_returns_400(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)
        resp = client.get('/api/unsplash/search')
        assert resp.status_code == 400
        assert 'No query' in resp.get_json()['error']

    def test_search_no_key_returns_400(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key='')
        resp = client.get('/api/unsplash/search?query=sunset')
        assert resp.status_code == 400
        assert 'not configured' in resp.get_json()['error']

    def test_search_per_page_capped_at_30(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)

        with rmock.Mocker() as m:
            m.get(UNSPLASH_SEARCH_URL, json={'total': 0, 'results': []})

            client.get('/api/unsplash/search?query=sunset&per_page=100')

            assert m.last_request.qs['per_page'] == ['30']

    def test_search_api_error(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)

        with rmock.Mocker() as m:
            m.get(UNSPLASH_SEARCH_URL, status_code=500)

            resp = client.get('/api/unsplash/search?query=sunset')
            assert resp.status_code == 500
            assert 'Unsplash API error' in resp.get_json()['error']


# ------------------------------------------------------------------
# /api/unsplash/download
# ------------------------------------------------------------------

class TestUnsplashDownload:
    def test_download_trigger_success(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)

        with rmock.Mocker() as m:
            m.get('https://api.unsplash.com/photos/abc123/download', json={})

            resp = client.post('/api/unsplash/download',
                               json={'photo_id': 'abc123'})
            assert resp.status_code == 200
            assert resp.get_json()['ok'] is True
            assert m.called

    def test_download_no_photo_id_returns_400(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)
        resp = client.post('/api/unsplash/download', json={'photo_id': ''})
        assert resp.status_code == 400

    def test_download_no_key_returns_400(self, monkeypatch):
        client, _ = _make_app(monkeypatch, unsplash_key='')
        resp = client.post('/api/unsplash/download',
                           json={'photo_id': 'abc123'})
        assert resp.status_code == 400

    def test_download_api_failure_still_returns_ok(self, monkeypatch):
        """Download trigger is best-effort; API failure doesn't block the user."""
        client, _ = _make_app(monkeypatch, unsplash_key=FAKE_UNSPLASH_KEY)

        with rmock.Mocker() as m:
            m.get('https://api.unsplash.com/photos/abc123/download',
                  exc=Exception('network error'))

            resp = client.post('/api/unsplash/download',
                               json={'photo_id': 'abc123'})
            assert resp.status_code == 200
            assert resp.get_json()['ok'] is True
