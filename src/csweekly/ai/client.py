# SPDX-License-Identifier: Apache-2.0
"""Optional OpenAI-compatible chat client (no hard dependency)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def ai_enabled() -> bool:
    return bool(os.environ.get("CSWEEKLY_AI_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def ai_config() -> dict[str, str]:
    return {
        "api_key": os.environ.get("CSWEEKLY_AI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or "",
        "base_url": (
            os.environ.get("CSWEEKLY_AI_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/"),
        "model": os.environ.get("CSWEEKLY_AI_MODEL") or "gpt-4.1-mini",
    }


def chat_json(system: str, user: str, *, temperature: float = 0.2) -> dict[str, Any] | None:
    """Call chat completions expecting a JSON object. Returns None if disabled/failed."""
    if not ai_enabled():
        return None
    cfg = ai_config()
    payload = {
        "model": cfg["model"],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        f"{cfg['base_url']}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, json.JSONDecodeError):
        return None
