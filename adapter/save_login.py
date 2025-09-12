# save_login.py
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=False)
    ctx = b.new_context()
    page = ctx.new_page()
    page.goto("https://www.replaypoker.com/")
    input("Log in, then press Enter...")
    ctx.storage_state(path="adapter/auth.json")
    b.close()