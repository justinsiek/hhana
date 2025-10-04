hhana (Hand History Analysis & Node Aggregation)

##Summary

Build a poker bot that uses TexasSolver decision table as a baseline, taking into account exploit signals generated
through hand history exploits (more info in How Actions Are Determined section)

##How Actions Are Determined:

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
  - Hand Buckets
    - premium (AA/KK/QQ/AKs)
    - strong (JJ/TT/AQs/AKo/KQs)
    - mid_pair (99-66)
    - low_pair (55-22)
    - suited_broadway (AJs, ATs, KJs, KTs, QJs, QTs, JTs)
    - offsuit_broadway (KQo-KTo, QJo, QTo, JTo)
    - suited_connector (T9s-54s, A5s, A4s)
    - Axs (Axs not above)
    - Axo (Axo not above)
    - suited_misc
    - offsuit_misc
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
  - Hand Buckets:
    - nuts (high straight, nut/near nut flush, boat, quads)
    - set 
    - two_pair
    - over_pair
    - top_pair_strong (top pair with strong kicker)
    - top_pair_weak (top pair weak kicker)
    - middle_pair
    - under_pair
    - combo_draw (open ender/flush draw, maybe also draw + overcards)
    - strong_draw (open ender/flush draw)
    - weak_draw (gutshot / bdfd)
    - air
  - Static Rules:
    - Raise Caps: 1 raise round per street
    - Jam enabled if stack pot ratio is small enough


##Technical Implementation Roadmap:

Site Adapter:
- Site adapter to connect bot to Replay Poker
- Requirements:
  - Data Capture:
    - Detect turn start/end
    - Detect position
    - Detect opponent action (fold, check, call, bet, raise)
      - Detect bet/raise size
    - Detect stacks
    - Detect hole cards 
    - Detect board cards
    - Detect street
    - Detect pot size
    - Optional: to_call, min_raise amounts
  - Action Execution:
    - Execute actions recieved from bot 
      - Main difficulty here is with inputing custom raise sizes
        - Workaround: only use buttons, not slider
  - Shadow Mode
    - For QA
    - Reads state, builds node key, runs policy, picks action/size, but does NOT click
    - Logs everything
      - state
      - node key
      - sanity flags

TexasSolver HU Baseline Decision Table:
- Purpose: Generate GTO baseline strategies, then provide efficient lookup
- Pipeline: Configure → Solve → Aggregate → Store → Query
- Note: TexasSolver ONLY supports postflop solving (requires board cards)

Table Generation:
  
  - Preflop Strategy (Alternative Approach):
    - TexasSolver does NOT support preflop solving
    - Solution: Use pre-computed GTO preflop charts
    - Sources:
      - Published HU GTO charts (GTO Wizard, PokerStrategy, etc.)
      - Simple analytical solutions (preflop trees are smaller)
      - Rules-based ranges as fallback
    - Map published ranges to your 10 preflop hand buckets
    - Store in same format: /data/baseline_tables/PF|{position}|{facing}|{pot_class}|{stack_bucket}.json
  
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
  
  - Aggregation into Hand Buckets:
    - Preflop: Convert GTO charts → 10 hand buckets
      - premium (AA/KK/QQ/AKs)
      - strong (JJ/TT/AQs/AKo/KQs)
      - mid_pair (99-66)
      - low_pair (55-22)
      - suited_broadway (AJs/ATs/KJs/KTs/QJs/QTs/JTs)
      - offsuit_broadway (KQo-KTo/QJo/QTo/JTo)
      - suited_connector (T9s-54s/A5s/A4s)
      - Axs (remaining Axs)
      - Axo (remaining Axo)
      - suited_misc, offsuit_misc
      - Method: Take published GTO ranges, average by bucket, convert to action frequencies
    
    - Postflop: Map TexasSolver output (1326 combos) → 12 hand buckets
      - nuts, set, two_pair, over_pair, top_pair_strong, top_pair_weak, 
        middle_pair, under_pair, combo_draw, strong_draw, weak_draw, air
      - Method: 
        1. Load raw TexasSolver strategies for all boards in bucket
        2. Classify each combo by made hand + draw strength
        3. Average strategies within each bucket across all boards
      - Precedence: made hands > draws (e.g., two_pair+weak_draw → two_pair)
    
    - Store aggregated strategy: dict[hand_bucket][action] = probability
    - Save: /data/baseline_tables/<node_key>.json

Table Storage Format:
  - File Structure: /data/baseline_tables/<node_key>.json
  - Node Key Format:
    - Preflop: "PF|{position}|{facing}|{pot_class}|{stack_bucket}"
      - Example: "PF|SB|Open_m|SRP|40-70bb"
    - Postflop: "POST|{role}|{pot_class}|{street}|{line}|{board_bucket}|{stack_bucket}"
      - Example: "POST|IP|SRP|Flop|vs_check|high_dry|40-70bb"
  
  - JSON Schema:
    {
      "node_key": "<full node key string>",
      "metadata": {
        "abstraction_version": "1.0",
        "iterations": 1000,
        "exploitability_bb_per_100": 0.05
      },
      "hand_buckets": {
        "<bucket_name>": {
          "fold": 0.0,
          "check": 0.0,
          "call": 0.0,
          "limp": 0.0,          // preflop only
          "open_s": 0.0,        // preflop only
          "open_m": 0.0,        // preflop only
          "open_l": 0.0,        // preflop only
          "bet_s": 0.0,         // postflop only
          "bet_p": 0.0,         // postflop only
          "bet_jam": 0.0,
          "3bet_s": 0.0,        // preflop only
          "3bet_jam": 0.0,      // preflop only
          "4bet_s": 0.0,        // preflop only
          "4bet_jam": 0.0,      // preflop only
          "raise_s": 0.0,       // postflop only
          "raise_jam": 0.0,     // postflop only
          "jam": 0.0
        }
      }
    }
  - Note: Only legal actions for that node will have non-zero probabilities

Lookup API (Main Functions):
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
  
  - preflop_hand_bucket(hand) -> str
    - Purpose: Classify hand into preflop hand buckets
    - Input: 2-card hand (e.g., "AsKh" or Hand object)
    - Output: Bucket label from 10 buckets (premium, strong, mid_pair, suited_connector, etc.)
    - Logic: Rank-first classification, then check suit, then special cases
  
  - postflop_hand_bucket(hole, board, street) -> str 
    - Purpose: Classify hand into postflop hand buckets
    - Input: hole cards, board cards, current street
    - Output: Bucket label from 12 buckets (nuts, set, two_pair, air, etc.)
    - Precedence: Check made hands first (high to low), then draws, finally air
    - Note: "nuts" is context-dependent (best possible hand on this board_bucket)
  
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
      2. Classify hand into hand_bucket
      3. Load table for node_key
      4. Retrieve strategy for hand_bucket
      5. Filter illegal actions based on current state
      6. Renormalize probabilities to sum to 1
    - Output: Dictionary mapping legal actions to probabilities
    - Example: {"fold": 0.2, "call": 0.5, "raise_s": 0.3}


    