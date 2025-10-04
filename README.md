# hhana (Hand History Analysis & Node Aggregation)

## Summary

Build a poker bot that uses TexasSolver decision table as a baseline, taking into account exploit signals generated
through hand history exploits (more info in How Actions Are Determined section)

## How Actions Are Determined:

baseline decision table mix = π0(a|node,hand)
E(a) = exploit signal
Compute adjusted policy with a softmax over utility boosts:
π(a) ∝ π0(a) · exp(clamp(E(a)/λ, −C, C))
λ (bb) controls aggressiveness; C caps deviation (e.g., C=1).

This calculation avoids overcommitting to a single action if it is an exploit, tunable with λ


## Poker Abstraction (What the solver sees)
Preflop:
  - Position (SB / BB)
  - Facing State (Unopened, Limped, Open[s/m/l], 3Bet[s/jam], 4bet[s/jam])
    - for 3bet, maybe cut down buckets? these buckets explode tree
  - Pot Class (SRP/3BP/4BP)
  - Effective Stack Size Buckets (0-40bb, 40-70bb, 70-120bb)
  - Static Rules:
    - Raise Cap: preflop capped at 4bet, no 5bet except jam
  - Hand Storage:
    - Store exact combos (169 total) from GTO charts
    - No bucketing preflop - use direct combo frequencies
    - Examples: AA, KK, AKs, AKo, 72o, etc.
  - Note on HU Ranges:
    - HU ranges are significantly wider than 6-max/full-ring
    - SB opens 80-100% of hands depending on stack depth
    - BB defends 60-80%+ vs opens
    - Most combos are played frequently (even weak offsuit hands)
Postflop:
  - Position (IP / OOP)
  - Pot Class (SRP / 3BP / 4BP)
  - Street (Flop / Turn / River)
  - Line (vs_check / vs_bet[s/p/jam] / vs_raise[s/jam])
  - Board Buckets:
    - high_dry (a/k high rainbow, unpaired, low connectivity)
    - mid_dry (q/j high rainbow, unpaired, low connectivity)
    - low_dry (t or lower high, rainbow, unpaired, low connectivty)
    - paired
    - monotone (3 (flop) or 4 (turn) same suit)
    - 2tone_connected (2 suits, connected)
    - dynamic 
  - 2D Hand Buckets (24 buckets - Made Hand × Draw Strength):
    - Made Hand Strength (6 levels):
      0. air           - No pair, no made hand
      1. weak_pair     - Bottom pair, underpair to board
      2. medium_pair   - Middle pair, top pair weak kicker
      3. strong_pair   - Top pair good kicker, overpair
      4. two_pair      - Two pair, set
      5. strong_made   - Straight+, flush, boat, quads
    
    - Draw Strength (4 levels):
      0. no_draw       - No draw whatsoever
      1. weak_draw     - Gutshot, backdoor flush/straight
      2. strong_draw   - OESD or flush draw
      3. combo_draw    - Multiple draws (OESD+FD, pair+draw)
    
    - Results in (made, draw) tuples: (0,2), (2,1), (3,0), etc.
    - Total: 6 × 4 = 24 distinct strategy buckets
    
  - Why 2D Bucketing (Made + Draw)?
    - Problem with pure equity: 50% equity flush draw ≠ 50% equity top pair
      - Flush draw wants to check/call (realize equity cheaply, no showdown value now)
      - Top pair wants to bet (has showdown value, protect equity, deny draws)
    - Made hand strength determines showdown value and protection needs
    - Draw strength determines realizability and desire for cheap cards
    - 2D approach captures both dimensions of hand strength
    - Still generalizes well (24 buckets vs 1326 combos)
  - Static Rules:
    - Raise Caps: 1 raise round per street
    - Jam enabled if stack pot ratio is small enough


