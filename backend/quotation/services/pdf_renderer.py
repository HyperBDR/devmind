from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from playwright.sync_api import sync_playwright

# Prefer the user cache when the environment points PLAYWRIGHT_BROWSERS_PATH
# at a missing temporary directory.
_DEFAULT_BROWSERS = Path.home() / "Library" / "Caches" / "ms-playwright"


def _ensure_browsers_path() -> None:
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured and Path(configured).exists():
        return
    if _DEFAULT_BROWSERS.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_DEFAULT_BROWSERS)


@lru_cache(maxsize=1)
def _browser_available() -> bool:
    _ensure_browsers_path()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        # Allow a later retry after `playwright install chromium`.
        _browser_available.cache_clear()
        return False


def render_html_to_pdf(html: str) -> bytes:
    """Render a full HTML document to PDF bytes via headless Chromium."""
    if not html or not html.strip():
        raise ValueError("HTML content is empty")

    _ensure_browsers_path()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True, args=["--no-sandbox"]
        )
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                margin={
                    "top": "12mm",
                    "right": "12mm",
                    "bottom": "12mm",
                    "left": "12mm",
                },
            )
        finally:
            browser.close()
    return pdf_bytes
