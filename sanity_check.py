"""Throwaway manual sanity check of portal_client.py against the live portal.
Not part of the graded deliverable -- run once, then delete/ignore."""
from playwright.sync_api import sync_playwright

from portal_client import PortalClient

URL = "http://127.0.0.1:8766/portal.html"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL)

    client = PortalClient(page)
    print("vendors:", client.list_vendors())

    client.click_reset()
    print("drafts after reset:", client.read_drafts())

    addr = client.select_vendor("V1")
    print("V1 original address:", addr)

    addr_missing = client.select_vendor("V999")
    print("V999 (should be None):", addr_missing)

    status = client.fill_and_submit("TEST-1", "42 Fiction Lane", "Demo City", "00123", "Exampleland")
    print("save status:", status)
    print("drafts after save:", client.read_drafts())

    # duplicate request_id should be rejected by the portal itself
    status2 = client.fill_and_submit("TEST-1", "42 Fiction Lane", "Demo City", "00123", "Exampleland")
    print("duplicate save status:", status2)
    print("drafts after duplicate attempt:", client.read_drafts())

    # fail switch
    client.set_fail_switch(True)
    status3 = client.fill_and_submit("TEST-2", "1 A", "B", "00000", "C")
    print("fail-switch save status:", status3)
    status4 = client.fill_and_submit("TEST-2", "1 A", "B", "00000", "C")
    print("retry save status:", status4)
    print("drafts final:", client.read_drafts())

    browser.close()
