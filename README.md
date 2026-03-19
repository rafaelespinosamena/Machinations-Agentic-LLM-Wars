# 🗡️ MACHINATIONS

### A Game of AI Diplomacy & Betrayal

> *Pit three frontier LLMs against each other in a simplified Diplomacy-style strategy game. Watch them negotiate alliances, coordinate attacks, and inevitably stab each other in the back.*

```
 ╔╦╗╔═╗╔═╗╦ ╦╦╔╗╔╔═╗╔╦╗╦╔═╗╔╗╔╔═╗
 ║║║╠═╣║  ╠═╣║║║║╠═╣ ║ ║║ ║║║║╚═╗
 ╩ ╩╩ ╩╚═╝╩ ╩╩╝╚╝╩ ╩ ╩ ╩╚═╝╝╚╝╚═╝
```

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Status: Experimental](https://img.shields.io/badge/status-experimental-orange.svg)

---

## 🎮 What Is This?

MACHINATIONS is a fully automated strategy game where **three frontier LLMs** control rival nations on a shared map. Each turn, they:

1. **Negotiate** — send private diplomatic messages (alliances, threats, lies)
2. **Order** — move armies, hold positions, or support allies
3. **Resolve** — simultaneous order resolution (simplified Diplomacy rules)
4. **Build** — gain or lose armies based on supply center control

The game ends when one nation captures **5 of 12 supply centers**, or after 12 turns.

### 🤖 The Combatants

| Nation | Model | Provider |
|--------|-------|----------|
| 🔴 **The Crimson Dominion** | DeepSeek V3.2 | DeepSeek |
| 🟣 **The Violet Throne** | Claude 4.5 Haiku | Anthropic |
| 🟢 **The Emerald League** | OpenAI o4-mini | OpenAI |

Three players creates a perfect diplomacy dynamic: at any moment, two can gang up on one — but who betrays whom first?

### 🧠 Reasoning Mode

Run with `--reasoning` to enable each model's thinking/chain-of-thought mode:
- **DeepSeek**: `deepseek-reasoner` (thinking mode)
- **Claude**: Extended thinking (`budget_tokens: 4096`)
- **OpenAI**: `reasoning_effort: high`

Compare the results! Do models play better when they can "think out loud"?

---

## 🚀 Quick Start

### 1. Clone & install

```bash
git clone https://github.com/yourusername/machinations.git
cd machinations
pip install -r requirements.txt
```

### 2. Add your API keys

```bash
cp .env.example .env
# Edit .env with your keys from:
#   DeepSeek  → https://platform.deepseek.com/api_keys
#   Anthropic → https://console.anthropic.com/settings/keys
#   OpenAI    → https://platform.openai.com/api-keys
```

### 3. Run!

```bash
# Interactive game — press Enter between phases to follow along
python run.py

# Auto-advance mode (no pausing, runs straight through)
python run.py --auto

# With reasoning/thinking enabled
python run.py --reasoning

# See what the models are thinking
python run.py --reasoning --show-reasoning

# Quick 6-turn game
python run.py --turns 6

# All options
python run.py --help
```

---

## 🗺️ The Map

A 4×3 grid arranged as a triangle — each player owns one side, and the center column is contested neutral ground:

```
        🔴 WEST         NEUTRAL        🟢 EAST
NORTH:  Ironhold ★     Northmarch ★    Frostpeak ★
MIDDLE: Mistwood ★     Heartland ★     Tundra ★
CENTER: Duskwood ★     Crossroads ★    Sandspire ★

                     🟣 SOUTH
SOUTH:  Tidehaven ★   Southmere ★     Ashvale ★
```

**All 12 territories are supply centers (★).** First to **5** wins.

- **DeepSeek** (🔴) starts on the west column: Ironhold, Mistwood, Duskwood
- **OpenAI** (🟢) starts on the east column: Frostpeak, Tundra, Sandspire
- **Claude** (🟣) starts on the south row: Tidehaven, Southmere, Ashvale
- **3 neutral supply centers** in the center column: Northmarch, Heartland, Crossroads
- Crossroads is the strategic choke point — it connects to 8 territories

---

## ⚙️ CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--reasoning` | Enable thinking/reasoning for all models | Off |
| `--show-reasoning` | Display reasoning tokens in output (implies `--reasoning`) | Off |
| `--auto` | Auto-advance without pressing Enter between phases | Off (interactive) |
| `--turns N` | Maximum turns before stalemate | 12 |
| `--win N` | Supply centers needed to win (12 total on map) | 5 |
| `--delay N` | Seconds between individual events during resolution | 0.6 |
| `--verbose` | Debug mode with full error traces | Off |

> **By default the game is interactive** — it pauses between each phase
> (diplomacy, orders, resolution) and waits for you to press Enter.
> This makes it easy to read and follow what's happening.
> Use `--auto` if you want it to run hands-free.

---

## 📂 Project Structure

```
machinations/
├── run.py                    # CLI entry point
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Package metadata
├── .env.example              # API key template (3 keys needed)
├── README.md
├── LICENSE
└── machinations/
    ├── __init__.py            # Package info
    ├── __main__.py            # python -m machinations support
    ├── config.py              # Model configs, player definitions, settings
    ├── board.py               # Map, territories, armies, order resolution
    ├── prompts.py             # LLM prompt templates (diplomacy & orders)
    ├── agents.py              # Unified LLM API wrappers (3 providers)
    ├── display.py             # Rich terminal rendering
    └── engine.py              # Main game loop & orchestration
```

---

## 🎯 Game Rules (Simplified Diplomacy)

### Orders
- **HOLD** — Stay put and defend
- **MOVE** — Move to an adjacent territory
- **SUPPORT** — Boost another army's move or defense (+1 strength)

### Resolution
- All orders resolve **simultaneously**
- Attack strength = 1 + number of valid supports
- Defense strength = 1 + number of valid supports
- **Attacker must be strictly stronger** to succeed (ties bounce)
- A support is **cut** if the supporting unit is attacked
- Dislodged units are **destroyed**

### Build Phase
- After resolution, army count adjusts to match supply center count
- New armies build at unoccupied owned supply centers
- Excess armies are disbanded

---

## 💡 What to Watch For

- **The 2v1 problem** — with three players, two can always gang up on one. Who gets targeted?
- **The backstab** — alliances are temporary. Who breaks trust first?
- **Strategic depth** — do models with reasoning play meaningfully better?
- **Personality** — each model develops a distinct diplomatic style
- **The Crossroads battle** — it connects to 8 territories, so whoever holds it dominates
- **Negotiation tactics** — threats, flattery, conditional deals, outright lies

---

## 💰 Cost Estimate

A typical 12-turn game costs roughly **$0.05–$0.30** total across all three providers, depending on reasoning mode.

| Model | Non-Reasoning | With Reasoning |
|-------|---------------|----------------|
| DeepSeek V3.2 | ~$0.01 | ~$0.03 |
| Claude 4.5 Haiku | ~$0.03 | ~$0.06 |
| OpenAI o4-mini | ~$0.04 | ~$0.08 |

---

## 🔧 Extending

**Add a 4th model:** Edit `config.py` — add a new entry to `PLAYERS`, update the map in `board.py` to give them home territory, and implement the provider call in `agents.py` if needed. The engine auto-discovers players from `PLAYERS`.

**Change the map:** Edit `TERRITORY_DATA` in `board.py` — add territories, change adjacencies, adjust supply centers.

**Modify prompts:** Edit `prompts.py` — tweak personality, rules emphasis, or output format.

**Logging:** The `engine.py` maintains a `game_log` list and `message_history` — easy to dump to JSON for analysis.

---

## 📜 License

MIT — do whatever you want with it.

---

*Built with love and the quiet hope that the AIs don't learn too much about betrayal.*
