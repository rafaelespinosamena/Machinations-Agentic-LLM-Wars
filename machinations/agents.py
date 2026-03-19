"""
Agents — unified interface for calling three LLM providers.

Each agent wraps the provider's API and handles:
  • Reasoning/thinking mode toggle
  • JSON extraction from responses
  • Error handling and retries
  • Reasoning content capture (for --show-reasoning flag)

Supported providers:
  • Anthropic (Claude 4.5 Haiku)
  • OpenAI (o4-mini)
  • DeepSeek (V3.2 via OpenAI-compatible API)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from .config import ModelConfig, Provider


@dataclass
class AgentResponse:
    """Unified response from any LLM agent."""
    content: str                          # The main text response
    reasoning: Optional[str] = None       # Reasoning/thinking content (if available)
    raw_response: Optional[object] = None # Full API response for debugging
    latency_ms: int = 0                   # Response time in milliseconds
    input_tokens: int = 0
    output_tokens: int = 0


def extract_json(text: str) -> Optional[dict]:
    """
    Extract JSON from an LLM response. Handles responses that may include
    markdown code fences, extra text before/after, etc.
    """
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from code fences
    patterns = [
        r'```json\s*(.*?)\s*```',
        r'```\s*(.*?)\s*```',
        r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1) if '```' in pattern else match.group(0))
            except (json.JSONDecodeError, IndexError):
                continue

    return None


class Agent:
    """
    A unified LLM agent that wraps any of the four supported providers.
    Instantiate one per player; reuse across turns.
    """

    def __init__(self, config: ModelConfig, reasoning: bool = False) -> None:
        self.config = config
        self.reasoning = reasoning
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Lazily initialize the provider-specific client."""
        api_key = os.environ.get(self.config.env_key)
        if not api_key:
            raise EnvironmentError(
                f"Missing API key: set {self.config.env_key} in your environment or .env file"
            )

        if self.config.provider == Provider.ANTHROPIC:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)

        elif self.config.provider == Provider.OPENAI:
            import openai
            self._client = openai.OpenAI(api_key=api_key)

        elif self.config.provider == Provider.DEEPSEEK:
            import openai
            self._client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
            )

    def query(self, system_prompt: str, user_prompt: str,
              max_retries: int = 2) -> AgentResponse:
        """
        Send a query to the LLM and return a unified AgentResponse.
        Retries on transient errors.
        """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                start = time.time()
                response = self._dispatch(system_prompt, user_prompt)
                response.latency_ms = int((time.time() - start) * 1000)
                return response
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff

        # All retries failed — return an error response
        return AgentResponse(
            content=json.dumps({"error": f"API call failed after {max_retries + 1} attempts: {last_error}"}),
            reasoning=None,
        )

    def _dispatch(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        """Route to the correct provider-specific call."""
        if self.config.provider == Provider.ANTHROPIC:
            return self._call_anthropic(system_prompt, user_prompt)
        elif self.config.provider == Provider.OPENAI:
            return self._call_openai(system_prompt, user_prompt)
        elif self.config.provider == Provider.DEEPSEEK:
            return self._call_deepseek(system_prompt, user_prompt)
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")

    # ── Anthropic (Claude) ───────────────────────────────────────────────

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        kwargs = {
            "model": self.config.model_id,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if self.reasoning:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 4096}
            kwargs["max_tokens"] = 8192

        response = self._client.messages.create(**kwargs)

        content = ""
        reasoning = ""
        for block in response.content:
            if block.type == "thinking":
                reasoning += block.thinking
            elif block.type == "text":
                content += block.text

        return AgentResponse(
            content=content,
            reasoning=reasoning if reasoning else None,
            raw_response=response,
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
        )

    # ── OpenAI (o4-mini) ─────────────────────────────────────────────────

    def _call_openai(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        kwargs = {
            "model": self.config.model_id,
            "messages": [
                {"role": "developer", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        if self.reasoning:
            kwargs["reasoning_effort"] = "high"
        else:
            kwargs["reasoning_effort"] = "low"

        response = self._client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""
        reasoning = None

        # o4-mini returns reasoning in the reasoning_content field
        if hasattr(response.choices[0].message, "reasoning_content"):
            reasoning = response.choices[0].message.reasoning_content

        usage = response.usage
        return AgentResponse(
            content=content,
            reasoning=reasoning,
            raw_response=response,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )

    # ── DeepSeek (V3.2 via OpenAI-compatible API) ────────────────────────

    def _call_deepseek(self, system_prompt: str, user_prompt: str) -> AgentResponse:
        model = self.config.model_id_reasoning if self.reasoning else self.config.model_id

        kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        response = self._client.chat.completions.create(**kwargs)

        content = response.choices[0].message.content or ""
        reasoning = None

        # DeepSeek reasoner returns reasoning_content
        msg = response.choices[0].message
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            reasoning = msg.reasoning_content

        usage = response.usage
        return AgentResponse(
            content=content,
            reasoning=reasoning,
            raw_response=response,
            input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        )
