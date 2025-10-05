"""Board texture classification for poker"""

from typing import List, Set


def classify_board(cards: List[str]) -> str:
    """
    Classify board texture into one of the predefined buckets.
    
    Buckets:
    - high_dry: A/K high, rainbow, unpaired, low connectivity
    - mid_dry: Q/J high, rainbow, unpaired, low connectivity
    - low_dry: T or lower high, rainbow, unpaired, low connectivity
    - paired: Board has a pair (but not dynamic)
    - monotone: 3 (flop) or 4 (turn/river) same suit (but not dynamic)
    - 2tone_connected: 2 suits, connected
    - dynamic: Multiple features present
    
    Args:
        cards: List of card strings like ["Kh", "7d", "2c"]
    
    Returns:
        Board bucket string
    """
    if not cards or len(cards) < 3:
        return "unknown"
    
    # Parse cards
    ranks = [_card_rank(c) for c in cards]
    suits = [c[-1] for c in cards]
    
    # Check all features
    is_paired = _is_paired(ranks)
    is_monotone = _is_monotone(suits)
    is_connected = _is_connected(ranks)
    is_two_tone = _is_two_tone(suits)
    
    # Count features (paired, monotone, connected count as features)
    feature_count = sum([is_paired, is_monotone, is_connected])
    
    # If multiple features present, it's dynamic
    if feature_count >= 2:
        return "dynamic"
    
    # Single feature boards
    if is_monotone:
        return "monotone"
    
    if is_paired:
        return "paired"
    
    # Connected boards
    if is_connected and is_two_tone:
        return "2tone_connected"
    
    if is_connected:
        return "dynamic"
    
    # Dry boards - categorize by high card
    high_rank = max(ranks)
    
    # Rainbow check (3+ different suits)
    if len(set(suits)) >= 3:
        if high_rank >= 13:  # A or K
            return "high_dry"
        elif high_rank >= 10:  # Q, J
            return "mid_dry"
        else:  # T or lower
            return "low_dry"
    
    # 2-tone but not connected
    if is_two_tone:
        return "2tone_connected"
    
    # Default to dynamic if unclear
    return "dynamic"


def _card_rank(card: str) -> int:
    """Convert card rank to numeric value (2=2, ..., T=10, J=11, Q=12, K=13, A=14)"""
    rank_char = card[0]
    rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, 
                '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
    return rank_map.get(rank_char, 0)


def _is_paired(ranks: List[int]) -> bool:
    """Check if board has a pair"""
    return len(ranks) != len(set(ranks))


def _is_monotone(suits: List[str]) -> bool:
    """Check if board is monotone (3+ cards of same suit)"""
    suit_counts = {}
    for suit in suits:
        suit_counts[suit] = suit_counts.get(suit, 0) + 1
    return any(count >= 3 for count in suit_counts.values())


def _is_two_tone(suits: List[str]) -> bool:
    """Check if board is 2-tone (exactly 2 suits represented with 2+ of each)"""
    suit_counts = {}
    for suit in suits:
        suit_counts[suit] = suit_counts.get(suit, 0) + 1
    
    # 2-tone means exactly 2 suits, each with 2+ cards
    suits_with_multiple = [s for s, count in suit_counts.items() if count >= 2]
    return len(suits_with_multiple) == 2


def _is_connected(ranks: List[int]) -> bool:
    """
    Check if board has connectivity (straight possibilities).
    
    Connected means cards that create meaningful straight draws:
    - All cards within 4 ranks of each other (e.g., 9-8-6-5)
    - Has actual sequential structure (not just two adjacent cards)
    """
    if len(ranks) < 3:
        return False
    
    # Get unique sorted ranks
    sorted_ranks = sorted(set(ranks))
    
    # Need at least 3 unique ranks for meaningful connectivity
    if len(sorted_ranks) < 3:
        return False
    
    # Check for wheel (A-2-3-4-5) - treat A as 1
    if 14 in sorted_ranks:
        wheel_ranks = [1 if r == 14 else r for r in sorted_ranks]
        wheel_ranks.sort()
        if _check_connectivity(wheel_ranks):
            return True
    
    return _check_connectivity(sorted_ranks)


def _check_connectivity(sorted_ranks: List[int]) -> bool:
    """
    Check if ranks form a connected structure.
    
    A board is connected if:
    - All cards are within a 4-rank window (straight possible)
    - AND at least 3 cards participate in the connectivity
    """
    if len(sorted_ranks) < 3:
        return False
    
    # Check if all cards are within 4-rank spread
    rank_spread = sorted_ranks[-1] - sorted_ranks[0]
    
    # If all cards within 4-rank window, it's connected
    # Examples: 9-8-7-6 (spread=3), 9-7-6-5 (spread=4), T-9-7-6 (spread=4)
    if rank_spread <= 4:
        return True
    
    # For 5-card boards, check if at least 4 cards are within 4-rank window
    if len(sorted_ranks) >= 4:
        # Check different 4-card windows
        for i in range(len(sorted_ranks) - 3):
            window_spread = sorted_ranks[i + 3] - sorted_ranks[i]
            if window_spread <= 4:
                return True
    
    return False