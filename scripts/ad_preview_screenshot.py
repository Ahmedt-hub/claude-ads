#!/usr/bin/env python3
"""
Screenshot a Meta ad preview so the ad creative can be inspected visually.

Takes the `preview_url` returned by the Meta Ads MCP tool `ads_get_ad_preview`
(an iframe URL on business.facebook.com) and saves a PNG of the rendered ad.

Usage:
    python3 scripts/ad_preview_screenshot.py --url "<preview_url>" --out ad.png

Output (stdout, JSON):
    {"png": "/abs/path/ad.png", "title": "Facebook Feed"}
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
from pathlib import Path


def launch(pw):
    try:
        return pw.chromium.launch()
    except Exception:  # browser build mismatch: fall back to a system Chromium
        exe = os.environ.get("CHROMIUM_PATH") or next(
            (p for p in ["/opt/pw-browsers/chromium", shutil.which("chromium") or "",
                         shutil.which("google-chrome") or ""] if p and Path(p).exists()), None)
        if not exe:
            raise
        return pw.chromium.launch(executable_path=exe, args=["--no-sandbox"])


def main() -> int:
    ap = argparse.ArgumentParser(description="Screenshot a Meta ad preview URL.")
    ap.add_argument("--url", required=True, help="preview_url from ads_get_ad_preview")
    ap.add_argument("--out", required=True, help="Output PNG path")
    ap.add_argument("--wait-ms", type=int, default=5000, help="Time to let images load")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    url = html.unescape(args.url)  # tool output may contain &amp;
    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(viewport={"width": 420, "height": 900}, device_scale_factor=2)
        page.goto(url, timeout=45000)
        page.wait_for_timeout(args.wait_ms)
        page.screenshot(path=str(out), full_page=True)
        title = page.title()
        browser.close()
    print(json.dumps({"png": str(out), "title": title}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
