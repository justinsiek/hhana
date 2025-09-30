from pathlib import Path
from playwright.sync_api import sync_playwright, Page, CDPSession


AUTH_PATH = Path(__file__).with_name("auth.json")
REPLAY_URL = "https://www.casino.org/replaypoker/"


def setup_cdp_console_listener(page: Page, page_name: str = "Page") -> CDPSession | None:
    """
    Set up console listener using Chrome DevTools Protocol (CDP).
    This captures console messages that may be intercepted by libraries like Bugsnag.
    """
    try:
        cdp = page.context.new_cdp_session(page)
        
        # Enable Runtime and Log domains
        cdp.send("Runtime.enable")
        cdp.send("Log.enable")
        
        def handle_console_api(params: dict) -> None:
            """Handle console.log/warn/error/etc calls"""
            msg_type = params.get("type", "log")
            args = params.get("args", [])
            
            # Extract message text from console arguments
            parts = []
            for arg in args:
                if arg.get("type") == "string":
                    parts.append(arg.get("value", ""))
                elif arg.get("description"):
                    parts.append(arg.get("description"))
                elif arg.get("value") is not None:
                    parts.append(str(arg.get("value")))
            
            message = " ".join(parts)
            if message:
                print(f"[{page_name} - {msg_type}] {message}", flush=True)
        
        def handle_log_entry(params: dict) -> None:
            """Handle additional log entries"""
            entry = params.get("entry", {})
            level = entry.get("level", "log")
            text = entry.get("text", "")
            if text:
                print(f"[{page_name} - {level}] {text}", flush=True)
        
        cdp.on("Runtime.consoleAPICalled", handle_console_api)
        cdp.on("Log.entryAdded", handle_log_entry)
        
        print(f"✓ CDP listener attached to {page_name}", flush=True)
        return cdp
    except Exception as e:
        print(f"✗ Failed to attach CDP listener to {page_name}: {e}", flush=True)
        return None


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        storage_state = str(AUTH_PATH) if AUTH_PATH.exists() else None
        context = browser.new_context(storage_state=storage_state)
        
        cdp_sessions = []
        
        # Attach CDP listener to all new pages immediately when created
        def handle_new_page(page: Page) -> None:
            page_num = len(context.pages)
            print(f"\n! New page detected (#{page_num})", flush=True)
            cdp = setup_cdp_console_listener(page, f"Page-{page_num}")
            if cdp:
                cdp_sessions.append(cdp)
        
        context.on("page", handle_new_page)
        
        # Open Replay Poker main page
        page = context.new_page()
        page.goto(REPLAY_URL, wait_until="domcontentloaded")
        
        print("\n" + "="*70, flush=True)
        print("Opened Replay Poker. Click a table to open it in a new tab.", flush=True)
        print("="*70 + "\n", flush=True)
        
        # Wait for table page to open
        try:
            table_page = context.wait_for_event("page", timeout=120000)
            print(f"\n✓ Table page opened: {table_page.url}", flush=True)
        except TimeoutError:
            print("No new tab detected within 2 minutes. Exiting.", flush=True)
            return
        
        # Bring table to front
        try:
            table_page.bring_to_front()
        except Exception:
            pass
        
        print("\n" + "="*70, flush=True)
        print("🎯 Console messages will appear below:", flush=True)
        print("="*70 + "\n", flush=True)
        
        # Keep running and processing events
        try:
            while True:
                table_page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            print("\nStopping...", flush=True)
        finally:
            # Clean up CDP sessions
            for cdp in cdp_sessions:
                try:
                    cdp.detach()
                except Exception:
                    pass


if __name__ == "__main__":
    main()


