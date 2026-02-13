#!/usr/bin/env python3
"""
Flask server for cnmn AI Puzzle Assistant.
Routes LLM requests through Portkey AI Gateway.

Usage:
    pip install flask python-dotenv requests
    python server.py

Environment variables:
    PORTKEY_API_KEY          - Portkey AI Gateway API key (required for AI features)
    PORTKEY_SLUG_ANTHROPIC   - Portkey provider slug for Anthropic
    PORTKEY_SLUG_OPENAI      - Portkey provider slug for OpenAI
    PORTKEY_SLUG_GOOGLE      - Portkey provider slug for Google
    AUTH_USERS               - Comma-separated user:pass pairs (e.g. "alice:pw1,bob:pw2")
    AUTH_USERNAME            - (legacy) Single-user fallback if AUTH_USERS is not set
    AUTH_PASSWORD            - (legacy) Single-user fallback if AUTH_USERS is not set
"""

import os
import json
import re
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, Response
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='.')

# Get API keys from environment
PORTKEY_API_KEY = os.getenv('PORTKEY_API_KEY', '')
# Auth credentials: AUTH_USERS="user1:pass1,user2:pass2" or legacy AUTH_USERNAME/AUTH_PASSWORD
def _parse_auth_users():
    """Parse AUTH_USERS env var into {username: password} dict."""
    raw = os.getenv('AUTH_USERS', '')
    users = {}
    for pair in raw.split(','):
        pair = pair.strip()
        if ':' in pair:
            user, pw = pair.split(':', 1)
            if user and pw:
                users[user] = pw
    # Legacy fallback
    if not users:
        u = os.getenv('AUTH_USERNAME', '')
        p = os.getenv('AUTH_PASSWORD', '')
        if u and p:
            users[u] = p
    return users

AUTH_USERS = _parse_auth_users()

# Model registry: model ID -> metadata
MODELS = {
    'claude-opus-4-6':             {'provider': 'anthropic', 'name': 'Claude Opus 4.6'},
    'claude-sonnet-4-5-20250929':  {'provider': 'anthropic', 'name': 'Claude Sonnet 4.5'},
    'claude-haiku-4-5-20251001':   {'provider': 'anthropic', 'name': 'Claude Haiku 4.5'},
    'gpt-4o':                      {'provider': 'openai',    'name': 'GPT-4o'},
    'gpt-4o-mini':                 {'provider': 'openai',    'name': 'GPT-4o Mini'},
    'o3-mini':                     {'provider': 'openai',    'name': 'o3 Mini'},
    'gemini-2.0-flash':            {'provider': 'google',    'name': 'Gemini 2.0 Flash'},
}

# Per-provider Portkey slugs (from Model Catalog)
# e.g. PORTKEY_SLUG_ANTHROPIC=my-anthropic -> {'anthropic': 'my-anthropic'}
PROVIDER_SLUGS = {
    k.replace('PORTKEY_SLUG_', '').lower(): v
    for k, v in os.environ.items()
    if k.startswith('PORTKEY_SLUG_') and v
}


def check_auth(username, password):
    """Check if username/password combination is valid."""
    return AUTH_USERS.get(username) == password


def authenticate():
    """Send 401 response to trigger basic auth."""
    return Response(
        'Authentication required.\n',
        401,
        {'WWW-Authenticate': 'Basic realm="cnmn Quiz Generator"'}
    )


def is_production():
    """Check if running in production (Render, etc.)."""
    return os.getenv('RENDER') == 'true' or os.getenv('PRODUCTION') == 'true'


def auth_not_configured_error():
    """Return error page when auth is required but not configured."""
    return Response(
        '''<!DOCTYPE html>
<html>
<head><title>Configuration Error</title></head>
<body style="font-family: sans-serif; padding: 40px; text-align: center;">
  <h1>⚠️ Authentication Not Configured</h1>
  <p>This app requires AUTH_USERS (or AUTH_USERNAME and AUTH_PASSWORD) environment variables to be set.</p>
  <p>Please configure these in your Render dashboard and redeploy.</p>
</body>
</html>''',
        500,
        {'Content-Type': 'text/html'}
    )


