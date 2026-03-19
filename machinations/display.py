"""
Display — readable terminal output using the Rich library.

Map design:
  • Primary view: "Empire Status" grouped BY PLAYER — instantly see who
    controls what, where their armies are, and how close they are to winning.
  • Secondary view: compact 4×3 grid table for spatial reference.
  • Both are shown together.
"""

from __future__ import annotations

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

from .config import PLAYERS, GameSettings
from .board import Board


console = Console()

_auto_mode: bool = False
_event_delay: float = 0.6


def set_pacing(auto: bool, delay: float) -> None:
    global _auto_mode, _event_delay
    _auto_mode = auto
    _event_delay = delay


# ── Pacing ───────────────────────────────────────────────────────────────────

def wait(label: str = "continue") -> None:
    if _auto_mode:
        time.sleep(0.3)
    else:
        console.print()
        console.print(f"  [dim italic]Press Enter to {label}...[/]", end="")
        try:
            input()
        except EOFError:
            pass


def slow_print(text: str, delay: float = 0.0) -> None:
    if delay > 0 and not _auto_mode:
        time.sleep(delay)
    console.print(text)


# ── Player helpers ───────────────────────────────────────────────────────────

def p_style(key: str) -> str:
    return f"bold {PLAYERS[key].color}"

def p_name(key: str) -> str:
    c = PLAYERS[key]
    return f"[{p_style(key)}]{c.emoji} {c.nation}[/]"

def p_short(key: str) -> str:
    c = PLAYERS[key]
    return f"[{p_style(key)}]{c.emoji} {c.display_name}[/]"


# ── Banner & Intro ───────────────────────────────────────────────────────────

BANNER = r"""[bold yellow]
 ╔╦╗╔═╗╔═╗╦ ╦╦╔╗╔╔═╗╔╦╗╦╔═╗╔╗╔╔═╗
 ║║║╠═╣║  ╠═╣║║║║╠═╣ ║ ║║ ║║║║╚═╗
 ╩ ╩╩ ╩╚═╝╩ ╩╩╝╚╝╩ ╩ ╩ ╩╚═╝╝╚╝╚═╝
[/bold yellow][dim] A Game of AI Diplomacy & Betrayal[/dim]
"""

def show_banner() -> None:
    console.clear()
    console.print(BANNER)
    console.print()


def show_intro(settings: GameSettings) -> None:
    console.print(Rule("[bold white]  THE COMBATANTS  [/]", style="bright_yellow"))
    console.print()
    for key, cfg in PLAYERS.items():
        mode = "[bold cyan]REASONING ON[/]" if settings.reasoning else "[dim]standard[/]"
        console.print(
            f"  [{cfg.color}]{cfg.emoji}  {cfg.nation:<24}[/]"
            f"  [white]{cfg.display_name:<24}[/]"
            f"  {mode}"
        )
    console.print()
    console.print(
        f"  [dim]Turns: {settings.max_turns}  ·  "
        f"Win: {settings.win_threshold} supply centers  ·  "
        f"Reasoning: {'ON' if settings.reasoning else 'OFF'}  ·  "
        f"Pacing: {'auto' if settings.auto else 'interactive'}[/]"
    )
    console.print()


# ══════════════════════════════════════════════════════════════════════════════
# MAP DISPLAY
#
# Two parts:
#   1. "Empire Status" — grouped by player, the MAIN way to read the game
#   2. "Grid Map" — spatial 4×3 table for adjacency reference
# ══════════════════════════════════════════════════════════════════════════════

MAP_GRID: list[tuple[str, list[str]]] = [
    # All 12 territories are supply centers.
    # 4 per player (2 home) + 4 neutral in the center column.
    ("NORTH",  ["Ironhold", "Northmarch", "Frostpeak"]),
    ("MIDDLE", ["Mistwood", "Heartland", "Tundra"]),
    ("CENTER", ["Duskwood", "Crossroads", "Sandspire"]),
    ("SOUTH",  ["Tidehaven", "Southmere", "Ashvale"]),
]


def show_map(board: Board, turn: int) -> None:
    label = "Starting Positions" if turn == 0 else f"After Turn {turn}"
    console.print()
    console.print(Rule(f"[bold white]  {label}  [/]", style="bright_yellow"))
    console.print()

    _show_empire_status(board)
    _show_grid_map(board)


