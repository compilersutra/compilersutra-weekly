# SPDX-License-Identifier: Apache-2.0
from csweekly.collectors.filters import subject_ignored
from csweekly.config import SourceConfig


def test_ignore_merge_and_nfc():
    src = SourceConfig(id="x", name="x", org="o", category="llvm")
    assert subject_ignored("Merge pull request #1", src)
    assert subject_ignored("[NFC] fix comment", src)
    assert not subject_ignored("InstCombine: fold add", src)
