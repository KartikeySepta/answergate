"""Render the 1280x640 social card from scripts/social-card.html.

GitHub, Slack, X and LinkedIn all show this image when the repo or demo is shared.
Without one they fall back to a generic avatar card, which loses most of the
click-through on exactly the posts meant to drive people here.

Re-run this after renaming the project — the wordmark is baked into the image.

  python3 scripts/build_social_card.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "social-card.html"
OUT = ROOT / "docs" / "demo" / "social-card.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    # device_scale_factor=2 so the text stays crisp when platforms downscale it.
    page = browser.new_page(viewport={"width": 1280, "height": 640}, device_scale_factor=2)
    page.goto(SRC.as_uri())
    page.wait_for_timeout(1800)          # let the webfont land before capturing
    page.screenshot(path=str(OUT))
    browser.close()

print(f"wrote {OUT.relative_to(ROOT)}")