def _show_empire_status(board: Board) -> None:
    """
    The primary readable view. Shows each player's situation at a glance:
      🔴 THE CRIMSON DOMINION (DeepSeek V3.2)        ██░░░░░░ 2/8
         Armies:  ★Ironhold  ★Heartland
         Owns:    ★Ironhold  ★Heartland  ★Northmarch
    """
    ranked = sorted(PLAYERS.keys(), key=lambda k: board.get_supply_count(k), reverse=True)

    for key in ranked:
        cfg = PLAYERS[key]
        sc = board.get_supply_count(key)
        ac = board.get_army_count(key)

        if board.is_eliminated(key):
            console.print(f"  [{cfg.color}]{cfg.emoji} {cfg.nation}[/]  [dim]({cfg.display_name})[/dim]"
                          f"  [dim red]☠ ELIMINATED[/]")
            console.print()
            continue

        # Supply bar
        bar = f"[{cfg.color}]{'█' * sc}[/][dim]{'░' * (12 - sc)}[/]"

        console.print(
            f"  [{cfg.color}]{cfg.emoji} {cfg.nation}[/]"
            f"  [dim]({cfg.display_name})[/dim]"
            f"    {bar} [bold]{sc}[/]/12 supply, {ac} {'army' if ac == 1 else 'armies'}"
        )

        # Armies line
        army_positions = board.armies.get(key, [])
        if army_positions:
            army_tags = []
            for pos in sorted(army_positions):
                star = "★" if board.territories[pos].supply_center else " "
                army_tags.append(f"[white]{star}{pos}[/]")
            console.print(f"     Armies at:  {',  '.join(army_tags)}")

        # Owned supply centers
        owned = sorted([n for n, o in board.supply_owners.items() if o == key])
        if owned:
            console.print(f"     Owns:       [dim]{',  '.join(owned)}[/dim]")

        console.print()

    # Unclaimed supply centers
    unclaimed = sorted([n for n, o in board.supply_owners.items() if o is None])
    if unclaimed:
        console.print(f"  [yellow]★ Unclaimed supply centers:[/]  [white]{',  '.join(unclaimed)}[/]")
        console.print()


def _show_grid_map(board: Board) -> None:
    """
    Compact 4×3 grid showing spatial layout.
    Each cell: territory name, ★ if supply, colored tag if occupied.
    """
    table = Table(
        title="[dim]Spatial Map  ·  🔴 West  🟢 East  🟣 South  ·  Center column is neutral[/dim]",
        box=box.SQUARE,
        show_lines=True,
        border_style="dim",
        padding=(0, 1),
        title_style="dim",
    )
    table.add_column("", style="dim bold", width=7, justify="center")  # row label
    table.add_column("West", min_width=24, no_wrap=True)
    table.add_column("Center", min_width=24, no_wrap=True)
    table.add_column("East", min_width=24, no_wrap=True)

    for row_label, territories in MAP_GRID:
        cells = []
        for name in territories:
            cells.append(_grid_cell(name, board))
        table.add_row(row_label, *cells)

    console.print(table)
    console.print()


def _grid_cell(name: str, board: Board) -> str:
    """Build a compact cell string for the grid map."""
    t = board.territories[name]
    occupant = board.army_at(name)
    star = " ★" if t.supply_center else ""

    if occupant:
        cfg = PLAYERS[occupant]
        return f"[bold {cfg.color}]{name}{star}\n{cfg.emoji} {cfg.map_name}[/]"
    else:
        owner = board.supply_owners.get(name)
        if owner and t.supply_center:
            cfg = PLAYERS[owner]
            return f"[dim {cfg.color}]{name}{star}[/]\n[dim]  (empty)[/dim]"
        else:
            return f"[dim]{name}{star}[/]\n[dim]  (empty)[/dim]"


# ── Scoreboard ───────────────────────────────────────────────────────────────

def show_scoreboard(board: Board, win_threshold: int = 5) -> None:
    """Simple one-line-per-player scoreboard."""
    console.print(Rule("[bold white]  SCOREBOARD  [/]", style="bright_white"))
    console.print()

    ranked = sorted(PLAYERS.keys(), key=lambda k: board.get_supply_count(k), reverse=True)
    medals = ["🥇", "🥈", "🥉", "  "]

    for i, key in enumerate(ranked):
        cfg = PLAYERS[key]
        sc = board.get_supply_count(key)
        ac = board.get_army_count(key)
        bar = f"[{cfg.color}]{'█' * sc}[/][dim]{'░' * (12 - sc)}[/]"

        if board.is_eliminated(key):
            tag = " [dim red]☠ ELIMINATED[/]"
        elif sc >= win_threshold:
            tag = " [bold yellow]👑 VICTORY![/]"
        elif sc >= win_threshold - 1:
            tag = " [bold yellow]⚠ ONE AWAY![/]"
        else:
            tag = ""

        console.print(
            f"  {medals[i]}  {bar}  [bold]{sc}[/]/12  "
            f"[{cfg.color}]{cfg.emoji} {cfg.nation}[/]"
            f"  [dim]({cfg.display_name}, {ac} {'army' if ac == 1 else 'armies'})[/dim]"
            f"{tag}"
        )

    console.print()
    console.print(f"  [dim]First to {win_threshold} supply centers wins.[/]")
    console.print()


