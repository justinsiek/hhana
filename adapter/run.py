"""Browser automation for Replay Poker using Playwright"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page, CDPSession

from console_logger import ConsoleListener
from adapter import PokerAdapter


AUTH_PATH = Path(__file__).with_name("auth.json")
REPLAY_URL = "https://www.casino.org/replaypoker/"


def setup_console_listener(page: Page, adapter: PokerAdapter) -> CDPSession:
    """Set up CDP console listener for a page"""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Runtime.enable")
    cdp.send("Log.enable")
    
    # Create listener with adapter hook
    listener = ConsoleListener(cdp, "Table", adapter)
    
    # Attach event handlers
    cdp.on("Runtime.consoleAPICalled", listener.on_console_api_called)
    cdp.on("Log.entryAdded", listener.on_log_entry_added)
    
    return cdp


def main() -> None:
    adapter = PokerAdapter()
    
    print("\n" + "="*70)
    print("Starting Replay Poker Adapter...")
    print("="*70 + "\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        
        # Load auth state if available
        storage_state = str(AUTH_PATH) if AUTH_PATH.exists() else None
        context = browser.new_context(storage_state=storage_state)
        
        # Open main page and attach listener
        page = context.new_page()
        cdp = setup_console_listener(page, adapter)
        page.goto(REPLAY_URL, wait_until="domcontentloaded")
        
        print("Monitoring poker table...\n")
        
        # Keep running
        try:
            while True:
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("\n✓ Shutting down...\n")
        finally:
            try:
                cdp.detach()
            except:
                pass


if __name__ == "__main__":
    main()


