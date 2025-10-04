"""Console logging utilities for Chrome DevTools Protocol"""

from playwright.sync_api import CDPSession


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


class ConsoleListener:
    """Handles console message formatting and routing"""
    
    def __init__(self, cdp: CDPSession, name: str, adapter=None):
        self.cdp = cdp
        self.name = name
        self.adapter = adapter
    
    def format_console_message(self, params: dict) -> str:
        """Format a console API call message"""
        args_str = ' '.join(format_value(self.cdp, arg) for arg in params['args'])
        return f"[{self.name} - {params['type']}] {args_str}"
    
    def format_log_message(self, params: dict) -> str:
        """Format a log entry message"""
        entry = params['entry']
        return f"[{self.name} - {entry['level']}] {entry['text']}"
    
    def on_console_api_called(self, params: dict):
        """Handle Runtime.consoleAPICalled event"""
        message = self.format_console_message(params)
        # Don't print - just pass to adapter
        
        # Pass to adapter if available
        if self.adapter:
            self.adapter.on_console_message(params['type'], message)
    
    def on_log_entry_added(self, params: dict):
        """Handle Log.entryAdded event"""
        if params['entry'].get('text'):
            message = self.format_log_message(params)
            # Don't print - just pass to adapter
            
            # Pass to adapter if available
            if self.adapter:
                self.adapter.on_console_message(params['entry']['level'], message)