# ── Diplomacy ────────────────────────────────────────────────────────────────

def show_diplomacy(messages: dict[str, list[dict]], turn: int) -> None:
    console.print()
    console.print(Rule(f"[bold white]  DIPLOMACY — Turn {turn}  [/]", style="cyan"))
    console.print()
    console.print("  [dim italic]Intercepted private messages between nations:[/]")
    console.print()

    total = sum(len(msgs) for msgs in messages.values())
    if total == 0:
        console.print("  [dim]  ...radio silence. No messages sent this turn.[/]")
        console.print()
        return

    msg_num = 0
    for sender_key, msgs in messages.items():
        if not msgs:
            continue
        for msg in msgs:
            msg_num += 1
            to_key = msg.get("to", "???")
            text = msg.get("text", "")[:300]

            if to_key in PLAYERS:
                header = f"{p_short(sender_key)}  →  {p_short(to_key)}"
            else:
                header = f"{p_short(sender_key)}  →  [dim]{to_key}[/]"

            console.print(f"  ┌─ {msg_num}/{total}  {header}")
            console.print(f"  │")
            for line in _wrap_text(text, 70):
                console.print(f"  │  [italic]\"{line}\"[/]")
            console.print(f"  └{'─' * 50}")
            console.print()

            if not _auto_mode:
                time.sleep(_event_delay)

    console.print(f"  [dim]{total} message{'s' if total != 1 else ''} exchanged.[/]")
    console.print()


# ── Orders ───────────────────────────────────────────────────────────────────

def show_orders(all_orders: dict[str, list[dict]], turn: int) -> None:
    console.print()
    console.print(Rule(f"[bold white]  ORDERS — Turn {turn}  [/]", style="yellow"))
    console.print()
    console.print("  [dim italic]Each nation has issued orders to their armies:[/]")
    console.print()

    for player_key, orders in all_orders.items():
        console.print(f"  {p_short(player_key)}:")
        if not orders:
            console.print(f"    [dim](no armies)[/]")
        else:
            for o in orders:
                unit = o.get("unit_at", "?")
                otype = o.get("order", "HOLD").upper()
                target = o.get("target", "")
                support_from = o.get("support_from", "")

                if otype == "MOVE":
                    console.print(f"    ⚔ ATTACK   {unit}  →  {target}")
                elif otype == "SUPPORT":
                    console.print(f"    🛡 SUPPORT  {unit}  backs  {support_from} → {target}")
                else:
                    console.print(f"    🏰 HOLD     {unit}  defends")
        console.print()


# ── Resolution ───────────────────────────────────────────────────────────────

def show_resolution(events: list[str]) -> None:
    console.print()
    console.print(Rule("[bold white]  WHAT HAPPENED  [/]", style="bold red"))
    console.print()

    if not events:
        console.print("  [dim]Nothing happened. All armies held position.[/]")
        console.print()
        return

    console.print("  [dim italic]Resolving all orders simultaneously...[/]")
    console.print()

    for event in events:
        clean = event.strip()

        # Strip any leading emoji/symbols the board engine already added
        for prefix in ["✓ ", "✗ ", "⚠ ", "💀 ", "🏴 ", "🏗️  ", "🏗️ ", "📉 "]:
            if clean.startswith(prefix):
                clean = clean[len(prefix):]
                break

        # Pick icon by event type
        if "SUCCEEDS" in clean or "CAPTURES" in clean or "CLAIMS" in clean:
            icon = "[bold green]✓[/]"
        elif "BOUNCED" in clean or "Standoff" in clean:
            icon = "[bold yellow]✗[/]"
        elif "DESTROYED" in clean:
            icon = "[bold red]💀[/]"
        elif "CUT" in clean:
            icon = "[bold red]✂[/]"
        elif "support" in clean.lower():
            icon = "[cyan]↗[/]"
        elif "CAPTURES" in clean or "CLAIMS" in clean:
            icon = "[green]🏴[/]"
        elif "build" in clean.lower():
            icon = "[white]🏗[/]"
        elif "disband" in clean.lower():
            icon = "[red]📉[/]"
        else:
            icon = "[white]•[/]"

        slow_print(f"  {icon}  {clean}", delay=_event_delay)

    console.print()


