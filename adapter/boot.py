# adapter/boot.py
from pathlib import Path
import time
from playwright.sync_api import sync_playwright


AUTH_PATH = Path(__file__).with_name("auth.json")
REPLAY_URL = "https://www.casino.org/replaypoker/"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        storage_state = str(AUTH_PATH) if AUTH_PATH.exists() else None
        context = browser.new_context(storage_state=storage_state)
        page = context.new_page()
        page.goto(REPLAY_URL, wait_until="domcontentloaded")
        main_page = page
        print("Opened Replay Poker. In the browser, open a table (it will open in a new tab).\nWhen the table tab is open, return here and press Enter...")
        input()
        table_page = None
        if len(context.pages) > 1:
            table_page = context.pages[-1]
            if table_page is main_page:
                for p in context.pages:
                    if p is not main_page:
                        table_page = p
                        break
        else:
            try:
                table_page = context.wait_for_event("page", timeout=60000)
            except Exception as e:
                print("No new tab detected within 60s. Exiting.")
                return
        if table_page is None:
            print("Could not find the table tab. Exiting.")
            return
        try:
            table_page.bring_to_front()
        except Exception:
            pass
        print(f"Tracking table tab at: {table_page.url}")
        print("Press Ctrl+C here to stop tracking and close the browser.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        
if __name__ == "__main__":
    main()


