from pathlib import Path
from playwright.sync_api import sync_playwright, Page, CDPSession


AUTH_PATH = Path(__file__).with_name("auth.json")
REPLAY_URL = "https://www.casino.org/replaypoker/"


def format_value(cdp: CDPSession, obj: dict, depth: int = 0, max_depth: int = 10) -> str:
    """Recursively format console values, expanding objects and arrays"""
    if depth >= max_depth:
        return "..."
    
    obj_type = obj.get("type")
    
    # Simple types
    if obj_type == "string":
        return f'"{obj.get("value", "")}"'
    if obj_type in ("number", "boolean", "undefined"):
        return str(obj.get("value", ""))
    if obj.get("subtype") == "null":
        return "null"
    
    # Complex types - fetch properties
    object_id = obj.get("objectId")
    if not object_id:
        return obj.get("description", "Object")
    
    try:
        props = cdp.send("Runtime.getProperties", {"objectId": object_id, "ownProperties": True})["result"]
        
        # Array
        if obj.get("subtype") == "array":
            items = [(int(p["name"]), format_value(cdp, p["value"], depth + 1, max_depth)) 
                     for p in props if p["name"].isdigit() and int(p["name"]) < 15]
            items.sort()
            return f"[{', '.join(v for _, v in items)}]"
        
        # Object
        items = [f"{p['name']}: {format_value(cdp, p['value'], depth + 1, max_depth)}" 
                 for p in props[:15] if p["name"] not in ("__proto__", "constructor") and not p.get("get")]
        return f"{{{', '.join(items)}}}"
    
    except Exception:
        return obj.get("description", "Object")


def setup_console_listener(page: Page, name: str) -> CDPSession:
    """Set up CDP console listener for a page"""
    cdp = page.context.new_cdp_session(page)
    cdp.send("Runtime.enable")
    cdp.send("Log.enable")
    
    cdp.on("Runtime.consoleAPICalled", 
           lambda p: print(f"[{name} - {p['type']}] {' '.join(format_value(cdp, arg) for arg in p['args'])}", flush=True))
    cdp.on("Log.entryAdded", 
           lambda p: print(f"[{name} - {p['entry']['level']}] {p['entry']['text']}", flush=True) if p['entry']['text'] else None)
    
    print(f"✓ Listener attached to {name}", flush=True)
    return cdp


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(AUTH_PATH) if AUTH_PATH.exists() else None)
        cdp_sessions = []
        
        # Auto-attach listeners to new pages
        def handle_page(page: Page):
            print(f"\n! New page #{len(context.pages)}", flush=True)
            cdp_sessions.append(setup_console_listener(page, f"Page-{len(context.pages)}"))
        
        context.on("page", handle_page)
        
        # Open main page
        page = context.new_page()
        page.goto(REPLAY_URL, wait_until="domcontentloaded")
        
        print("\n" + "="*70, flush=True)
        print("Waiting for table to open...", flush=True)
        print("="*70 + "\n", flush=True)
        
        # Wait for table page
        try:
            table_page = context.wait_for_event("page", timeout=120000)
            table_page.bring_to_front()
        except (TimeoutError, Exception):
            print("No table opened", flush=True)
            return
        
        print(f"\n✓ Table: {table_page.url}\n", flush=True)
        
        # Keep running
        try:
            while True:
                table_page.wait_for_timeout(1000)
        except KeyboardInterrupt:
            pass
        finally:
            for cdp in cdp_sessions:
                try:
                    cdp.detach()
                except:
                    pass


if __name__ == "__main__":
    main()