## Technical Implementation Roadmap:

  ### Phase 1: State Reading and Logging
  
  #### Checkpoint 1.1: Basic Adapter - Read and Print State
  Goal: Adapter can read game state from poker site and log it
  Deliverables:
  - Adapter connects to poker site (Replay Poker)
  - Detects when game state changes
  - On change, prints raw state to terminal
  ```
    === GAME STATE UPDATE ===
    Position: BB
    Stacks: Hero=50bb, Villain=48bb
    Pot: 1.5bb
    Street: preflop
    Board: -
    Hole Cards: Kh Qs
    Action History: ["SB post 0.5bb", "BB post 1bb"]
    To Act: Hero
    Legal Actions: [fold, call, raise]
  ```

### Phase 2: Context Classification

#### Checkpoint 2.1: Node Key Generation
Goal: Generate and log node keys at each decision point
Deliverables:
- Implement build_node_key(state) -> str
- Parse action history to determine facing state
- Bucket stacks
- Determine pot class
- On turn, log node key alongside state:
```
  === DECISION POINT ===
  Hand: KhQs
  Node Key: PF|BB|Open_m|SRP|40-70bb
  State: {...}
```

#### Checkpoint 2.2: Hand Classification
Goal: Classify hands into buckets/combos
Deliverables:
- Implement normalize_hand_to_combo(hand) -> str (preflop)
- Implement classify_made_hand(hand, board) -> int (postflop)
- Implement classify_draw(hand, board) -> int (postflop)
- Implement bucket_2d(hand, board) -> tuple (postflop)
- Implement classify_board(board) -> str (board bucketing)
- On turn, log hand classification, node key, state:
```
 === DECISION POINT ===
  Hand: KhQs
  Node Key: PF|BB|Open_m|SRP|40-70bb
  Hand Bucket: KQo
  State: {...}
  ---
  Hand: KhQs
  Board: As 7d 2h
  Node Key: POST|IP|SRP|Flop|vs_check|high_dry|40-70bb
  Made Hand: 0 (air)
  Draw: 1 (weak_draw - backdoor straight)
  Hand Bucket: (0, 1)
```

### Phase 3: Baseline Strategy

#### Checkpoint 3.1: Preflop GTO Chart Integration
Goal: Load real preflop GTO strategies
Deliverables:
- Source/create GTO preflop charts for HU
- Convert to your JSON format
- Store in data/baseline_tables/
- At every preflop situation, log baseline strategy:
```
  === DECISION POINT ===
    Hand: KQo
    Node Key: PF|BB|Open_m|SRP|40-70bb
    Hand Bucket: KQo
    Baseline Strategy: {"fold": 0.3, "call": 0.5, "3bet_s": 0.15, "3bet_jam": 0.05}
```

