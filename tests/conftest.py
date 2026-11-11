"""Shared fixtures for the offline (no-Anthropic-API-calls) test suite.

Everything here uses a real local HTTP server + real headless Chromium via
Playwright -- both free. Nothing in this file or the tests that use it ever
calls the Anthropic API, so the whole suite can be run as many times as
useful at zero cost.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))
from portal_client import PortalClient  # noqa: E402
from server_utils import start_server, stop_server  # noqa: E402

PORTAL_DIR = Path(__file__).parent.parent.parent / "client-ai-starter-pack" / "tasks" / "computer-use"
TEST_PORT = 8767
URL = f"http://127.0.0.1:{TEST_PORT}/portal.html"


@pytest.fixture(scope="session")
def portal_server():
    proc = start_server(TEST_PORT, PORTAL_DIR)
    yield
    stop_server(proc)


@pytest.fixture(scope="session")
def browser(portal_server):
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def portal(browser):
    """Fresh PortalClient with drafts reset, for each test function."""
    page = browser.new_page()
    page.goto(URL)
    client = PortalClient(page)
    client.click_reset()
    yield client
    page.close()
