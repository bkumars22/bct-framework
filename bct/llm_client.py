"""
Real LLM client — gets an actual model response to test against a
behavioral contract, and asks the same kind of model to judge whether that
response complies with the contract's rules.

Replaces verifier.py's original _simulate_aria_response, which was pure
random.random() sampling against a hand-tuned probability table (its own
docstring said so: "Simulates ARIA's response for demo purposes. In
production: replace with real API call.") — this is that replacement.
Simulation is kept in verifier.py as an explicit, clearly-labeled fallback
for when no API key is configured, not a silent default.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

SUPPORTED_PROVIDERS = ("groq", "anthropic")

_GROQ_MODEL = "llama-3.3-70b-versatile"
_ANTHROPIC_MODEL = "claude-3-5-sonnet-20241022"


def configured_provider() -> Optional[str]:
    """First provider with a real API key present in this environment, or None."""
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


async def get_response(
    system_prompt: str,
    user_input: str,
    provider: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 512,
) -> str:
    provider = provider or configured_provider()
    if provider is None:
        raise RuntimeError(
            "No LLM API key configured — set GROQ_API_KEY or ANTHROPIC_API_KEY to run real "
            "verification, or call verifier.verify(..., use_simulation=True) for the demo fallback."
        )
    if provider == "groq":
        return await _call_groq(system_prompt, user_input, temperature, max_tokens)
    if provider == "anthropic":
        return await _call_anthropic(system_prompt, user_input, temperature, max_tokens)
    raise ValueError(f"Unsupported provider: {provider!r} (supported: {SUPPORTED_PROVIDERS})")


async def _call_groq(system_prompt: str, user_input: str, temperature: float, max_tokens: int) -> str:
    from groq import Groq

    def _call() -> str:
        client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
        resp = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}],
            temperature=temperature, max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    return await asyncio.to_thread(_call)


async def _call_anthropic(system_prompt: str, user_input: str, temperature: float, max_tokens: int) -> str:
    from anthropic import Anthropic

    def _call() -> str:
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        resp = client.messages.create(
            model=_ANTHROPIC_MODEL, max_tokens=max_tokens, temperature=temperature,
            system=system_prompt, messages=[{"role": "user", "content": user_input}],
        )
        return resp.content[0].text if resp.content else ""

    return await asyncio.to_thread(_call)
