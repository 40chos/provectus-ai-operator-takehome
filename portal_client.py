"""Bounded DOM action layer over the fictional vendor portal.

This module is the ONLY thing allowed to touch Playwright/the raw page.
It exposes a small, explicit set of operations -- no raw selector/click
access leaks past this module. The agent never sees a CSS selector.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import Page


def _sanitize(text: str) -> str:
    """Strips invisible/control chars from page-derived text before it
    reaches the model's context (defense against indirect prompt injection)."""
    if text is None:
        return text
    return "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")


def _sanitize_value(value):
    """Recursively applies _sanitize to every string leaf of a dict/list."""
    if isinstance(value, str):
        return _sanitize(value)
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    return value


@dataclass
class Vendor:
    vendor_id: str
    name: str
    address: dict


class PortalClient:
    # Short fail-fast timeout: this page is local/static with zero network
    # latency, so Playwright's 30s default would only mask a genuine hang.
    DEFAULT_TIMEOUT_MS = 5000

    def __init__(self, page: Page):
        self.page = page
        page.set_default_timeout(self.DEFAULT_TIMEOUT_MS)
        self._vendors: list[Vendor] = []
        self._load_vendor_list()

    def _load_vendor_list(self) -> None:
        options = self.page.eval_on_selector_all(
            "#vendor option",
            "els => els.map(e => ({value: e.value, text: e.textContent}))",
        )
        vendors = []
        for opt in options:
            if not opt["value"]:
                continue
            # option text is "V1 — Cedar Office"; strip the id/em-dash prefix
            text = _sanitize(opt["text"])
            name = text.split("—", 1)[1].strip() if "—" in text else text
            vendors.append(Vendor(vendor_id=_sanitize(opt["value"]), name=name, address={}))
        self._vendors = vendors

    def list_vendors(self) -> list[dict]:
        """Static vendor_id/name list, as shown in the portal dropdown."""
        return [{"vendor_id": v.vendor_id, "name": v.name} for v in self._vendors]

    def select_vendor(self, vendor_id: str) -> Optional[dict]:
        """Select a vendor by exact ID. Returns its original address, or
        None if the ID does not exist in the portal."""
        if vendor_id not in [v.vendor_id for v in self._vendors]:
            return None
        self.page.select_option("#vendor", vendor_id)
        # Safe to read immediately: onchange is plain sync JS, no async latency.
        original_text = self.page.inner_text("#original")
        try:
            original = json.loads(original_text)
        except json.JSONDecodeError:
            return None
        return _sanitize_value(original.get("address"))

    def read_drafts(self) -> list[dict]:
        """Ground truth of saved state: parses the #drafts <pre> block."""
        text = self.page.inner_text("#drafts")
        return _sanitize_value(json.loads(text))

    def set_fail_switch(self, value: bool) -> None:
        """Toggle the 'Simulate failure on next save' checkbox."""
        checkbox = self.page.locator("#fail")
        is_checked = checkbox.is_checked()
        if is_checked != value:
            checkbox.set_checked(value)

    def fill_and_submit(
        self, request_id: str, line1: str, city: str, postal_code: str, country: str
    ) -> str:
        """Fill the address-draft form and click Save. Returns the
        resulting #status text (success or failure message)."""
        self.page.fill("#request", request_id)
        self.page.fill("#line1", line1)
        self.page.fill("#city", city)
        self.page.fill("#postal_code", postal_code)
        self.page.fill("#country", country)
        self.page.click("button:has-text('Save draft')")
        # Same sync-handler invariant as select_vendor above.
        return _sanitize(self.page.inner_text("#status"))

    def click_reset(self) -> None:
        """Reset fictional drafts -- used only for repeatable test runs,
        never mid-flow on a single request."""
        self.page.click("#reset")
