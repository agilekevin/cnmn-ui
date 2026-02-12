"""Playwright smoke tests for the cnmn Quiz Generator UI."""

import json
import socket
import subprocess
import time
import signal
import os
import pytest
from playwright.sync_api import sync_playwright, expect


def _free_port():
    """Find a free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server():
    """Start the Flask server for smoke testing on a free port."""
    port = _free_port()
    env = os.environ.copy()
    # Clear any real slug/key vars so only our test values apply.
    # Set to empty string (not delete) so load_dotenv() won't fill them from .env.
    for k in list(env):
        if k.startswith('PORTKEY_') or k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
            env[k] = ''
    env['PORTKEY_API_KEY'] = 'pk-live-test-xxxxxxxxxxxxxxxxxxxx1'
    env['PORTKEY_SLUG_ANTHROPIC'] = 'my-anthropic'
    env['AUTH_USERS'] = ''
    env['AUTH_USERNAME'] = ''
    env['AUTH_PASSWORD'] = ''
    env['PORT'] = str(port)

    proc = subprocess.Popen(
        [os.path.join(os.path.dirname(__file__), '..', 'venv', 'bin', 'python'),
         'server.py'],
        cwd=os.path.join(os.path.dirname(__file__), '..'),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    server_url = f'http://localhost:{port}'

    # Wait for server to be ready
    for _ in range(30):
        try:
            import requests
            requests.get(f'{server_url}/api/models', timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.kill()
        raise RuntimeError("Server did not start in time")

    yield server_url, proc

    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def server_url(server):
    """Return the base URL for the test server."""
    return server[0]


@pytest.fixture(scope="module")
def browser_page(server):
    """Provide a Playwright browser page."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        yield page
        browser.close()


class TestPageLoad:
    def test_title(self, browser_page, server_url):
        browser_page.goto(server_url)
        assert 'cnmn Quiz Generator' in browser_page.title()

    def test_model_dropdown_populated(self, browser_page, server_url):
        browser_page.goto(server_url)
        # Wait for loadModels() to populate the dropdown
        browser_page.wait_for_function(
            "document.querySelector('#modelSelect').options.length > 1"
        )

        select = browser_page.locator('#modelSelect')
        options = select.locator('option').all()
        labels = [o.text_content() for o in options]

        # Should have at least one AI model + Rule-Based
        assert len(options) >= 2

        # Last option should be Rule-Based
        assert 'Rule-Based' in labels[-1]

        # At least one Claude model should appear (anthropic slug is set by fixture)
        ai_labels = labels[:-1]  # exclude Rule-Based
        assert any('Claude' in l for l in ai_labels), f"Expected at least one Claude model, got: {ai_labels}"

    def test_status_shows_via_portkey(self, browser_page, server_url):
        browser_page.goto(server_url)
        browser_page.wait_for_function(
            "document.querySelector('#modelSelect').options.length > 1"
        )
        status = browser_page.locator('#modelStatus')
        expect(status).to_have_text('via Portkey')


class TestRuleBasedQuiz:
    def test_generate_quiz_with_rules(self, browser_page, server_url):
        browser_page.goto(server_url)
        browser_page.wait_for_function(
            "document.querySelector('#modelSelect').options.length > 1"
        )

        # Select Rule-Based
        browser_page.select_option('#modelSelect', 'rules')

        # Enter theme
        browser_page.fill('#themeInput', 'Buildings')

        # Click generate
        browser_page.click('#generateBtn')

        # Wait for questions to appear
        browser_page.wait_for_selector('.question-card', timeout=5000)

        # Should have 6 question cards
        cards = browser_page.locator('.question-card').all()
        assert len(cards) == 6

        # Export section should be visible
        export = browser_page.locator('#exportSection')
        expect(export).to_be_visible()

    def test_ask_ai_disabled_in_rules_mode(self, browser_page, server_url):
        """Ask AI emoji button should be disabled when Rule-Based is selected."""
        browser_page.goto(server_url)
        browser_page.wait_for_function(
            "document.querySelector('#modelSelect').options.length > 1"
        )
        browser_page.select_option('#modelSelect', 'rules')
        browser_page.fill('#themeInput', 'Weather')
        browser_page.click('#generateBtn')
        browser_page.wait_for_selector('.question-card', timeout=5000)

        # Open emoji picker for first question
        browser_page.click('.emoji-btn')
        browser_page.wait_for_selector('.emoji-dropdown.open', timeout=2000)

        # Ask AI button should be disabled
        ai_btn = browser_page.locator('.emoji-ai-suggest').first
        expect(ai_btn).to_be_disabled()


class TestModelSelection:
    def test_default_model_is_sonnet(self, browser_page, server_url):
        """Sonnet 4.5 should be selected by default when available."""
        browser_page.goto(server_url)
        browser_page.wait_for_function(
            "document.querySelector('#modelSelect').options.length > 1"
        )

        current = browser_page.evaluate("currentModel")
        assert 'sonnet' in current, f"Expected sonnet as default, got: {current}"

        selected = browser_page.evaluate(
            "document.querySelector('#modelSelect').value"
        )
        assert selected == current

    def test_switching_model_updates_state(self, browser_page, server_url):
        browser_page.goto(server_url)
        browser_page.wait_for_function(
            "document.querySelector('#modelSelect').options.length > 1"
        )

        # Select a Claude model
        browser_page.select_option('#modelSelect', 'claude-sonnet-4-5-20250929')
        current = browser_page.evaluate("currentModel")
        assert current == 'claude-sonnet-4-5-20250929'

        # Switch to rules
        browser_page.select_option('#modelSelect', 'rules')
        current = browser_page.evaluate("currentModel")
        assert current == 'rules'
