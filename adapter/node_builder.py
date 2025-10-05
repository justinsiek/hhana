"""Node key generation for poker game states"""

import re
from typing import List
from state import GameState
from board_classifier import classify_board


def build_node_key(state: GameState) -> str:
    """
    Build a node key for the current game state.
    
    Node key format:
    - Preflop: "PF|{position}|{facing}|{pot_class}|{stack_bucket}"
    - Postflop: "POST|{role}|{pot_class}|{street}|{line}|{board_bucket}|{stack_bucket}"
    
    Args:
        state: Current game state
    
    Returns:
        Node key string
    """
    position = state.get_position()
    stack_bb = state.get_hero_stack_bb()
    stack_bucket = get_stack_bucket(stack_bb)
    pot_class = get_pot_class(state)
    
    # Preflop
    if state.street.lower() == "preflop":
        facing = get_facing_state(state)
        return f"PF|{position}|{facing}|{pot_class}|{stack_bucket}"
    
    # Postflop
    else:
        role = get_postflop_role(state, pot_class)
        line = get_postflop_line(state)
        board_bucket = classify_board(state.community_cards)
        return f"POST|{role}|{pot_class}|{state.street}|{line}|{board_bucket}|{stack_bucket}"


def get_facing_state(state: GameState) -> str:
    """
    Determine what the hero is facing based on action history.
    
    Facing states:
    - Unopened: No raises yet (hero first to act or only limps before)
    - Limped: Someone limped, no raises
    - Open_s/m/l: Facing an open raise (small/medium/large)
    - 3Bet_s/jam: Facing a 3bet
    - 4Bet_s/jam: Facing a 4bet
    
    Args:
        state: Current game state
    
    Returns:
        Facing state string
    """
    actions = state.action_history
    
    # Count raises/bets (excluding blinds)
    non_blind_actions = [a for a in actions if "post" not in a.lower()]
    raise_count = sum(1 for a in non_blind_actions if "raise" in a.lower())
    
    # No actions yet or only blinds
    if not non_blind_actions:
        return "Unopened"
    
    # Check for limps (calls without raises)
    if raise_count == 0:
        has_call = any("call" in a.lower() for a in non_blind_actions)
        if has_call:
            return "Limped"
        return "Unopened"
    
    # Facing open raise (first raise)
    if raise_count == 1:
        # Get the raise size from last raise action
        last_raise = next((a for a in reversed(non_blind_actions) if "raise" in a.lower()), None)
        if last_raise:
            size = get_raise_size_category(last_raise)
            return f"Open_{size}"
        return "Open_m"
    
    # Facing 3bet (second raise)
    elif raise_count == 2:
        last_raise = next((a for a in reversed(non_blind_actions) if "raise" in a.lower()), None)
        if last_raise:
            size = get_raise_size_category(last_raise)
            return f"3Bet_{size}"
        return "3Bet_s"
    
    # Facing 4bet (third raise)
    elif raise_count >= 3:
        last_raise = next((a for a in reversed(non_blind_actions) if "raise" in a.lower()), None)
        if last_raise:
            size = get_raise_size_category(last_raise)
            return f"4Bet_{size}"
        return "4Bet_s"
    
    return "Unopened"


def get_raise_size_category(action: str) -> str:
    """
    Categorize raise size as small (s), medium (m), or large (l).
    
    Heuristic:
    - Small: 2-2.5bb
    - Medium: 2.5-3.5bb
    - Large: 3.5bb+
    - Jam: if "jam" or all-in implied
    
    Args:
        action: Action string like "Seat5 raises 3bb"
    
    Returns:
        Size category: 's', 'm', 'l', or 'jam'
    """
    # Check for all-in indicators
    if "jam" in action.lower() or "all" in action.lower():
        return "jam"
    
    # Extract bb amount
    match = re.search(r'(\d+(?:\.\d+)?)bb', action)
    if match:
        bb = float(match.group(1))
        if bb < 2.5:
            return "s"
        elif bb < 3.5:
            return "m"
        else:
            return "l"
    
    # Default to medium
    return "m"


