# SPDX-License-Identifier: Apache-2.0
"""Trivial-commit / noise filters."""

from __future__ import annotations

import re

from csweekly.config import SourceConfig


def subject_ignored(subject: str, source: SourceConfig) -> bool:
    for pattern in source.ignore_subject_regexes:
        if re.search(pattern, subject):
            return True
    return False


def author_ignored(author: str, source: SourceConfig) -> bool:
    for pattern in source.ignore_author_regexes:
        if re.search(pattern, author):
            return True
    return False
