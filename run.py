"""
CLI entry point for MACHINATIONS.

Usage:
    python run.py                              # Interactive game (press Enter between phases)
    python run.py --auto                       # Auto-advance, no pauses
    python run.py --reasoning                  # Enable thinking/reasoning for all models
    python run.py --reasoning --show-reasoning # Also display thinking tokens
    python run.py --turns 8                    # Shorter game (8 turns)
    python run.py --auto --delay 0.3           # Fast auto mode
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from machinations.config import GameSettings, PLAYERS
from machinations.engine import GameEngine
from machinations.display import console


def check_dependencies() -> None:
    """Verify all required packages are installed."""
    missing = []
    try:
        import rich
    except ImportError:
        missing.append("rich")
    try:
        import anthropic
    except ImportError:
        missing.append("anthropic")
    try:
        import openai
    except ImportError:
        missing.append("openai")
    try:
        import dotenv
    except ImportError:
        missing.append("python-dotenv")

    if missing:
        console.print(f"[bold red]Missing packages:[/] {', '.join(missing)}")
        console.print(f"[dim]Run: pip install {' '.join(missing)}[/dim]")
        sys.exit(1)


def check_api_keys() -> None:
    """Verify all required API keys are set."""
    missing = []
    for key, cfg in PLAYERS.items():
        if not os.environ.get(cfg.env_key):
            missing.append(f"  {cfg.env_key:25s} → {cfg.display_name}")

    if missing:
        console.print("[bold red]Missing API keys:[/]")
        for m in missing:
            console.print(f"  [red]✗[/] {m}")
        console.print()
        console.print("[dim]Set them in your environment or create a .env file:[/dim]")
        console.print("[dim]  cp .env.example .env[/dim]")
        console.print("[dim]  # Then fill in your keys[/dim]")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="machinations",
        description="🗡️  MACHINATIONS — A Game of AI Diplomacy & Betrayal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                          Interactive game (press Enter between phases)
  python run.py --auto                   Auto-advance, no waiting
  python run.py --reasoning              Enable thinking/reasoning mode
  python run.py --reasoning --show-reasoning
                                         See what the models are thinking
  python run.py --turns 6                Quick 6-turn game
  python run.py --auto --delay 0.2       Blitz mode
        """,
    )
    parser.add_argument(
        "--reasoning", action="store_true",
        help="Enable thinking/reasoning mode for all models (costs more tokens)",
    )
    parser.add_argument(
        "--show-reasoning", action="store_true",
        help="Display model reasoning/thinking in output (implies --reasoning)",
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Auto-advance without waiting for Enter between phases (old behavior)",
    )
    parser.add_argument(
        "--turns", type=int, default=12,
        help="Maximum number of turns (default: 12)",
    )
    parser.add_argument(
        "--win", type=int, default=5,
        help="Supply centers needed to win (default: 5, out of 12 total)",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show detailed API response info",
    )
    parser.add_argument(
        "--delay", type=float, default=0.6,
        help="Seconds between events during resolution (default: 0.6)",
    )
    return parser.parse_args()


def main() -> None:
    # Load .env file if present
    load_dotenv()

    args = parse_args()

    check_dependencies()
    check_api_keys()

    # --show-reasoning implies --reasoning
    if args.show_reasoning:
        args.reasoning = True

    settings = GameSettings(
        max_turns=args.turns,
        win_threshold=args.win,
        reasoning=args.reasoning,
        show_reasoning=args.show_reasoning,
        verbose=args.verbose,
        turn_delay=args.delay,
        auto=args.auto,
    )

    engine = GameEngine(settings)

    try:
        winner = engine.run()
        if winner:
            console.print(f"[bold]Game complete. Winner: {PLAYERS[winner].display_name}[/]")
        else:
            console.print("[bold]Game complete. No clear winner.[/]")
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Game interrupted by user.[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Fatal error:[/] {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
