# SPDX-License-Identifier: Apache-2.0
"""Shared HTTP session — optional CSWEEKLY_GITHUB_TOKEN / GITHUB_TOKEN."""

from __future__ import annotations

import os
from typing import Any

import requests

UA = "compilersutra-weekly/0.1 (+https://github.com/aabhinavg1/compilersutra-weekly)"


def github_token() -> str | None:
    return os.environ.get("CSWEEKLY_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")


def session(*, github: bool = False) -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.headers["Accept"] = "application/json"
    if github:
        s.headers["Accept"] = "application/vnd.github+json"
        s.headers["X-GitHub-Api-Version"] = "2022-11-28"
        token = github_token()
        if token:
            s.headers["Authorization"] = f"Bearer {token}"
    return s


def get_json(url: str, *, github: bool = False, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    r = session(github=github).get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()