## Table Generation:
  
  Key Design Decisions:
  - Preflop: Store exact combo strategies (169 combos) from GTO charts (no solver, no bucketing)
  - Postflop: Use 2D buckets (6 made × 4 draw = 24 buckets) + TexasSolver CFR
  - Rationale:
    - Preflop: GTO charts give exact frequencies, storage is trivial (~350KB total), no reason to bucket
    - Postflop: 2D bucketing captures both showdown value AND draw potential while keeping storage manageable
  
  - Preflop Strategy (GTO Charts - No Solving):
    - TexasSolver does NOT support preflop solving
    - Solution: Use pre-computed GTO preflop charts directly
    - Sources:
      - Published HU GTO charts (GTO Wizard, PokerStrategy, Nash Equilibrium tables)
      - Simple analytical solutions (preflop trees are smaller)
      - Rules-based ranges as fallback
    - Store exact combo frequencies (all 169 combos)
    - No bucketing needed - charts already provide per-combo strategies
    - Storage: ~7KB per node × 50 nodes = ~350KB total (negligible)
    - Format: /data/baseline_tables/PF|{position}|{facing}|{pot_class}|{stack_bucket}.json
  
  - Postflop Solver Configuration (TexasSolver):
    - Use TexasSolver CFR engine (MCCFR or DiscountedCFR)
    - Iterations: target 1000-2000 iterations for convergence per spot
    - Bet Sizing Abstractions:
      - Postflop: check, bet[50%pot/100%pot/jam], raise[2.5x/jam]
    - Stack Size Buckets: Generate separate trees for each effective stack bucket
      - 0-40bb (short-stack), 41-70bb (mid-stack), 71+bb (deep-stack)
    - Pot Classes: SRP (single raised pot), 3BP (3bet pot), 4BP (4bet pot)
    - Static Rules Enforcement:
      - Preflop: capped at 4bet, no 5bet except jam
      - Postflop: 1 raise round per street max
      - Jam enabled when SPR < threshold
  
  - Postflop Game Tree Generation (TexasSolver):
    - Dimensions: Position × Pot Class × Street × Line × Board Bucket × Stack Bucket
    - Generate solver tree for each combination:
      Position: IP, OOP
      Pot Class: SRP, 3BP, 4BP
      Street: Flop, Turn, River
      Line: vs_check, vs_bet_s, vs_bet_p, vs_bet_jam, vs_raise_s, vs_raise_jam
      Board Bucket: high_dry, mid_dry, low_dry, paired, monotone, 2tone_connected, dynamic
      Stack Bucket: 0-40bb, 40-70bb, 70-120bb (SPR-based, not raw stacks)
    - Example Trees to Solve:
      - IP|SRP|Flop|vs_check|high_dry|40-70bb → solve with [check/bet_s/bet_p/bet_jam]
      - OOP|SRP|Flop|vs_bet_p|monotone|40-70bb → solve with [fold/call/raise_s/raise_jam]
      - IP|3BP|Turn|vs_raise_s|2tone_connected|0-40bb → solve with [fold/call/jam]
    - Total Postflop Trees: 2 positions × 3 pot classes × 3 streets × 6 lines × 7 board buckets × 3 SPR buckets
      = ~2268 trees (prune invalid combos like "can't raise on river if already raised")
    - Board Aggregation:
      - Sample 20-50 representative boards per board_bucket
      - Solve each, then average strategies across boards within bucket
  
  - Solving Process (Postflop Only):
    - For each postflop tree configuration:
      1. Build TexasSolver game tree with proper abstractions
      2. Run CFR for 1000-2000 iterations (monitor exploitability)
      3. Extract final strategy for 1326 hand combos
      4. Save raw strategy: /data/solver_outputs/<node_key>_raw.json
    - Parallelization: Solve independent spots in parallel (4-8 solves at once)
    - Expected time: ~2000 postflop spots × 20 boards × 30-60s = 15-30 hours (8 parallel)
  
  - Strategy Storage:
    - Preflop: Direct storage of exact combo frequencies (no aggregation)
      - Load GTO chart for each spot
      - Store all 169 combos with their exact action frequencies
      - Example from chart: "AA: Open 100% (70% large, 30% medium)"
      - Store as: "AA": {"fold": 0.0, "open_m": 0.3, "open_l": 0.7}
      - No bucketing, no averaging, no information loss
    
    - Postflop: Map TexasSolver output (1326 combos) → 24 2D buckets
      - Buckets: (made_hand: 0-5, draw: 0-3) = 24 total combinations
      - Method: 
        1. For each board in board_bucket (20-50 boards sampled):
           a. Load raw TexasSolver strategies (1326 combos × actions)
           b. Classify each combo into 2D bucket:
              - Evaluate made hand strength (0-5): air → strong_made
              - Evaluate draw strength (0-3): no_draw → combo_draw
              - Example: AhQh on Kc7d2h = (made=0 air, draw=2 strong_draw) = bucket (0,2)
              - Example: KhQs on Kc7d2h = (made=3 strong_pair, draw=0 no_draw) = bucket (3,0)
           c. Group combos by 2D bucket and average strategies within bucket
        2. Average 2D-bucketed strategies across all boards in board_bucket
      - Result: Each node gets 24 strategies (one per (made, draw) combination)
      - Advantage: Captures both showdown value AND draw potential
    
    - Store strategies: 
      - Preflop: dict[combo][action] = probability (169 combos, no aggregation)
      - Postflop: dict[(made, draw)][action] = probability (24 buckets, aggregated)
    - Save: /data/baseline_tables/<node_key>.json

