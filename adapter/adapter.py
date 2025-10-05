"""Main poker adapter - processes console messages into game state"""

import re
from typing import Optional
from parser import StateParser
from state import GameState
from node_builder import build_node_key


class PokerAdapter:
    """
    Adapter that processes browser console messages and maintains game state.
    
    Current Status: Checkpoint 2.1/2.2 - Node key generation and board classification
    """
    
    def __init__(self, hero_user_id: Optional[int] = None):
        self.hero_user_id = hero_user_id
        self.parser: Optional[StateParser] = None
        self.last_logged_state = None
    
    def on_console_message(self, message_type: str, message_text: str):
        """
        Called when a console message arrives from the browser.
        
        Args:
            message_type: Type of message (log, info, debug, etc.)
            message_text: Formatted message text
        """
        
        # Extract user ID from authentication message
        if "[AUTH] authenticated as userId" in message_text and not self.hero_user_id:
            try:
                parts = message_text.split("userId ")
                if len(parts) > 1:
                    user_id_str = parts[1].split(",")[0]
                    self.hero_user_id = int(user_id_str)
                    self.parser = StateParser(self.hero_user_id)
                    print(f"\n✓ Authenticated as User ID: {self.hero_user_id}\n", flush=True)
            except Exception:
                pass
        
        # Parse UpdateQueue messages
        if self.parser and "[UpdateQueue]" in message_text:
            # Simple debug: show what action is being processed
            try:
                match = re.search(r'action\s*:\s*"?(\w+)"?', message_text)
                if match:
                    action = match.group(1)
                    print(f"[Processing: {action}]", flush=True)
            except Exception:
                pass
            
            try:
                state = self.parser.parse_message(message_text)
                
                if state:
                    # Only log if state has actually changed
                    state_key = self._get_state_key(state)
                    if state_key != self.last_logged_state:
                        # Check if it's hero's turn
                        is_decision_point = state.is_hero_turn()
                        self.log_game_state(state, is_decision_point)
                        self.last_logged_state = state_key
                        
            except Exception as e:
                print(f"[ERROR] Parser exception: {e}", flush=True)
    
    def _get_state_key(self, state: GameState) -> str:
        """Create a unique key for the current state to detect changes"""
        return (
            f"{state.hand_id}|{state.street}|{state.current_player_seat}|"
            f"{state.pot}|{len(state.action_history)}|"
            f"{''.join(state.community_cards)}"
        )
    
    def log_game_state(self, state: GameState, is_decision_point: bool = False):
        """
        Log game state update.
        
        Args:
            state: Current game state
            is_decision_point: True if it's hero's turn to act
        """
        print("\n" + "="*70, flush=True)
        if is_decision_point:
            print("=== 🎯 DECISION POINT 🎯 ===", flush=True)
        else:
            print("=== GAME STATE UPDATE ===", flush=True)
        print("="*70, flush=True)
        
        # Show node key only at decision points (Checkpoint 2.1/2.2)
        if is_decision_point:
            try:
                node_key = build_node_key(state)
                print(f"Node Key: {node_key}", flush=True)
            except Exception as e:
                print(f"Node Key: [Error: {e}]", flush=True)
        
        # Show who's turn it is
        if state.current_player_seat == state.hero_seat_id:
            print(f"To Act: Hero (Seat {state.current_player_seat})", flush=True)
        else:
            print(f"To Act: Villain (Seat {state.current_player_seat})", flush=True)
        
        print(f"Position: {state.get_position()}", flush=True)
        print(f"Stacks: Hero={state.get_hero_stack_bb():.1f}bb, Villain={state.get_villain_stack_bb():.1f}bb", flush=True)
        print(f"Pot: {state.pot / 2:.1f}bb", flush=True)
        print(f"Street: {state.street.lower()}", flush=True)
        
        if state.community_cards:
            print(f"Board: {' '.join(state.community_cards)}", flush=True)
        else:
            print(f"Board: -", flush=True)
        
        if state.hero_cards:
            print(f"Hole Cards: {' '.join(state.hero_cards)}", flush=True)
        else:
            print(f"Hole Cards: -", flush=True)
        
        print(f"Action History: {state.action_history}", flush=True)
        
        if is_decision_point:
            print(f"Legal Actions: {state.get_legal_actions()}", flush=True)
        
        print("="*70 + "\n", flush=True)