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


@dataclass
class Vendor:
    vendor_id: str
    name: str
    address: dict


class PortalClient:
    def __init__(self, page: Page):
        self.page = page
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
        original_text = self.page.inner_text("#original")
        try:
            original = json.loads(original_text)
        except json.JSONDecodeError:
            return None
        return original.get("address")

    def read_drafts(self) -> list[dict]:
        """Ground truth of saved state: parses the #drafts <pre> block."""
        text = self.page.inner_text("#drafts")
        return json.loads(text)

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
        return _sanitize(self.page.inner_text("#status"))

    def click_reset(self) -> None:
        """Reset fictional drafts -- used only for repeatable test runs,
        never mid-flow on a single request."""
        self.page.click("#reset")

    def snapshot(self, selected_vendor_id: Optional[str] = None) -> dict:
        """Compact text-like observation of current portal state, given to
        the model instead of a screenshot (accessibility-tree style)."""
        snap = {
            "vendors": self.list_vendors(),
            "saved_drafts": self.read_drafts(),
        }
        if selected_vendor_id:
            original_text = self.page.inner_text("#original")
            try:
                snap["selected_vendor_original_address"] = json.loads(original_text)
            except json.JSONDecodeError:
                snap["selected_vendor_original_address"] = None
        return snap
