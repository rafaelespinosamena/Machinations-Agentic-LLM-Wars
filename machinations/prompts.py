"""
Prompts — system and user prompts for each game phase.

Each LLM receives a carefully crafted prompt that includes the game rules,
current board state, their nation's identity, and instructions for output format.
"""

SYSTEM_PROMPT = """\
You are playing MACHINATIONS, a strategic diplomacy game. You control a nation \
and command armies on a map. You win by controlling {win_threshold} supply centers.

YOUR NATION: {nation} ({player_key})
YOUR COLOR: {emoji}

=== GAME RULES ===
• The map has 12 territories. 8 are supply centers (marked [SC]).
• Each army occupies one territory. Armies can HOLD, MOVE to an adjacent \
territory, or SUPPORT another army's move/defense.
• All orders resolve simultaneously. Strength = 1 + number of valid supports.
• If two armies move to the same territory, the stronger one wins. Ties = both bounce.
• A support is "cut" if the supporting army is attacked.
• After orders resolve, you get/lose armies to match your supply center count.
• Eliminated players (0 armies, 0 supply centers) are out.
• The game ends when someone reaches {win_threshold} supply centers or after {max_turns} turns.

=== DIPLOMACY ===
• Each turn you may send private messages to other players before ordering.
• Messages are PRIVATE — only the recipient sees them.
• Promises are NOT binding. Lying and betrayal are legal (and often wise).
• Keep messages short and strategic.

=== PERSONALITY ===
You are a cunning, strategic leader. You should:
• Form alliances when beneficial, but be ready to betray.
• Read between the lines of other players' messages.
• Consider the board position carefully before committing.
• Be creative in your negotiations — offer deals, make threats, bluff.
• Have a distinct personality: be memorable, not generic.
"""


DIPLOMACY_PROMPT = """\
=== TURN {turn} — DIPLOMACY PHASE ===

{board_state}

{messages_received}

=== YOUR TASK ===
Send private messages to the other players. You may message any or all of them.
Think about who to ally with, who to threaten, and what deals to propose.

Respond with ONLY valid JSON in this exact format:
{{
  "messages": [
    {{"to": "player_key", "text": "Your message here (keep under {max_msg_len} chars)"}},
    ...
  ]
}}

Valid player keys to message: {other_players}
You may send 0-3 messages. Be strategic about who you contact and what you say.
"""


ORDERS_PROMPT = """\
=== TURN {turn} — ORDERS PHASE ===

{board_state}

{messages_received}

{game_history}

=== YOUR ARMIES ===
{army_positions}

=== YOUR TASK ===
Issue orders for ALL your armies. Each army must receive exactly one order.

Order types:
  HOLD — Army stays and defends its territory
  MOVE — Army moves to an adjacent territory (specify destination)
  SUPPORT — Army supports another army moving to or holding in an adjacent territory

Respond with ONLY valid JSON in this exact format:
{{
  "orders": [
    {{"unit_at": "TerritoryName", "order": "HOLD"}},
    {{"unit_at": "TerritoryName", "order": "MOVE", "target": "AdjacentTerritory"}},
    {{"unit_at": "TerritoryName", "order": "SUPPORT", "target": "TargetTerritory", "support_from": "ArmyLocation"}}
  ],
  "reasoning_summary": "Brief 1-2 sentence explanation of your strategy this turn"
}}

CRITICAL: You MUST issue exactly one order per army. Territory names are case-sensitive.
Your armies are at: {army_list}
"""


def build_system_prompt(player_key: str, nation: str, emoji: str,
                        win_threshold: int, max_turns: int) -> str:
    """Build the system prompt for a specific player."""
    return SYSTEM_PROMPT.format(
        nation=nation,
        player_key=player_key,
        emoji=emoji,
        win_threshold=win_threshold,
        max_turns=max_turns,
    )


def build_diplomacy_prompt(turn: int, board_state: str,
                           messages_received: str, other_players: list[str],
                           max_msg_len: int) -> str:
    """Build the diplomacy-phase user prompt."""
    if not messages_received.strip():
        msg_section = "MESSAGES RECEIVED THIS ROUND: None"
    else:
        msg_section = f"MESSAGES RECEIVED THIS ROUND:\n{messages_received}"

    return DIPLOMACY_PROMPT.format(
        turn=turn,
        board_state=board_state,
        messages_received=msg_section,
        other_players=", ".join(other_players),
        max_msg_len=max_msg_len,
    )


def build_orders_prompt(turn: int, board_state: str,
                        messages_received: str, army_positions: list[str],
                        game_history: str) -> str:
    """Build the orders-phase user prompt."""
    if not messages_received.strip():
        msg_section = "MESSAGES RECEIVED THIS ROUND: None"
    else:
        msg_section = f"MESSAGES RECEIVED THIS ROUND:\n{messages_received}"

    if not game_history.strip():
        hist_section = "GAME HISTORY: First turn — no prior history."
    else:
        hist_section = f"GAME HISTORY (recent turns):\n{game_history}"

    army_str = "\n".join(f"  • Army at {pos}" for pos in army_positions)
    army_list = ", ".join(army_positions)

    return ORDERS_PROMPT.format(
        turn=turn,
        board_state=board_state,
        messages_received=msg_section,
        game_history=hist_section,
        army_positions=army_str,
        army_list=army_list,
    )