## Table Storage Format:
  - File Structure: /data/baseline_tables/<node_key>.json
  - Node Key Format:
    - Preflop: "PF|{position}|{facing}|{pot_class}|{stack_bucket}"
      - Example: "PF|SB|Open_m|SRP|40-70bb"
    - Postflop: "POST|{role}|{pot_class}|{street}|{line}|{board_bucket}|{stack_bucket}"
      - Example: "POST|IP|SRP|Flop|vs_check|high_dry|40-70bb"
  
  - JSON Schema (Preflop):
    {
      "node_key": "PF|SB|Unopened|SRP|40-70bb",
      "metadata": {
        "abstraction_version": "1.0",
        "street": "preflop",
        "source": "GTO Wizard HU 100bb"
      },
      "combos": {
        "AA": {"fold": 0.0, "limp": 0.0, "open_s": 0.0, "open_m": 0.3, "open_l": 0.7},
        "KK": {"fold": 0.0, "limp": 0.0, "open_s": 0.0, "open_m": 0.4, "open_l": 0.6},
        "QQ": {"fold": 0.0, "limp": 0.0, "open_s": 0.0, "open_m": 0.5, "open_l": 0.5},
        "AKs": {"fold": 0.0, "limp": 0.0, "open_s": 0.1, "open_m": 0.6, "open_l": 0.3},
        "AKo": {"fold": 0.0, "limp": 0.0, "open_s": 0.2, "open_m": 0.7, "open_l": 0.1},
        "72o": {"fold": 0.85, "limp": 0.15, "open_s": 0.0, "open_m": 0.0, "open_l": 0.0},
        ... // All 169 combos
      }
    }
  
  - JSON Schema (Postflop):
    {
      "node_key": "POST|IP|SRP|Flop|vs_check|high_dry|40-70bb",
      "metadata": {
        "abstraction_version": "1.0",
        "iterations": 2000,
        "exploitability_bb_per_100": 0.05,
        "boards_solved": 20,
        "street": "postflop"
      },
      "hand_buckets": {
        "(0,0)": {"fold": 0.9, "check": 0.1, "bet_s": 0.0, "bet_p": 0.0},
        "(0,1)": {"fold": 0.5, "check": 0.4, "bet_s": 0.1, "bet_p": 0.0},
        "(0,2)": {"fold": 0.2, "check": 0.3, "bet_s": 0.4, "bet_p": 0.1},
        "(0,3)": {"fold": 0.1, "check": 0.2, "bet_s": 0.5, "bet_p": 0.2},
        "(1,0)": {"fold": 0.3, "check": 0.5, "bet_s": 0.2, "bet_p": 0.0},
        "(1,2)": {"fold": 0.1, "check": 0.3, "bet_s": 0.4, "bet_p": 0.2},
        "(2,0)": {"fold": 0.0, "check": 0.3, "bet_s": 0.5, "bet_p": 0.2},
        "(2,1)": {"fold": 0.0, "check": 0.2, "bet_s": 0.5, "bet_p": 0.3},
        "(3,0)": {"fold": 0.0, "check": 0.2, "bet_s": 0.3, "bet_p": 0.5},
        "(3,1)": {"fold": 0.0, "check": 0.1, "bet_s": 0.2, "bet_p": 0.7},
        "(4,0)": {"fold": 0.0, "check": 0.1, "bet_s": 0.1, "bet_p": 0.8},
        "(5,0)": {"fold": 0.0, "check": 0.05, "bet_s": 0.05, "bet_p": 0.9}
      }
    }
  - Note: Postflop bucket format is "(made_hand, draw)" where:
    - made_hand: 0=air, 1=weak_pair, 2=medium_pair, 3=strong_pair, 4=two_pair, 5=strong_made
    - draw: 0=no_draw, 1=weak_draw, 2=strong_draw, 3=combo_draw
  - Note: Only legal actions for that node will have non-zero probabilities
  - Note: Preflop stores exact combos (169), postflop uses 2D (made, draw) buckets (24)