def requires_auth(f):
    """Decorator to require HTTP Basic Auth if credentials are configured."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # In production, require auth to be configured
        if is_production() and not AUTH_USERS:
            return auth_not_configured_error()

        # Skip auth check if no credentials configured (local dev)
        if not AUTH_USERS:
            return f(*args, **kwargs)

        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def is_key_valid(key, prefix=''):
    """Check if an API key looks valid (not empty or placeholder)."""
    if not key:
        return False
    if key.startswith('sk-your') or key.startswith('sk-ant-your'):
        return False
    if prefix and not key.startswith(prefix):
        return False
    return len(key) > 20


@app.route('/')
@requires_auth
def index():
    return send_from_directory('.', 'puzzle-editor.html')


@app.route('/<path:filename>')
@requires_auth
def serve_static(filename):
    return send_from_directory('.', filename)


def provider_has_slug(provider):
    """Check if a provider has a Portkey slug configured."""
    return provider in PROVIDER_SLUGS


@app.route('/api/models')
@requires_auth
def get_models():
    """Return available models and gateway status.

    Only includes models whose provider has a slug configured.
    """
    portkey_configured = is_key_valid(PORTKEY_API_KEY)
    models = {}
    if portkey_configured:
        for model_id, meta in MODELS.items():
            if provider_has_slug(meta['provider']):
                models[model_id] = meta
    return jsonify({
        'models': models,
        'portkey': portkey_configured,
        'rules': True,
    })


@app.route('/api/save-puzzle', methods=['POST'])
@requires_auth
def save_puzzle():
    """Save puzzle JSON to the puzzles directory."""
    data = request.json

    pub_date = data.get('publicationDate')
    if not pub_date:
        return jsonify({'error': 'No publication date provided'}), 400

    # Validate date format (YYYY-MM-DD)
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', pub_date):
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Ensure puzzles directory exists
    puzzles_dir = os.path.join(os.path.dirname(__file__), 'puzzles')
    os.makedirs(puzzles_dir, exist_ok=True)

    # Write file
    filename = f'{pub_date}.json'
    filepath = os.path.join(puzzles_dir, filename)

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    return jsonify({'success': True, 'filename': f'puzzles/{filename}'})


@app.route('/api/puzzle-dates')
@requires_auth
def puzzle_dates():
    """Return sorted list of existing puzzles with date and theme."""
    puzzles_dir = os.path.join(os.path.dirname(__file__), 'puzzles')
    if not os.path.isdir(puzzles_dir):
        return jsonify([])
    results = []
    for f in os.listdir(puzzles_dir):
        if re.match(r'^\d{4}-\d{2}-\d{2}\.json$', f):
            date = f[:-5]
            theme = ''
            try:
                with open(os.path.join(puzzles_dir, f)) as fh:
                    theme = json.load(fh).get('theme', '')
            except (json.JSONDecodeError, OSError):
                pass
            results.append({'date': date, 'theme': theme})
    results.sort(key=lambda r: r['date'])
    return jsonify(results)


@app.route('/api/puzzle/<date>')
@requires_auth
def get_puzzle(date):
    """Return a single puzzle JSON by date."""
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    puzzles_dir = os.path.join(os.path.dirname(__file__), 'puzzles')
    filepath = os.path.join(puzzles_dir, f'{date}.json')

    if not os.path.isfile(filepath):
        return jsonify({'error': f'No puzzle found for {date}'}), 404

    try:
        with open(filepath) as f:
            data = json.load(f)
        return jsonify(data)
    except (json.JSONDecodeError, OSError) as e:
        return jsonify({'error': f'Failed to read puzzle: {str(e)}'}), 500


@app.route('/api/chat', methods=['POST'])
@requires_auth
def chat():
    """Proxy chat requests through Portkey AI Gateway."""
    data = request.json
    model = data.get('model')
    prompt = data.get('prompt')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    if not model or model not in MODELS:
        return jsonify({'error': f'Unknown model: {model}'}), 400

    if not is_key_valid(PORTKEY_API_KEY):
        return jsonify({'error': 'Portkey API key not configured'}), 400

    provider = MODELS[model]['provider']
    if not provider_has_slug(provider):
        return jsonify({
            'error': f'No Portkey slug configured for {provider}. '
                     f'Set PORTKEY_SLUG_{provider.upper()} in .env'
        }), 400

    max_tokens = data.get('max_tokens', 1024)
    try:
        max_tokens = int(max_tokens)
    except (TypeError, ValueError):
        max_tokens = 1024
    max_tokens = max(1, min(max_tokens, 8192))

    return call_portkey(model, prompt, max_tokens=max_tokens)


def portkey_model_name(model):
    """Build the @slug/model format for Portkey Model Catalog.

    e.g. 'claude-haiku-4-5-20251001' with slug 'anthropic'
         -> '@anthropic/claude-haiku-4-5-20251001'
    """
    provider = MODELS[model]['provider']
    slug = PROVIDER_SLUGS[provider]
    return f'@{slug}/{model}'


def call_portkey(model, prompt, max_tokens=1024):
    """Call LLM via Portkey AI Gateway using Model Catalog slugs."""
    headers = {
        'Content-Type': 'application/json',
        'x-portkey-api-key': PORTKEY_API_KEY,
    }

    try:
        response = requests.post(
            'https://api.portkey.ai/v1/chat/completions',
            headers=headers,
            json={
                'model': portkey_model_name(model),
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': max_tokens,
                'temperature': 0.7,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        result = {'content': data['choices'][0]['message']['content']}
        if 'usage' in data:
            result['usage'] = data['usage']
        return jsonify(result)
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Portkey API error: {str(e)}'}), 500


if __name__ == '__main__':
    print("\n🤖 cnmn Quiz Generator Server")
    print("=" * 40)
    print(f"Portkey:   {'✓ configured' if is_key_valid(PORTKEY_API_KEY) else '✗ not configured'}")
    if PROVIDER_SLUGS:
        print(f"Providers: {', '.join(f'{p} (@{s})' for p, s in PROVIDER_SLUGS.items())}")
    else:
        print("Providers: none (set PORTKEY_SLUG_ANTHROPIC etc. in .env)")
    print(f"Auth:      {'✓ ' + str(len(AUTH_USERS)) + ' user(s)' if AUTH_USERS else '✗ disabled (open access)'}")
    print("=" * 40)
    port = int(os.getenv('PORT', 5000))
    print(f"Open http://localhost:{port} in your browser\n")
    app.run(debug=True, port=port, host='0.0.0.0')
