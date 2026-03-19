"""
Configuration — model definitions, player setup, and game parameters.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Model Provider Enum ──────────────────────────────────────────────────────

class Provider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


# ── Model Configuration ─────────────────────────────────────────────────────

@dataclass
class ModelConfig:
    """Configuration for a single LLM provider."""
    provider: Provider
    model_id: str                        # API model string (non-reasoning)
    model_id_reasoning: Optional[str]    # API model string (reasoning mode)
    display_name: str                    # Pretty name for terminal output
    map_name: str                        # Short name for map cards (max ~18 chars)
    env_key: str                         # Environment variable for API key
    color: str                           # Rich color tag
    emoji: str                           # Nation emoji
    nation: str                          # In-game nation name


# ── The Three Players ────────────────────────────────────────────────────────

PLAYERS: dict[str, ModelConfig] = {
    "deepseek": ModelConfig(
        provider=Provider.DEEPSEEK,
        model_id="deepseek-chat",
        model_id_reasoning="deepseek-reasoner",
        display_name="DeepSeek V3.2",
        map_name="DeepSeek V3.2",
        env_key="DEEPSEEK_API_KEY",
        color="red",
        emoji="🔴",
        nation="The Crimson Dominion",
    ),
    "claude": ModelConfig(
        provider=Provider.ANTHROPIC,
        model_id="claude-haiku-4-5-20251001",
        model_id_reasoning="claude-haiku-4-5-20251001",  # same model, thinking toggled
        display_name="Claude 4.5 Haiku",
        map_name="Claude 4.5 Haiku",
        env_key="ANTHROPIC_API_KEY",
        color="magenta",
        emoji="🟣",
        nation="The Violet Throne",
    ),
    "openai": ModelConfig(
        provider=Provider.OPENAI,
        model_id="o4-mini-2025-04-16",
        model_id_reasoning="o4-mini-2025-04-16",  # same model, reasoning_effort toggled
        display_name="OpenAI o4-mini",
        map_name="OpenAI o4-mini",
        env_key="OPENAI_API_KEY",
        color="green",
        emoji="🟢",
        nation="The Emerald League",
    ),
}


# ── Game Parameters ──────────────────────────────────────────────────────────

@dataclass
class GameSettings:
    """Tunable knobs for the game."""
    max_turns: int = 12              # Game ends after N turns
    win_threshold: int = 5           # Supply centers needed to win (12 total, 3 per player + 3 neutral)
    max_message_length: int = 300    # Characters per diplomatic message
    reasoning: bool = False          # Enable reasoning/thinking mode
    show_reasoning: bool = False     # Display reasoning tokens in output
    verbose: bool = False            # Show full API responses
    turn_delay: float = 1.0          # Seconds between display updates
    auto: bool = False               # Skip "Press Enter" pauses (fast mode)
