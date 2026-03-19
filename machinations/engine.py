"""
Engine — the main game loop with proper pacing.

Orchestrates the turn cycle:
  1. Show map & scoreboard → wait
  2. Diplomacy phase (parallel API calls) → wait
  3. Orders phase (parallel API calls) → wait
  4. Resolution (one event at a time) → wait
  5. Build/disband
  6. Victory check

Uses ThreadPoolExecutor for parallel LLM calls within each phase.
Interactive by default (press Enter to advance). Use --auto for fast mode.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .config import PLAYERS, GameSettings
from .board import Board, Order, OrderType
from .agents import Agent, AgentResponse, extract_json
from .prompts import build_system_prompt, build_diplomacy_prompt, build_orders_prompt
from . import display


class GameEngine:
    """
    The core game engine. Manages state, agents, and the turn loop.
    """

    def __init__(self, settings: GameSettings) -> None:
        self.settings = settings
        self.board = Board()
        self.agents: dict[str, Agent] = {}
        self.turn = 0
        self.game_log: list[str] = []
        self.message_history: list[dict] = []

        # Per-player mailboxes (messages received this turn)
        self.inbox: dict[str, list[dict]] = {k: [] for k in PLAYERS}

    def setup(self) -> None:
        """Initialize agents for all three players."""
        # Configure display pacing
        display.set_pacing(
            auto=self.settings.auto,
            delay=self.settings.turn_delay,
        )

        display.show_banner()
        display.show_intro(self.settings)

        display.console.print()
        display.show_status("Initializing AI agents...")
        display.console.print()

        for key, cfg in PLAYERS.items():
            try:
                self.agents[key] = Agent(cfg, reasoning=self.settings.reasoning)
                display.show_status(f"  ✓ {cfg.display_name} connected")
            except EnvironmentError as e:
                display.console.print(f"  [bold red]✗ {cfg.display_name}: {e}[/]")
                raise SystemExit(1)

        display.console.print()
        display.console.print("  [bold green]All agents ready![/]")
        display.console.print()

        # Show the starting map
        display.show_map(self.board, 0)
        display.show_scoreboard(self.board, self.settings.win_threshold)

        display.wait("start the game")

    def run(self) -> Optional[str]:
        """Run the full game. Returns winning player key, or None."""
        self.setup()

        for turn in range(1, self.settings.max_turns + 1):
            self.turn = turn

            # ── Turn Header ──────────────────────────────────────────
            display.show_turn_header(turn, self.settings.max_turns)

            # ── Phase 1: Diplomacy ───────────────────────────────────
            display.show_waiting_for_agents("diplomacy")
            messages = self._diplomacy_phase()
            display.show_diplomacy(messages, turn)

            display.wait("see the military orders")

            # ── Phase 2: Orders ──────────────────────────────────────
            display.show_waiting_for_agents("military orders")
            all_orders, strategies = self._orders_phase()
            display.show_orders(all_orders, turn)
            display.show_strategy_summaries(strategies)

            display.wait("resolve the orders")

            # ── Phase 3: Resolution ──────────────────────────────────
            parsed_orders = self._parse_orders(all_orders)
            events = self.board.resolve_orders(parsed_orders)
            display.show_resolution(events)
            self.game_log.extend(events)

            # ── Phase 4: Build/Disband ───────────────────────────────
            build_events = self.board.do_builds()
            display.show_builds(build_events)
            self.game_log.extend(build_events)

            # ── Show updated state ───────────────────────────────────
            display.show_map(self.board, turn)
            display.show_scoreboard(self.board, self.settings.win_threshold)

            # ── Victory check ────────────────────────────────────────
            winner = self.board.check_winner(self.settings.win_threshold)
            if winner:
                display.show_winner(winner, turn)
                return winner

            # Check for stalemate (all but one eliminated)
            active = [k for k in PLAYERS if not self.board.is_eliminated(k)]
            if len(active) <= 1:
                display.show_winner(active[0], turn)
                return active[0]

            if turn < self.settings.max_turns:
                display.wait("proceed to next turn")

        # No winner after max turns
        display.show_game_over_no_winner(self.settings.max_turns, self.board)
        return None

    # ── Diplomacy Phase ──────────────────────────────────────────────────

    def _diplomacy_phase(self) -> dict[str, list[dict]]:
        """Each agent sends private messages. Returns {sender: [msgs]}."""
        # Clear inboxes
        self.inbox = {k: [] for k in PLAYERS}
        board_state = self.board.get_state_summary()
        results: dict[str, list[dict]] = {}

        def make_inbox_text(player_key: str) -> str:
            msgs = self.inbox.get(player_key, [])
            if not msgs:
                return ""
            return "\n".join(f"  From {m['from']}: \"{m['text']}\"" for m in msgs)

        def query_agent(player_key: str) -> tuple[str, list[dict], Optional[str]]:
            if self.board.is_eliminated(player_key):
                return player_key, [], None

            cfg = PLAYERS[player_key]
            other_players = [k for k in PLAYERS if k != player_key and not self.board.is_eliminated(k)]

            system_prompt = build_system_prompt(
                player_key, cfg.nation, cfg.emoji,
                self.settings.win_threshold, self.settings.max_turns,
            )
            user_prompt = build_diplomacy_prompt(
                self.turn, board_state, make_inbox_text(player_key),
                other_players, self.settings.max_message_length,
            )

            response = self.agents[player_key].query(system_prompt, user_prompt)

            if self.settings.show_reasoning and response.reasoning:
                display.show_reasoning(player_key, "Diplomacy", response.reasoning)

            parsed = extract_json(response.content)
            messages = []
            if parsed and "messages" in parsed:
                for msg in parsed["messages"]:
                    to = msg.get("to", "")
                    text = msg.get("text", "")[:self.settings.max_message_length]
                    if to in PLAYERS and to != player_key:
                        messages.append({"to": to, "text": text})

            return player_key, messages, response.reasoning

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(query_agent, k): k for k in PLAYERS}
            for future in as_completed(futures):
                try:
                    player_key, messages, reasoning = future.result()
                    results[player_key] = messages
                    for msg in messages:
                        self.inbox[msg["to"]].append({
                            "from": player_key,
                            "text": msg["text"],
                        })
                    self.message_history.extend([
                        {"turn": self.turn, "from": player_key, **msg} for msg in messages
                    ])
                except Exception as e:
                    pk = futures[future]
                    display.show_error(pk, "diplomacy", str(e))
                    results[pk] = []

        return results

    # ── Orders Phase ─────────────────────────────────────────────────────

    def _orders_phase(self) -> tuple[dict[str, list[dict]], dict[str, str]]:
        """Each agent submits military orders. Returns (orders, strategies)."""
        board_state = self.board.get_state_summary()
        all_orders: dict[str, list[dict]] = {}
        strategies: dict[str, str] = {}

        def make_inbox_text(player_key: str) -> str:
            msgs = self.inbox.get(player_key, [])
            if not msgs:
                return ""
            return "\n".join(f"  From {m['from']}: \"{m['text']}\"" for m in msgs)

        def make_history_text() -> str:
            if not self.game_log:
                return ""
            return "\n".join(self.game_log[-20:])

        def query_agent(player_key: str) -> tuple[str, list[dict], str, Optional[str]]:
            if self.board.is_eliminated(player_key):
                return player_key, [], "", None

            cfg = PLAYERS[player_key]
            army_positions = self.board.armies.get(player_key, [])
            if not army_positions:
                return player_key, [], "", None

            system_prompt = build_system_prompt(
                player_key, cfg.nation, cfg.emoji,
                self.settings.win_threshold, self.settings.max_turns,
            )
            user_prompt = build_orders_prompt(
                self.turn, board_state, make_inbox_text(player_key),
                army_positions, make_history_text(),
            )

            response = self.agents[player_key].query(system_prompt, user_prompt)

            if self.settings.show_reasoning and response.reasoning:
                display.show_reasoning(player_key, "Orders", response.reasoning)

            parsed = extract_json(response.content)
            orders = []
            strategy = ""

            if parsed:
                orders = parsed.get("orders", [])
                strategy = parsed.get("reasoning_summary", "")
            else:
                display.show_error(player_key, "orders", "Could not parse JSON response")
                orders = [{"unit_at": pos, "order": "HOLD"} for pos in army_positions]

            return player_key, orders, strategy, response.reasoning

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(query_agent, k): k for k in PLAYERS}
            for future in as_completed(futures):
                try:
                    player_key, orders, strategy, reasoning = future.result()
                    all_orders[player_key] = orders
                    strategies[player_key] = strategy
                except Exception as e:
                    pk = futures[future]
                    display.show_error(pk, "orders", str(e))
                    positions = self.board.armies.get(pk, [])
                    all_orders[pk] = [{"unit_at": p, "order": "HOLD"} for p in positions]
                    strategies[pk] = ""

        return all_orders, strategies

    # ── Order Parsing ────────────────────────────────────────────────────

    def _parse_orders(self, all_orders: dict[str, list[dict]]) -> list[Order]:
        """Convert raw JSON orders into validated Order objects."""
        parsed: list[Order] = []

        for player_key, orders in all_orders.items():
            army_positions = set(self.board.armies.get(player_key, []))
            ordered_units = set()

            for o in orders:
                unit_at = o.get("unit_at", "")
                order_type_str = o.get("order", "HOLD").upper()
                target = o.get("target", "")
                support_from = o.get("support_from", "")

                unit_at = self._fuzzy_territory(unit_at)
                target = self._fuzzy_territory(target) if target else None
                support_from = self._fuzzy_territory(support_from) if support_from else None

                if unit_at not in army_positions or unit_at in ordered_units:
                    continue

                ordered_units.add(unit_at)

                try:
                    otype = OrderType(order_type_str)
                except ValueError:
                    otype = OrderType.HOLD

                parsed.append(Order(
                    player=player_key,
                    unit_at=unit_at,
                    order_type=otype,
                    target=target,
                    support_from=support_from,
                ))

            for pos in army_positions - ordered_units:
                parsed.append(Order(
                    player=player_key,
                    unit_at=pos,
                    order_type=OrderType.HOLD,
                ))

        return parsed

    def _fuzzy_territory(self, name: str) -> str:
        """Fuzzy-match territory names from LLM output."""
        if not name:
            return name

        territories = self.board.get_all_territory_names()
        if name in territories:
            return name

        lower_map = {t.lower(): t for t in territories}
        if name.lower() in lower_map:
            return lower_map[name.lower()]

        for t in territories:
            if t.lower().startswith(name.lower()[:4]):
                return t

        return name