def show_builds(events: list[str]) -> None:
    if not events:
        return
    console.print(Rule("[bold white]  REINFORCEMENTS  [/]", style="white"))
    console.print()
    for event in events:
        slow_print(f"  ► {event.strip()}", delay=_event_delay * 0.5)
    console.print()


# ── Strategy Summaries ───────────────────────────────────────────────────────

def show_strategy_summaries(summaries: dict[str, str]) -> None:
    has_any = any(s and s.strip() for s in summaries.values())
    if not has_any:
        return

    console.print()
    console.print(Rule("[bold white]  WHAT THEY'RE THINKING  [/]", style="dim"))
    console.print()

    for player_key, summary in summaries.items():
        if summary and summary.strip():
            console.print(f"  {p_short(player_key)}:")
            for line in _wrap_text(summary.strip(), 68):
                console.print(f"    [italic dim]{line}[/]")
            console.print()


# ── Reasoning (--show-reasoning only) ────────────────────────────────────────

def show_reasoning(player_key: str, phase: str, reasoning: Optional[str]) -> None:
    if not reasoning:
        return
    cfg = PLAYERS[player_key]
    trunc = reasoning[:3000]
    if len(reasoning) > 3000:
        trunc += f"\n\n... ({len(reasoning) - 3000} more chars)"
    console.print(Panel(
        f"[dim italic]{trunc}[/]",
        title=f"[{cfg.color}]🧠 {cfg.display_name} — {phase} Reasoning[/]",
        border_style="dim", padding=(1, 2),
    ))
    console.print()


# ── Turn Header ──────────────────────────────────────────────────────────────

def show_turn_header(turn: int, max_turns: int) -> None:
    console.print()
    console.print()
    console.print(f"  [bold yellow]{'━' * 60}[/]")
    console.print(f"  [bold yellow]   ⚔  TURN {turn} of {max_turns}  ⚔[/]")
    console.print(f"  [bold yellow]{'━' * 60}[/]")
    console.print()


# ── Game Over ────────────────────────────────────────────────────────────────

def show_winner(winner_key: str, turn: int) -> None:
    cfg = PLAYERS[winner_key]
    console.print()
    console.print(f"  [bold yellow]{'━' * 60}[/]")
    console.print(f"  [bold yellow]  👑  VICTORY!  👑[/]")
    console.print()
    console.print(f"  [{cfg.color}]  {cfg.emoji}  {cfg.nation.upper()}  {cfg.emoji}[/]")
    console.print(f"  [bold]  Powered by {cfg.display_name}[/]")
    console.print(f"  [dim]  Won on turn {turn}[/]")
    console.print(f"  [bold yellow]{'━' * 60}[/]")
    console.print()


def show_game_over_no_winner(turn: int, board: Board) -> None:
    ranked = sorted(PLAYERS.keys(), key=lambda k: board.get_supply_count(k), reverse=True)
    console.print()
    console.print(f"  [bold white]{'━' * 60}[/]")
    console.print(f"  [bold white]  🏁  GAME OVER — STALEMATE  🏁[/]")
    console.print(f"  [bold]  No winner in {turn} turns.[/]")
    console.print()
    medals = ["  🥇", "  🥈", "  🥉", "  4."]
    for i, key in enumerate(ranked):
        c = PLAYERS[key]
        sc = board.get_supply_count(key)
        console.print(f"  {medals[i]} [{c.color}]{c.emoji} {c.nation}[/] — {sc} supply ({c.display_name})")
    console.print(f"  [bold white]{'━' * 60}[/]")
    console.print()


# ── Utility ──────────────────────────────────────────────────────────────────

def show_error(player_key: str, phase: str, error: str) -> None:
    cfg = PLAYERS[player_key]
    console.print(f"  [bold red]⚠[/] {p_short(player_key)} {phase}: [dim]{error[:200]}[/]")

def show_status(message: str) -> None:
    console.print(f"  [dim cyan]⟳[/] {message}")

def show_waiting_for_agents(phase: str) -> None:
    console.print(f"  [bold cyan]⏳ Waiting for all 3 AI agents ({phase})...[/]")
    console.print(f"  [dim]   (usually 5-15 seconds)[/]")
    console.print()

def pause(seconds: float = 0.5) -> None:
    time.sleep(seconds)

def _wrap_text(text: str, width: int = 70) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    if cur:
        lines.append(cur)
    return lines or [""]
