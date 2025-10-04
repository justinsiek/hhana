"""Browser automation for Replay Poker using Playwright"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page, CDPSession

from console_logger import ConsoleListener
from adapter import PokerAdapter


AUTH_PATH = Path(__file__).with_name("auth.json")
REPLAY_URL = "https://www.casino.org/replaypoker/"


def setup_console_listener(page: Page, name: str, adapter: PokerAdapter) -> CDPSession:
    """Set up CDP console listener for a page"""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Runtime.enable")
    cdp.send("Log.enable")
    
    # Create listener with adapter hook
    listener = ConsoleListener(cdp, name, adapter)
    
    # Attach event handlers
    cdp.on("Runtime.consoleAPICalled", listener.on_console_api_called)
    cdp.on("Log.entryAdded", listener.on_log_entry_added)
    
    return cdp


def main() -> None:
    # Create adapter (will auto-detect hero_user_id from auth message)
    adapter = PokerAdapter()
    
    print("\n" + "="*70)
    print("Starting Replay Poker Adapter...")
    print("="*70 + "\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(AUTH_PATH) if AUTH_PATH.exists() else None)
        cdp_sessions = []
        
        # Auto-attach listeners to new pages (in case tables do open in popups)
        def handle_page(page: Page):
            cdp_sessions.append(setup_console_listener(page, f"Page-{len(context.pages)}", adapter))
        
        context.on("page", handle_page)
        
        # Open main page
        page = context.new_page()
        page.goto(REPLAY_URL, wait_until="domcontentloaded")
        
        print("Monitoring poker table...")
        print("(Game state will be displayed when it's your turn to act)\n")
        
        # Keep running
        try:
            while True:
                page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("\n✓ Shutting down...\n")
        finally:
            for cdp in cdp_sessions:
                try:
                    cdp.detach()
                except:
                    pass


if __name__ == "__main__":
    main()