## Lookup API (Main Functions):
  - node_key(state) -> str 
    - Purpose: Build node key from current game state to lookup baseline table
    - Input: game state dict with position, stacks, pot, street, action_history, board, etc.
    - Output: node_key string (dimensions vary by street)
      - Preflop: "PF|{position}|{facing}|{pot_class}|{stack_bucket}"
      - Postflop: "POST|{role}|{pot_class}|{street}|{line}|{board_bucket}|{stack_bucket}"
    - Logic:
      - Parse action history to determine facing state / line
      - Bucket effective stacks (preflop: raw bb, postflop: SPR)
      - Determine pot class from action history (SRP/3BP/4BP)
  
  - normalize_hand_to_combo(hand) -> str
    - Purpose: Convert specific hand to combo notation for preflop lookup
    - Input: 2-card hand (e.g., "AsKh", "7c2d")
    - Output: Combo string (e.g., "AKs", "72o", "77")
    - Logic:
      - If paired: return rank pair (e.g., "AA", "77")
      - If suited: return high-low + 's' (e.g., "AKs", "T9s")
      - If offsuit: return high-low + 'o' (e.g., "AKo", "72o")
  
  - classify_made_hand(hole, board) -> int
    - Purpose: Classify made hand strength (0-5)
    - Input: hole cards, board cards
    - Output: 0=air, 1=weak_pair, 2=medium_pair, 3=strong_pair, 4=two_pair, 5=strong_made
    - Logic:
      - Evaluate hand (using poker evaluator library)
      - Check position relative to board (top pair? middle pair? overpair?)
      - Consider kicker strength for pairs
  
  - classify_draw(hole, board) -> int
    - Purpose: Classify draw strength (0-3)
    - Input: hole cards, board cards
    - Output: 0=no_draw, 1=weak_draw, 2=strong_draw, 3=combo_draw
    - Logic:
      - Count flush outs (suited cards, backdoor possibilities)
      - Count straight outs (OESD, gutshot, backdoor)
      - Combine with made hand (pair+draw = combo?)
  
  - bucket_2d(hole, board) -> tuple[int, int]
    - Purpose: Get full 2D bucket for hand
    - Input: hole cards, board cards
    - Output: (made_hand, draw) tuple, e.g., (3, 0) for strong pair no draw
    - Simple wrapper: return (classify_made_hand(hole, board), classify_draw(hole, board))
  
  - board_bucket(board, street) -> str
    - Purpose: Classify board texture for postflop aggregation
    - Input: board cards, current street
    - Output: Board bucket (high_dry, mid_dry, low_dry, paired, monotone, 2tone_connected, dynamic)
    - Logic:
      - Check for paired first
      - Check for monotone (3+ same suit on flop, 4 on turn)
      - Check connectivity (straights possible)
      - Check high card (A/K = high, Q/J = mid, T or lower = low)
      - Default to dynamic if multiple features present
  
  - load_baseline_table(node_key) -> dict | None
    - Purpose: Load precomputed baseline table from disk
    - Input: node_key string
    - Output: Full strategy dict with hand_buckets, or None if not found
    - Caching: Keep frequently accessed tables in memory
  
  - query_policy(state, hand) -> dict[action, prob]
    - Purpose: Main query function - fetch baseline action distribution
    - Input: game state, player hand
    - Steps:
      1. Build node_key from state
      2. If preflop:
         - Normalize hand to combo: normalize_hand_to_combo("AsKh") → "AKs"
         - Load table for node_key
         - Direct lookup: strategy = table["combos"]["AKs"]
         - No bucketing, no classification needed
      3. If postflop:
         - Classify hand into 2D bucket: (made_hand, draw)
         - Example: bucket_2d("AhQh", "Kc7d2h") → (0, 2) for "air + strong draw"
         - Example: bucket_2d("KhQs", "Kc7d2h") → (3, 0) for "strong pair + no draw"
         - Load table for node_key
         - Retrieve strategy from table["hand_buckets"]["(made,draw)"]
      4. Filter illegal actions based on current state
      5. Renormalize probabilities to sum to 1
    - Output: Dictionary mapping legal actions to probabilities
    - Example: {"fold": 0.0, "check": 0.2, "bet_p": 0.8}


    