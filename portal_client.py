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
    """Strip characters commonly used for indirect prompt injection (zero-width
    joiners, other invisible/control chars) before any page-derived text is
    passed into the model's context. This portal's data is fully fictional and
    static, so the risk here is near-zero -- but a real production UI-operator
    agent reads content it does not control (vendor names, status messages),
    and that boundary should be enforced unconditionally, not only when a
    concrete attack is anticipated."""
    if text is None:
        return text
    return "".join(ch for ch in text if ch.isprintable() or ch in "\n\t")


def _sanitize_value(value):
    """Recursively applies _sanitize to every string leaf of a JSON-shaped
    value (dict/list/str), so every page-derived payload reaching the model
    is covered -- not just the vendor list and status line. Address dicts
    and saved-draft records are typed into the page by (in this exercise,
    fictional) requests and echoed straight back through read_drafts()/
    select_vendor(); the sanitization boundary must apply there too, not
    only at the two places an earlier pass happened to add it first."""
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
    # The page is fully local/static with zero network latency -- Playwright's
    # 30s default would only mask a genuine hang (e.g. a selector typo)
    # behind a long wait. A short fail-fast timeout is appropriate for this
    # specific fixture; it would be too aggressive against a real
    # network-backed production UI.
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
        # Safe to read #original immediately: portal.html's onchange handler
        # is plain synchronous JS (no setTimeout/promise), so by the time
        # select_option()'s event dispatch returns, the DOM mutation has
        # already happened. This would need an explicit wait if the fixture
        # ever simulated async latency here.
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
        # Same synchronous-handler invariant as select_vendor above: the
        # form's onsubmit is plain sync JS, so #status is already updated by
        # the time .click() returns -- no wait_for_function needed here.
        return _sanitize(self.page.inner_text("#status"))

    def click_reset(self) -> None:
        """Reset fictional drafts -- used only for repeatable test runs,
        never mid-flow on a single request."""
        self.page.click("#reset")
