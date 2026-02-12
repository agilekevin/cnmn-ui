"""Playwright smoke tests for the cnmn Puzzle Editor UI."""

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
        # Auto-accept beforeunload dialogs so goto() works when page is dirty
        page.on("dialog", lambda dialog: dialog.accept())
        yield page
        browser.close()


class TestEditorPageLoad:
    def test_title(self, browser_page, server_url):
        browser_page.goto(f'{server_url}/puzzle-editor.html')
        assert 'cnmn Puzzle Editor' in browser_page.title()

    def test_date_picker_populated(self, browser_page, server_url):
        browser_page.goto(f'{server_url}/puzzle-editor.html')
        browser_page.wait_for_function("puzzle !== null", timeout=5000)

        options = browser_page.locator('#dateSelect option').all()
        assert len(options) >= 2, f"Expected multiple date options, got {len(options)}"

    def test_auto_loads_most_recent_puzzle(self, browser_page, server_url):
        browser_page.goto(f'{server_url}/puzzle-editor.html')
        browser_page.wait_for_function("puzzle !== null", timeout=5000)

        theme = browser_page.evaluate("document.getElementById('themeInput').value")
        assert theme, "Theme input should be populated after auto-load"

        cards = browser_page.locator('.question-card').all()
        assert len(cards) > 0, "Question cards should be rendered"


class TestEditorQuestionCards:
    def test_question_cards_rendered(self, browser_page, server_url):
        browser_page.goto(f'{server_url}/puzzle-editor.html')
        browser_page.wait_for_function("puzzle !== null", timeout=5000)
        browser_page.wait_for_selector('.question-card', timeout=5000)

        expected = browser_page.evaluate("puzzle.questions.length")
        actual = len(browser_page.locator('.question-card').all())
        assert actual == expected, f"Expected {expected} cards, got {actual}"

    def test_edit_theme_marks_dirty(self, browser_page, server_url):
        browser_page.goto(f'{server_url}/puzzle-editor.html')
        browser_page.wait_for_function("puzzle !== null && dirty === false", timeout=5000)

        indicator = browser_page.locator('#dirtyIndicator')
        expect(indicator).to_be_hidden()

        browser_page.fill('#themeInput', 'New Test Theme')

        expect(indicator).to_be_visible()
        assert browser_page.evaluate("dirty") is True


class TestEditorDisguises:
    def test_regen_all_disguises(self, browser_page, server_url):
        browser_page.goto(f'{server_url}/puzzle-editor.html')
        browser_page.wait_for_function("puzzle !== null", timeout=5000)
        browser_page.wait_for_selector('.question-card', timeout=5000)

        browser_page.click('text=Re-derive All Disguises')

        toast = browser_page.wait_for_selector('.toast', timeout=3000)
        assert 'All disguises re-derived' in toast.text_content()

        assert browser_page.evaluate("dirty") is True


class TestEditorSave:
    def test_save_clears_dirty(self, browser_page, server_url):
        browser_page.goto(f'{server_url}/puzzle-editor.html')
        browser_page.wait_for_function("puzzle !== null && dirty === false", timeout=5000)

        # Edit theme to a value that differs from whatever was loaded
        original_theme = browser_page.evaluate("puzzle.theme")
        new_theme = original_theme + ' (edited)'
        browser_page.fill('#themeInput', new_theme)

        indicator = browser_page.locator('#dirtyIndicator')
        expect(indicator).to_be_visible()

        # Save
        browser_page.click('button:has-text("Save")')

        toast = browser_page.wait_for_selector('.toast', timeout=3000)
        assert 'Puzzle saved' in toast.text_content()

        assert browser_page.evaluate("dirty") is False
        expect(indicator).to_be_hidden()

        # Restore original theme so the test is idempotent
        browser_page.fill('#themeInput', original_theme)
        browser_page.click('button:has-text("Save")')
        browser_page.wait_for_selector('.toast', timeout=3000)
