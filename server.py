#!/usr/bin/env python3
"""
Flask server for cnmn AI Puzzle Assistant.
Reads API keys from .env and proxies requests to AI providers.

Usage:
    pip install flask python-dotenv requests
    python server.py
"""

import os
import json
import re
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='.')

# Get API keys from environment
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')


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
def index():
    return send_from_directory('.', 'puzzle-ai-assistant.html')


@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)


@app.route('/api/providers')
def get_providers():
    """Return which AI providers are available."""
    return jsonify({
        'openai': is_key_valid(OPENAI_API_KEY, 'sk-'),
        'anthropic': is_key_valid(ANTHROPIC_API_KEY)
    })


@app.route('/api/save-puzzle', methods=['POST'])
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


@app.route('/api/chat', methods=['POST'])
def chat():
    """Proxy chat requests to the appropriate AI provider."""
    data = request.json
    provider = data.get('provider')
    prompt = data.get('prompt')

    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    if provider == 'openai':
        if not is_key_valid(OPENAI_API_KEY, 'sk-'):
            return jsonify({'error': 'OpenAI API key not configured'}), 400
        return call_openai(prompt)

    elif provider == 'anthropic':
        if not is_key_valid(ANTHROPIC_API_KEY):
            return jsonify({'error': 'Anthropic API key not configured'}), 400
        return call_anthropic(prompt)

    else:
        return jsonify({'error': f'Unknown provider: {provider}'}), 400


def call_openai(prompt):
    """Call OpenAI API."""
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {OPENAI_API_KEY}'
            },
            json={
                'model': 'gpt-4',
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.7
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return jsonify({'content': data['choices'][0]['message']['content']})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'OpenAI API error: {str(e)}'}), 500


def call_anthropic(prompt):
    """Call Anthropic API."""
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01'
            },
            json={
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 1024,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        return jsonify({'content': data['content'][0]['text']})
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Anthropic API error: {str(e)}'}), 500


if __name__ == '__main__':
    print("\n🤖 cnmn AI Puzzle Assistant Server")
    print("=" * 40)
    print(f"OpenAI:    {'✓ configured' if is_key_valid(OPENAI_API_KEY, 'sk-') else '✗ not configured'}")
    print(f"Anthropic: {'✓ configured' if is_key_valid(ANTHROPIC_API_KEY) else '✗ not configured'}")
    print("=" * 40)
    print("Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000, host='0.0.0.0')