def get_pot_class(state: GameState) -> str:
    """
    Determine pot class based on number of raises.
    
    Pot classes:
    - SRP: Single raised pot (0-1 raises)
    - 3BP: 3bet pot (2 raises)
    - 4BP: 4bet pot (3+ raises)
    
    Args:
        state: Current game state
    
    Returns:
        Pot class: "SRP", "3BP", or "4BP"
    """
    actions = state.action_history
    
    # Count raises (excluding blinds and postflop)
    preflop_actions = []
    for action in actions:
        if "post" in action.lower():
            continue
        # Stop counting at flop/turn/river
        if any(street in action.lower() for street in ["flop", "turn", "river"]):
            break
        preflop_actions.append(action)
    
    raise_count = sum(1 for a in preflop_actions if "raise" in a.lower())
    
    if raise_count <= 1:
        return "SRP"
    elif raise_count == 2:
        return "3BP"
    else:
        return "4BP"


def get_stack_bucket(stack_bb: float) -> str:
    """
    Bucket effective stack size.
    
    Buckets:
    - 0-40bb: Short stack
    - 40-70bb: Mid stack
    - 70-120bb: Deep stack
    
    Args:
        stack_bb: Stack size in big blinds
    
    Returns:
        Stack bucket string
    """
    if stack_bb < 40:
        return "0-40bb"
    elif stack_bb < 70:
        return "40-70bb"
    else:
        return "70-120bb"


def get_postflop_role(state: GameState, pot_class: str) -> str:
    """
    Determine if hero is in-position (IP) or out-of-position (OOP).
    
    In heads-up:
    - SRP: Button/SB is IP, BB is OOP
    - 3BP/4BP: Depends on who 3bet/4bet last
    
    Args:
        state: Current game state
        pot_class: Pot class (SRP/3BP/4BP)
    
    Returns:
        "IP" or "OOP"
    """
    position = state.get_position()
    
    # In heads-up SRP, SB/Button is always IP
    if pot_class == "SRP":
        return "IP" if position == "SB" else "OOP"
    
    # For 3BP/4BP, need to check who was aggressor
    # For now, simplify: SB is IP
    return "IP" if position == "SB" else "OOP"


def get_postflop_line(state: GameState) -> str:
    """
    Determine what line hero is facing on this street.
    
    Lines:
    - vs_check: Opponent checked
    - vs_bet_s/p/jam: Facing a bet (small/pot/jam)
    - vs_raise_s/jam: Facing a raise
    
    Args:
        state: Current game state
    
    Returns:
        Line string
    """
    actions = state.action_history
    
    # Get actions on current street (after last community card deal)
    current_street_actions = []
    for action in reversed(actions):
        if any(indicator in action.lower() for indicator in ["flop", "turn", "river", "post"]):
            break
        current_street_actions.insert(0, action)
    
    if not current_street_actions:
        return "vs_check"
    
    # Check last opponent action
    last_action = current_street_actions[-1] if current_street_actions else ""
    
    if "check" in last_action.lower():
        return "vs_check"
    elif "bet" in last_action.lower():
        size = get_bet_size_category(last_action, state.pot)
        return f"vs_bet_{size}"
    elif "raise" in last_action.lower():
        size = get_raise_size_category(last_action)
        return f"vs_raise_{size}"
    
    return "vs_check"


def get_bet_size_category(action: str, pot: int) -> str:
    """
    Categorize bet size relative to pot.
    
    Categories:
    - s: Small (< 50% pot)
    - p: Pot-sized (50-120% pot)
    - jam: All-in or > 120% pot
    
    Args:
        action: Action string
        pot: Current pot size
    
    Returns:
        Size category
    """
    match = re.search(r'(\d+(?:\.\d+)?)bb', action)
    if match and pot > 0:
        bet_bb = float(match.group(1))
        pot_bb = pot / 2  # Pot is in chips, convert to bb
        
        if pot_bb == 0:
            return "p"
        
        ratio = bet_bb / pot_bb
        
        if ratio < 0.5:
            return "s"
        elif ratio < 1.2:
            return "p"
        else:
            return "jam"
    
    return "p"