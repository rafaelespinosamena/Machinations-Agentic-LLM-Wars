"""
Board — the map, territories, armies, and order resolution engine.

The map is a 12-territory graph in a 4×3 grid (triangle layout).
Three player home regions plus contested neutral center column.
Resolution uses simplified Diplomacy rules:
  • All orders resolve simultaneously
  • Strength = 1 (base) + number of valid supports
  • Ties mean everyone bounces (no movement)
  • Dislodged units are destroyed
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Territory Definitions ────────────────────────────────────────────────────

TERRITORY_DATA: dict[str, dict] = {
    # name: {adjacent: [...], supply_center: bool, home_of: player_key|None}
    #
    # 3-player triangle layout on a 4×3 grid:
    #   DeepSeek controls the WEST column  (Ironhold, Mistwood, Duskwood)
    #   OpenAI   controls the EAST column  (Frostpeak, Tundra, Sandspire)
    #   Claude   controls the BOTTOM row   (Tidehaven, Southmere, Ashvale)
    #   NEUTRAL  center column             (Northmarch, Heartland, Crossroads)
    #
    # Each player: 3 home supply centers, 3 armies. Win at 5.
    # Total: 12 territories, all supply centers.
    #
    # --- WEST COLUMN (DeepSeek home) ---
    "Ironhold":   {"adj": ["Northmarch", "Mistwood", "Heartland"],                           "sc": True,  "home": "deepseek"},
    "Mistwood":   {"adj": ["Ironhold", "Heartland", "Crossroads", "Duskwood"],                "sc": True,  "home": "deepseek"},
    "Duskwood":   {"adj": ["Mistwood", "Crossroads", "Tidehaven"],                            "sc": True,  "home": "deepseek"},
    # --- EAST COLUMN (OpenAI home) ---
    "Frostpeak":  {"adj": ["Northmarch", "Tundra", "Heartland"],                             "sc": True,  "home": "openai"},
    "Tundra":     {"adj": ["Frostpeak", "Heartland", "Crossroads", "Sandspire"],              "sc": True,  "home": "openai"},
    "Sandspire":  {"adj": ["Tundra", "Crossroads", "Ashvale"],                                "sc": True,  "home": "openai"},
    # --- BOTTOM ROW (Claude home) ---
    "Tidehaven":  {"adj": ["Duskwood", "Southmere", "Crossroads"],                            "sc": True,  "home": "claude"},
    "Southmere":  {"adj": ["Crossroads", "Tidehaven", "Ashvale"],                             "sc": True,  "home": "claude"},
    "Ashvale":    {"adj": ["Sandspire", "Southmere", "Crossroads"],                           "sc": True,  "home": "claude"},
    # --- CENTER COLUMN (neutral — the contested middle ground) ---
    "Northmarch": {"adj": ["Ironhold", "Frostpeak", "Heartland"],                            "sc": True,  "home": None},
    "Heartland":  {"adj": ["Northmarch", "Ironhold", "Frostpeak", "Mistwood", "Tundra", "Crossroads"], "sc": True,  "home": None},
    "Crossroads": {"adj": ["Heartland", "Mistwood", "Tundra", "Duskwood", "Sandspire", "Southmere", "Tidehaven", "Ashvale"], "sc": True, "home": None},
}


class OrderType(Enum):
    HOLD = "HOLD"
    MOVE = "MOVE"
    SUPPORT = "SUPPORT"


@dataclass
class Order:
    """A single army order."""
    player: str          # player key
    unit_at: str         # territory where the ordering army is
    order_type: OrderType
    target: Optional[str] = None       # destination (MOVE) or territory being supported into (SUPPORT)
    support_from: Optional[str] = None # for SUPPORT: the army location being supported


@dataclass
class Army:
    """An army on the board."""
    player: str
    territory: str


@dataclass
class Territory:
    """A single territory on the map."""
    name: str
    adjacent: list[str]
    supply_center: bool
    home_of: Optional[str]  # player key or None


class Board:
    """
    The game board: tracks territories, armies, supply center ownership,
    and resolves a set of simultaneous orders each turn.
    """

    def __init__(self) -> None:
        # Build territory objects
        self.territories: dict[str, Territory] = {}
        for name, data in TERRITORY_DATA.items():
            self.territories[name] = Territory(
                name=name,
                adjacent=data["adj"],
                supply_center=data["sc"],
                home_of=data["home"],
            )

        # Armies: player_key -> list of territory names
        self.armies: dict[str, list[str]] = {
            "deepseek": ["Ironhold", "Mistwood", "Duskwood"],
            "claude":   ["Tidehaven", "Southmere", "Ashvale"],
            "openai":   ["Frostpeak", "Tundra", "Sandspire"],
        }

        # Supply center ownership: territory -> player_key
        self.supply_owners: dict[str, Optional[str]] = {}
        for name, data in TERRITORY_DATA.items():
            if data["sc"]:
                self.supply_owners[name] = data["home"]  # None if contested

    # ── Queries ──────────────────────────────────────────────────────────

    def get_supply_count(self, player: str) -> int:
        """How many supply centers does a player control?"""
        return sum(1 for owner in self.supply_owners.values() if owner == player)

    def get_army_count(self, player: str) -> int:
        """How many armies does a player have?"""
        return len(self.armies.get(player, []))

    def army_at(self, territory: str) -> Optional[str]:
        """Return the player key of the army at a territory, or None."""
        for player, positions in self.armies.items():
            if territory in positions:
                return player
        return None

    def is_adjacent(self, t1: str, t2: str) -> bool:
        """Are two territories adjacent?"""
        if t1 not in self.territories or t2 not in self.territories:
            return False
        return t2 in self.territories[t1].adjacent

    def get_all_territory_names(self) -> list[str]:
        return list(self.territories.keys())

    def get_supply_centers(self) -> list[str]:
        return [n for n, t in self.territories.items() if t.supply_center]

    def is_eliminated(self, player: str) -> bool:
        """A player is eliminated if they have zero armies AND zero supply centers."""
        return self.get_army_count(player) == 0 and self.get_supply_count(player) == 0

    def get_state_summary(self, perspective: Optional[str] = None) -> str:
        """
        Return a human-readable summary of the board state.
        If perspective is given, frame it from that player's point of view.
        """
        lines = []
        lines.append("=== CURRENT MAP STATE ===")
        lines.append("")

        for name in sorted(self.territories.keys()):
            t = self.territories[name]
            occupant = self.army_at(name)
            sc_tag = " [SUPPLY CENTER]" if t.supply_center else ""
            owner_tag = ""
            if t.supply_center and self.supply_owners.get(name):
                owner_tag = f" (owned by {self.supply_owners[name]})"
            army_tag = f" — Army: {occupant}" if occupant else " — Empty"
            adj_str = ", ".join(t.adjacent)
            lines.append(f"  {name}{sc_tag}{owner_tag}{army_tag}")
            lines.append(f"    Adjacent to: {adj_str}")

        lines.append("")
        lines.append("=== SUPPLY CENTER COUNTS ===")
        for player in ["deepseek", "claude", "openai"]:
            sc = self.get_supply_count(player)
            ac = self.get_army_count(player)
            lines.append(f"  {player}: {sc} supply centers, {ac} armies")

        return "\n".join(lines)

    # ── Order Resolution ─────────────────────────────────────────────────

    def resolve_orders(self, orders: list[Order]) -> list[str]:
        """
        Resolve a set of simultaneous orders. Returns a list of event
        descriptions (what happened) for the game log.

        Resolution algorithm (simplified Diplomacy):
        1. Validate all orders; invalid orders become HOLDs.
        2. Calculate attack strength for each MOVE (1 + supports).
        3. Calculate defense strength for each territory (1 if HOLD/SUPPORT + supports).
        4. A MOVE succeeds if attack strength > all competing strengths.
        5. Failed MOVEs bounce back (unit stays put).
        6. Dislodged defending units are destroyed.
        """
        events: list[str] = []
        validated = self._validate_orders(orders, events)

        # Separate moves from holds/supports
        moves: list[Order] = [o for o in validated if o.order_type == OrderType.MOVE]
        supports: list[Order] = [o for o in validated if o.order_type == OrderType.SUPPORT]
        holds: list[Order] = [o for o in validated if o.order_type == OrderType.HOLD]

        # Calculate support for each move
        move_strength: dict[str, int] = {}  # "unit_at->target" -> strength
        for m in moves:
            key = f"{m.unit_at}->{m.target}"
            strength = 1
            for s in supports:
                if s.target == m.target and s.support_from == m.unit_at:
                    # Check support isn't cut (attacker moving to support's location)
                    support_cut = any(
                        m2.target == s.unit_at and m2.player != s.player
                        for m2 in moves
                    )
                    if not support_cut:
                        strength += 1
                        events.append(f"  {s.player}'s army at {s.unit_at} supports {m.player}'s move {m.unit_at} → {m.target}")
                    else:
                        events.append(f"  {s.player}'s support at {s.unit_at} was CUT!")
            move_strength[key] = strength

        # Calculate defense strength for each territory being attacked
        defense_strength: dict[str, int] = {}
        for m in moves:
            target = m.target
            defender = self.army_at(target)
            if defender and defender != m.player:
                if target not in defense_strength:
                    d_str = 1
                    for s in supports:
                        if s.target == target and s.support_from == target:
                            support_cut = any(
                                m2.target == s.unit_at and m2.player != s.player
                                for m2 in moves
                            )
                            if not support_cut:
                                d_str += 1
                    defense_strength[target] = d_str

        # Resolve moves: check for conflicts at same target
        target_attempts: dict[str, list[Order]] = {}
        for m in moves:
            target_attempts.setdefault(m.target, []).append(m)

        successful_moves: set[str] = set()  # "unit_at->target"
        dislodged: set[str] = set()  # territories where units are dislodged

        for target, attackers in target_attempts.items():
            if len(attackers) == 1:
                m = attackers[0]
                key = f"{m.unit_at}->{m.target}"
                atk = move_strength[key]
                dfn = defense_strength.get(target, 0)

                # Check if the defender is also trying to move away
                defender = self.army_at(target)
                defender_moving = False
                if defender and defender != m.player:
                    defender_moving = any(
                        m2.unit_at == target and m2.order_type == OrderType.MOVE
                        for m2 in moves
                    )

                if defender and not defender_moving and atk <= dfn:
                    events.append(f"  ✗ {m.player}'s move {m.unit_at} → {target} BOUNCED (atk {atk} vs def {dfn})")
                else:
                    successful_moves.add(key)
                    if defender and defender != m.player and not defender_moving:
                        dislodged.add(target)
                        events.append(f"  ✓ {m.player}'s army {m.unit_at} → {target} SUCCEEDS, dislodging {defender}!")
                    elif defender and defender != m.player and defender_moving:
                        events.append(f"  ✓ {m.player}'s army {m.unit_at} → {target} SUCCEEDS (defender moved away)")
                    else:
                        events.append(f"  ✓ {m.player}'s army {m.unit_at} → {target} SUCCEEDS")
            else:
                # Multiple attacks on same target — highest wins, ties bounce
                best_strength = 0
                for m in attackers:
                    key = f"{m.unit_at}->{m.target}"
                    best_strength = max(best_strength, move_strength[key])

                winners = [m for m in attackers if move_strength[f"{m.unit_at}->{m.target}"] == best_strength]

                if len(winners) == 1:
                    m = winners[0]
                    key = f"{m.unit_at}->{m.target}"
                    dfn = defense_strength.get(target, 0)
                    if move_strength[key] > dfn:
                        successful_moves.add(key)
                        defender = self.army_at(target)
                        if defender and defender != m.player:
                            dislodged.add(target)
                        events.append(f"  ✓ {m.player}'s army wins contest for {target} (strength {best_strength})")
                    else:
                        events.append(f"  ✗ All moves to {target} BOUNCE (tied with defense)")
                    # Losers bounce
                    for m2 in attackers:
                        if m2 != winners[0]:
                            events.append(f"  ✗ {m2.player}'s move to {target} BOUNCED (outmatched)")
                else:
                    events.append(f"  ✗ Standoff at {target}! All {len(winners)} attackers bounce (tied at strength {best_strength})")

        # Apply results
        # 1. Remove dislodged units
        for territory in dislodged:
            defender = self.army_at(territory)
            if defender:
                self.armies[defender].remove(territory)
                events.append(f"  💀 {defender}'s army at {territory} was DESTROYED")

        # 2. Execute successful moves
        for key in successful_moves:
            src, dst = key.split("->")
            # Find which player has army at src
            for player, positions in self.armies.items():
                if src in positions:
                    positions.remove(src)
                    positions.append(dst)
                    break

        # 3. Update supply center ownership
        for sc_name in self.supply_owners:
            occupant = self.army_at(sc_name)
            if occupant:
                old_owner = self.supply_owners[sc_name]
                if old_owner != occupant:
                    self.supply_owners[sc_name] = occupant
                    if old_owner:
                        events.append(f"  🏴 {occupant} CAPTURES {sc_name} from {old_owner}!")
                    else:
                        events.append(f"  🏴 {occupant} CLAIMS {sc_name}!")

        return events

    def _validate_orders(self, orders: list[Order], events: list[str]) -> list[Order]:
        """Validate orders and convert invalid ones to HOLDs."""
        validated = []
        for o in orders:
            # Check the player actually has an army at that location
            if o.unit_at not in self.armies.get(o.player, []):
                events.append(f"  ⚠ Invalid order from {o.player}: no army at {o.unit_at} → converted to HOLD")
                continue  # Skip entirely, no army there

            if o.order_type == OrderType.MOVE:
                if not self.is_adjacent(o.unit_at, o.target):
                    events.append(f"  ⚠ {o.player}'s MOVE {o.unit_at}→{o.target} invalid (not adjacent) → HOLD")
                    validated.append(Order(o.player, o.unit_at, OrderType.HOLD))
                else:
                    validated.append(o)
            elif o.order_type == OrderType.SUPPORT:
                if not self.is_adjacent(o.unit_at, o.target):
                    events.append(f"  ⚠ {o.player}'s SUPPORT into {o.target} invalid (not adjacent) → HOLD")
                    validated.append(Order(o.player, o.unit_at, OrderType.HOLD))
                else:
                    validated.append(o)
            else:
                validated.append(o)
        return validated

    def do_builds(self) -> list[str]:
        """
        Build phase: players with more supply centers than armies get new
        armies (at unoccupied home supply centers). Players with fewer
        supply centers than armies must disband.
        """
        events = []
        for player in ["deepseek", "claude", "openai"]:
            sc = self.get_supply_count(player)
            ac = self.get_army_count(player)

            if sc > ac:
                # Build armies at unoccupied owned supply centers
                builds_needed = sc - ac
                for sc_name, owner in self.supply_owners.items():
                    if builds_needed <= 0:
                        break
                    if owner == player and self.army_at(sc_name) is None:
                        self.armies[player].append(sc_name)
                        builds_needed -= 1
                        events.append(f"  🏗️  {player} builds army at {sc_name}")

            elif ac > sc:
                # Disband excess armies (remove from farthest positions)
                disband_count = ac - sc
                positions = list(self.armies[player])
                # Disband units that are NOT on supply centers first
                non_sc = [p for p in positions if not self.territories[p].supply_center]
                on_sc = [p for p in positions if self.territories[p].supply_center]
                to_disband = (non_sc + on_sc)[:disband_count]
                for t in to_disband:
                    self.armies[player].remove(t)
                    events.append(f"  📉 {player} disbands army at {t}")

        return events

    def check_winner(self, threshold: int = 5) -> Optional[str]:
        """Return the winning player key, or None."""
        for player in ["deepseek", "claude", "openai"]:
            if self.get_supply_count(player) >= threshold:
                return player
        return None
