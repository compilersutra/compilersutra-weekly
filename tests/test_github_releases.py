# SPDX-License-Identifier: Apache-2.0
from datetime import date
from unittest.mock import patch

from csweekly.collectors.github_releases import collect_github_releases
from csweekly.config import SourceConfig
from csweekly.window import friday_friday_window


def test_github_releases_window():
    window = friday_friday_window(as_of=date(2026, 11, 5))
    payload = [
        {
            "tag_name": "llvmorg-21.1.0",
            "name": "LLVM 21.1.0",
            "html_url": "https://github.com/llvm/llvm-project/releases/tag/llvmorg-21.1.0",
            "published_at": "2026-11-02T10:00:00Z",
            "body": "First line of notes\nMore",
            "draft": False,
            "prerelease": False,
        },
        {
            "tag_name": "old",
            "name": "old",
            "html_url": "https://example.com/old",
            "published_at": "2026-01-01T00:00:00Z",
            "body": "old",
            "draft": False,
            "prerelease": False,
        },
    ]
    src = SourceConfig(
        id="llvm-releases",
        name="LLVM Releases",
        org="LLVM",
        category="llvm",
        kind="github_releases",
        github_repo="llvm/llvm-project",
    )
    with patch("csweekly.collectors.github_releases.get_json", return_value=payload):
        result = collect_github_releases(src, window)
    assert len(result.stories) == 1
    assert "21.1.0" in result.stories[0].title
