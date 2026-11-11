"""Orchestrates the operator agent across all requests in a seed file.

Starts the portal's dev server, launches one shared Playwright browser
context for the whole run (localStorage does not persist across separate
contexts), resets fictional drafts once at the start, then processes each
request in order and writes a machine-readable + human-readable report.
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from agent import make_client, run_request
from portal_client import PortalClient

PORTAL_DIR = Path(__file__).parent.parent / "client-ai-starter-pack" / "tasks" / "computer-use"
PORT = 8766
URL = f"http://127.0.0.1:{PORT}/portal.html"


def _port_free(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _start_server() -> subprocess.Popen:
    if not _port_free(PORT):
        raise RuntimeError(f"Port {PORT} already in use; stop the other server first.")
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(PORT), "--bind", "127.0.0.1", "--directory", str(PORTAL_DIR)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if not _port_free(PORT):
            return proc
        time.sleep(0.1)
    raise RuntimeError("Portal server did not start in time")


def run_all(seed_path: Path, logs_dir: Path) -> list[dict]:
    seed = json.loads(seed_path.read_text())
    requests = seed["requests"]

    load_dotenv()
    anthropic_client = make_client()
    logs_dir.mkdir(parents=True, exist_ok=True)

    server = _start_server()
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                # Single shared context/page for the whole run.
                page = browser.new_page()
                page.goto(URL)
                portal = PortalClient(page)
                portal.click_reset()

                for request in requests:
                    if request.get("simulate") == "fail next save once":
                        portal.set_fail_switch(True)

                    label = request.get("label", request.get("request_id", "?"))
                    try:
                        outcome = run_request(anthropic_client, portal, request, logs_dir)
                        results.append(
                            {
                                "request_id": outcome.request_id,
                                "status": outcome.status,
                                "reason": outcome.reason,
                                "save_attempts": outcome.save_attempts,
                                "had_failure": outcome.had_failure,
                                "new_drafts": outcome.new_drafts,
                                "transcript_path": outcome.transcript_path,
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        # One request crashing (e.g. a non-retryable API error,
                        # an unexpected Playwright failure) must not take the
                        # whole batch down -- record it and keep going, so a
                        # single bad request doesn't erase results already
                        # earned for every other request in this run.
                        results.append(
                            {
                                "request_id": label,
                                "status": "error",
                                "reason": f"{type(exc).__name__}: {exc}",
                                "save_attempts": None,
                                "had_failure": None,
                                "new_drafts": 0,
                                "transcript_path": str(logs_dir / f"{label}.json"),
                            }
                        )
            finally:
                browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    return results


def write_reports(results: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run-report.json").write_text(json.dumps(results, indent=2))

    lines = ["# Run report\n"]
    for r in results:
        lines.append(f"## {r['request_id']}")
        lines.append(f"- status: `{r['status']}`")
        lines.append(f"- reason: {r['reason']}")
        lines.append(f"- save attempts: {r['save_attempts']} (failure seen: {r['had_failure']})")
        lines.append(f"- new drafts created: {r['new_drafts']}")
        lines.append(f"- transcript: {r['transcript_path']}\n")
    (out_dir / "run-report.md").write_text("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", default=str(PORTAL_DIR / "seed.json"))
    parser.add_argument("--logs", default="logs")
    parser.add_argument("--out", default=".")
    args = parser.parse_args()

    results = run_all(Path(args.seed), Path(args.logs))
    write_reports(results, Path(args.out))
    print(json.dumps(results, indent=2))
