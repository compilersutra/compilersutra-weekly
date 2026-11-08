# SPDX-License-Identifier: Apache-2.0
from datetime import date, datetime, timezone
from unittest.mock import patch

from csweekly.collectors.arxiv_api import collect_arxiv
from csweekly.collectors.rss_feed import collect_rss
from csweekly.config import SourceConfig
from csweekly.window import friday_friday_window

UTC = timezone.utc


class _Entry(dict):
    pass


def test_rss_window_filter():
    window = friday_friday_window(as_of=date(2026, 11, 8))

    class Feed:
        entries = [
            _Entry(
                title="In window",
                link="https://example.com/a",
                id="a",
                summary="hello",
                published_parsed=(2026, 11, 2, 12, 0, 0, 0, 0, 0),
            ),
            _Entry(
                title="Out",
                link="https://example.com/b",
                id="b",
                summary="nope",
                published_parsed=(2026, 10, 1, 12, 0, 0, 0, 0, 0),
            ),
        ]

    src = SourceConfig(
        id="feed",
        name="Feed",
        org="Org",
        category="llvm",
        kind="rss",
        feed_url="https://example.com/feed.rss",
    )
    with patch("csweekly.collectors.rss_feed.feedparser.parse", return_value=Feed()):
        result = collect_rss(src, window)
    assert len(result.stories) == 1
    assert result.stories[0].title == "In window"


def test_arxiv_window_filter():
    window = friday_friday_window(as_of=date(2026, 11, 8))

    class Feed:
        entries = [
            _Entry(
                title="Cool  paper",
                link="https://arxiv.org/abs/2601.00001",
                id="http://arxiv.org/abs/2601.00001",
                summary="about LLVM",
                published_parsed=(2026, 11, 4, 0, 0, 0, 0, 0, 0),
            )
        ]

    src = SourceConfig(
        id="ax",
        name="arXiv",
        org="arXiv",
        category="research",
        kind="arxiv",
        arxiv_query="all:LLVM",
    )
    with patch("csweekly.collectors.arxiv_api.feedparser.parse", return_value=Feed()):
        result = collect_arxiv(src, window)
    assert len(result.stories) == 1
    assert result.stories[0].related_ref.endswith("2601.00001")
