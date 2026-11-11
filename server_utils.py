"""Shared local-HTTP-server lifecycle helpers for the portal fixture.

Previously duplicated near-identically between run.py and tests/conftest.py
-- a genuine duplication risk (if one copy's port-check logic diverged from
the other, failures would get confusing to diagnose). Single copy here.
"""
from __future__ import annotations

import socket
import subprocess
import time
from contextlib import closing
from pathlib import Path


def port_free(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def start_server(port: int, directory: Path) -> subprocess.Popen:
    if not port_free(port):
        raise RuntimeError(f"Port {port} already in use; stop the other server first.")
    proc = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(directory)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if not port_free(port):
            return proc
        time.sleep(0.1)
    raise RuntimeError("Portal server did not start in time")


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
