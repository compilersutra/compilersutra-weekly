#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exit 0 and print 'yes' if the publishable edition is already published."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import yaml

from csweekly.window import publish_saturday, publishable_window


def main() -> int:
    as_of_s = os.environ.get("AS_OF") or None
    as_of = date.fromisoformat(as_of_s) if as_of_s else None
    pub = publish_saturday(publishable_window(as_of=as_of))
    meta = Path("data/editions") / f"{pub.year}" / pub.isoformat() / "edition.yaml"
    if meta.is_file():
        status = yaml.safe_load(meta.read_text(encoding="utf-8")).get("status")
        print("yes" if status == "published" else "no")
    else:
        print("no")
    return 0


if __name__ == "__main__":
    sys.exit(main())
