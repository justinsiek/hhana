"""Parse Phoenix Socket UpdateQueue messages into game state"""

import re
import json
from typing import Dict, Any, Optional
from state import GameState, Player


class StateParser:
    """
    Parses UpdateQueue messages from Replay Poker into structured GameState.
    
    UpdateQueue messages have format:
    [UpdateQueue] #{sequence}: {action} {json_data}
    """
    
    def __init__(self, hero_user_id: int):
        self.hero_user_id = hero_user_id
        self.state = GameState(hero_user_id=hero_user_id)
        self.last_sequence = -1
    
    def parse_message(self, message_text: str) -> Optional[GameState]:
        """
        Parse an UpdateQueue message and update state.
        
        Returns updated GameState after significant game events.
        """
        if "[UpdateQueue]" not in message_text:
            return None
        
        # Extract the update data
        update = self._extract_update_data(message_text)
        if not update:
            return None
        
        action = update.get("action")
        if not action:
            return None
        
        # Process based on action type
        if action == "startHand":
            self._handle_start_hand(update)
        elif action == "dealHoleCards":
            self._handle_hole_cards(update)
        elif action == "blinds":
            self._handle_blinds(update)
        elif action == "tick":
            self._handle_tick(update)
            # Return state after tick to show whose turn it is
            return self.state
        elif action in ["raise", "call", "check", "bet", "fold"]:
            self._handle_action(update)
        elif action == "dealCommunityCards":
            self._handle_community_cards(update)
        elif action == "updatePots":
            self._handle_update_pots(update)
        
        return None
    
    def _extract_update_data(self, message_text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON data from UpdateQueue message"""
        try:
            # Pattern: [UpdateQueue] #N: action {data}
            match = re.search(r'\[UpdateQueue\][^{]*({.*})$', message_text)
            if not match:
                return None
            
            json_str = match.group(1)
            
            # Convert JavaScript object notation to proper JSON
            # 1. Replace True/False/null with lowercase
            json_str = json_str.replace(': True', ': true')
            json_str = json_str.replace(': False', ': false')
            json_str = json_str.replace(':True', ':true')
            json_str = json_str.replace(':False', ':false')
            json_str = json_str.replace(': null', ': null')
            
            # 2. Quote unquoted keys - match word followed by colon
            # This regex finds words that aren't already quoted followed by a colon
            json_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)', r'\1"\2"\3', json_str)
            
            return json.loads(json_str)
        except (json.JSONDecodeError, AttributeError) as e:
            return None
    
    def _handle_start_hand(self, update: Dict):
        """Handle startHand - reset state for new hand"""
        self.state = GameState(
            hand_id=update.get("id") or update.get("handId"),
            hero_user_id=self.hero_user_id,
            dealer_seat=update.get("dealerSeat"),
            action_history=[]
        )
        
        # Find hero's seat
        seats = update.get("seats", [])
        for seat in seats:
            user_id = seat.get("userId")
            seat_id = seat.get("id")
            if user_id == self.hero_user_id:
                self.state.hero_seat_id = seat_id
                break
        
        # Initialize players
        players_data = update.get("players", [])
        for p_data in players_data:
            seat_id = p_data.get("seatId")
            # Find user_id and stack from seats
            user_id = None
            stack = 0
            for seat in seats:
                if seat.get("id") == seat_id:
                    user_id = seat.get("userId")
                    stack = seat.get("stack", 0)
                    break
            
            self.state.players.append(Player(
                seat_id=seat_id,
                user_id=user_id,
                stack=stack,
                state=p_data.get("state", "ask")
            ))
    
    def _handle_blinds(self, update: Dict):
        """Handle blinds posting"""
        players_data = update.get("players", [])
        for p_data in players_data:
            seat_id = p_data.get("seatId")
            for player in self.state.players:
                if player.seat_id == seat_id:
                    player.bet = p_data.get("bet", 0)
                    player.stack = p_data.get("stack", player.stack)
                    player.state = p_data.get("state", "ask")
        
        # Update pot (sum of bets)
        self.state.current_bets = sum(p.bet for p in self.state.players)
        self.state.minimum_raise = update.get("minimumRaise", 2)
        
        # Record action
        for p_data in players_data:
            bet = p_data.get("bet", 0)
            seat_id = p_data.get("seatId")
            if bet == 1:
                self.state.action_history.append(f"Seat{seat_id} post SB 0.5bb")
            elif bet == 2:
                self.state.action_history.append(f"Seat{seat_id} post BB 1bb")
    
    def _handle_hole_cards(self, update: Dict):
        """Handle dealHoleCards - extract hero's cards"""
        players_data = update.get("players", [])
        for p_data in players_data:
            if p_data.get("userId") == self.hero_user_id:
                cards = p_data.get("cards", [])
                self.state.hero_cards = [c for c in cards if c != "X"]
                break
    
    def _handle_tick(self, update: Dict):
        """Handle tick - whose turn it is"""
        current_player = update.get("currentPlayer", {})
        self.state.current_player_seat = current_player.get("seatId")
        
        street = update.get("state", "preFlop")
        self.state.street = street
        self.state.minimum_raise = update.get("minimumRaise", 2)
    
    def _handle_action(self, update: Dict):
        """Handle player actions (raise, call, check, bet, fold)"""
        action = update.get("action")
        seat_id = update.get("seatId")
        chips = update.get("chips", 0)
        
        # Update players
        players_data = update.get("players", [])
        for p_data in players_data:
            p_seat_id = p_data.get("seatId")
            for player in self.state.players:
                if player.seat_id == p_seat_id:
                    player.bet = p_data.get("bet", 0)
                    player.stack = p_data.get("stack", player.stack)
                    player.state = p_data.get("state", "ask")
        
        # Record action in history
        if action == "raise":
            self.state.action_history.append(f"Seat{seat_id} raises {chips}bb")
        elif action == "call":
            self.state.action_history.append(f"Seat{seat_id} calls {chips}bb")
        elif action == "check":
            self.state.action_history.append(f"Seat{seat_id} checks")
        elif action == "bet":
            self.state.action_history.append(f"Seat{seat_id} bets {chips}bb")
        elif action == "fold":
            self.state.action_history.append(f"Seat{seat_id} folds")
        
        # Update pot
        self.state.current_bets = sum(p.bet for p in self.state.players)
    
    def _handle_community_cards(self, update: Dict):
        """Handle dealCommunityCards - flop/turn/river"""
        cards = update.get("cards", [])
        
        # If 3 cards, it's the flop - replace community cards
        # If 1 card, it's turn or river - append to existing
        if len(cards) == 3:
            self.state.community_cards = cards
        elif len(cards) == 1:
            self.state.community_cards.extend(cards)
    
    def _handle_update_pots(self, update: Dict):
        """Handle updatePots - pot total updates"""
        pots = update.get("pots", [])
        total_pot = sum(pot.get("chips", 0) for pot in pots)
        self.state.pot = total_pot
        
        # Also update player states
        players_data = update.get("players", [])
        for p_data in players_data:
            seat_id = p_data.get("seatId")
            for player in self.state.players:
                if player.seat_id == seat_id:
                    player.bet = p_data.get("bet", 0)
                    if "stack" in p_data:
                        player.stack = p_data["stack"]
                    player.state = p_data.get("state", "ask")


