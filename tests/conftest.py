"""Shared fixtures for the offline (no-Anthropic-API-calls) test suite.

Everything here uses a real local HTTP server + real headless Chromium via
Playwright -- both free. Nothing in this file or the tests that use it ever
calls the Anthropic API, so the whole suite can be run as many times as
useful at zero cost.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent.parent))
from portal_client import PortalClient  # noqa: E402

PORTAL_DIR = Path(__file__).parent.parent.parent / "client-ai-starter-pack" / "tasks" / "computer-use"
TEST_PORT = 8767
URL = f"http://127.0.0.1:{TEST_PORT}/portal.html"


def _port_free(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


@pytest.fixture(scope="session")
def portal_server():
    if not _port_free(TEST_PORT):
        raise RuntimeError(f"Test port {TEST_PORT} already in use")
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(TEST_PORT), "--bind", "127.0.0.1", "--directory", str(PORTAL_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if not _port_free(TEST_PORT):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Test portal server did not start in time")
    yield
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


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
