"""Game state data structures"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Player:
    """Represents a player in the hand"""
    seat_id: int
    user_id: Optional[int] = None
    stack: int = 0
    bet: int = 0
    state: str = "ask"  # "ask", "bet", "fold", "all_in"
    cards: Optional[List[str]] = None


@dataclass
class GameState:
    """Complete game state at a decision point"""
    # Hand info
    hand_id: Optional[int] = None
    street: str = "preflop"  # "preFlop", "flop", "turn", "river"
    
    # Table info
    dealer_seat: Optional[int] = None
    hero_seat_id: Optional[int] = None
    hero_user_id: Optional[int] = None
    
    # Pot and betting
    pot: int = 0
    current_bets: int = 0
    minimum_raise: int = 2
    
    # Cards
    hero_cards: List[str] = field(default_factory=list)
    community_cards: List[str] = field(default_factory=list)
    
    # Players
    players: List[Player] = field(default_factory=list)
    
    # Action tracking
    current_player_seat: Optional[int] = None
    action_history: List[str] = field(default_factory=list)
    
    def is_hero_turn(self) -> bool:
        """Check if it's hero's turn to act"""
        return self.current_player_seat == self.hero_seat_id
    
    def get_hero_player(self) -> Optional[Player]:
        """Get hero's player object"""
        for player in self.players:
            if player.seat_id == self.hero_seat_id:
                return player
        return None
    
    def get_hero_stack_bb(self, bb_size: int = 2) -> float:
        """Get hero's stack in big blinds"""
        hero = self.get_hero_player()
        if hero:
            return hero.stack / bb_size
        return 0.0
    
    def get_villain_stack_bb(self, bb_size: int = 2) -> float:
        """Get villain's stack in big blinds (heads-up)"""
        for player in self.players:
            if player.seat_id != self.hero_seat_id:
                return player.stack / bb_size
        return 0.0
    
    def get_position(self) -> str:
        """Get hero's position (SB/BB for heads-up)"""
        if self.dealer_seat is None or self.hero_seat_id is None:
            return "Unknown"
        # In heads-up, dealer is SB
        return "SB" if self.dealer_seat == self.hero_seat_id else "BB"
    
    def get_legal_actions(self) -> List[str]:
        """Determine legal actions based on current state"""
        actions = []
        
        if not self.is_hero_turn():
            return actions
        
        hero = self.get_hero_player()
        if not hero:
            return actions
        
        # Always can fold
        actions.append("fold")
        
        # Find max bet
        max_bet = max((p.bet for p in self.players), default=0)
        
        if hero.bet < max_bet:
            # Facing a bet - can call or raise
            actions.append("call")
            if hero.stack > 0:
                actions.append("raise")
        else:
            # No bet facing - can check or bet
            actions.append("check")
            if hero.stack > 0:
                actions.append("bet")
        
        return actions
