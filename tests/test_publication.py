# SPDX-License-Identifier: Apache-2.0
"""Publication presentation layer — briefing cards and evidence-safe copy."""

from csweekly.ai.evidence import CommitEvidence, EvidencePack
from csweekly.ai.writer import write_deterministic
from csweekly.reporters.publication import (
    briefing_cards_from_payload,
    editorial_headline,
    engineering_takeaway,
    path_grounded_targets,
)


def test_path_grounded_targets_drops_aarch64_for_lldb_wasm():
    g = {
        "title": "[lldb][test] Skip more tests that don't work with WebAssembly",
        "what_changed": "Adds skipIfWasm for Green Dragon WebAssembly matrix.",
        "hardware_targets": ["WebAssembly", "AArch64"],
        "stories": [
            {
                "paths": [
                    "lldb/test/API/commands/process/detach-launched/TestDetachLaunched.py",
                    "lldb/test/API/functionalities/breakpoint/breakpoint_while_running/TestBreakpointWhileRunning.py",
                ]
            }
        ],
    }
    assert path_grounded_targets(g) == ["WebAssembly"]


def test_editorial_headline_strips_brackets_and_pr():
    g = {"title": "[AMDGPU] Add an async barrier arrival workaround (#238539)"}
    h = editorial_headline(g)
    assert "AMDGPU" not in h or "async barrier" in h.lower()
    assert "(#238539)" not in h
    assert "async barrier" in h.lower()


def test_engineering_takeaway_rejects_generic_filler():
    g = {
        "title": "LoopVectorize fp unsafe metadata",
        "what_changed": "Adds llvm.loop.vectorize.fp_unsafe.enable metadata.",
        "why_it_matters": (
            "Affects X86 lowering / target code generation. "
            "Matters for CPU compiler engineering. Lives in the Middle-end of the pipeline."
        ),
        "stages": ["Middle-end"],
        "domains": ["CPU"],
        "stories": [{"paths": ["llvm/lib/Transforms/Vectorize/LoopVectorize.cpp"]}],
    }
    take = engineering_takeaway(g)
    assert "Matters for CPU compiler engineering" not in take
    assert "Lives in the Middle-end of the pipeline" not in take
    assert "fp_unsafe" in take or "Middle-end" in take


def test_briefing_cards_prefer_deep_dive_first():
    payload = {
        "deep_dive": {
            "id": "d1",
            "story_id": "d1",
            "title": "[lldb] Skip wasm tests",
            "what_changed": "skipIfWasm on broken API tests.",
            "why_it_matters": "Debugger coverage must follow new targets.",
            "stages": ["Runtime & Toolchain"],
            "domains": ["Languages"],
            "signal": "deep_dive",
            "stories": [
                {
                    "related_ref": "8e1359f4",
                    "source_url": "https://example.com/c",
                    "paths": ["lldb/test/API/foo.py"],
                }
            ],
            "deep_dive_notes": {
                "confidence": "high",
                "factcheck": "pass",
                "validation": "Tests touched: foo.py",
            },
        },
        "high_signal": [
            {
                "id": "h1",
                "story_id": "h1",
                "title": "[AMDGPU] async barrier",
                "what_changed": "Workaround for async barrier arrivals.",
                "why_it_matters": "gfx1250 needs special handling when XNACK is on.",
                "stages": ["Backend"],
                "domains": ["GPU"],
                "hardware_targets": ["AMDGPU"],
                "signal": "high_signal",
                "stories": [
                    {
                        "related_ref": "63b8d2fd",
                        "source_url": "https://example.com/a",
                        "paths": ["llvm/lib/Target/AMDGPU/SIInsertWaitcnts.cpp"],
                    }
                ],
            }
        ],
        "worth_knowing": [],
    }
    cards = briefing_cards_from_payload(payload, limit=5)
    assert cards[0]["headline"]
    assert "FEATURED" in cards[0]["kicker"]
    assert cards[0]["evidence_label"] == "Verified"


def test_implementation_explanation_is_prose_not_file_dump():
    from csweekly.reporters.publication import implementation_explanation, primary_commit

    g = {
        "title": "[lldb][test] Skip more tests that don't work with WebAssembly",
        "what_changed": (
            "These are breaking the new Green Dragon matrix bot that now also tests "
            "WebAssembly. This patch just adds skipIfWasm to all broken tests."
        ),
        "technical_context": (
            "Primary `8e1359f419e7` (+24/−1). Files: "
            "lldb/test/API/commands/process/detach-launched/TestDetachLaunched.py, "
            "lldb/test/API/functionalities/breakpoint/breakpoint_while_running/TestBreakpointWhileRunning.py."
        ),
        "deep_dive_notes": {
            "implementation": (
                "Primary `8e1359f419e7` (+24/−1). Files: "
                "lldb/test/API/foo.py. Diff-referenced symbols include: FooTest."
            ),
            "problem": "Green Dragon WebAssembly matrix was failing on LLDB API tests.",
        },
        "stories": [
            {
                "related_ref": "8e1359f419e7c7b6bf5c3ac9ff34f7c459f43eeb",
                "source_url": "https://github.com/llvm/llvm-project/commit/8e1359f4",
                "paths": [
                    "lldb/test/API/commands/process/detach-launched/TestDetachLaunched.py",
                    "lldb/test/API/functionalities/breakpoint/breakpoint_while_running/TestBreakpointWhileRunning.py",
                ],
            }
        ],
    }
    text = implementation_explanation(g)
    assert "TestDetachLaunched.py" not in text
    assert "Files:" not in text
    assert "skipIfWasm" in text or "WebAssembly" in text
    assert "LLDB API test" in text
    meta = primary_commit(g)
    assert meta["short"] == "8e1359f4"
    assert "github.com" in meta["url"]


def test_watchlist_bucket_ranks_maintenance_low():
    from csweekly.reporters.publication import watchlist_bucket

    assert (
        watchlist_bucket(
            {
                "title": "Fix incorrect comments about sinking ExtractElement",
                "stories": [{}],
                "stages": ["Backend"],
            }
        )
        == "low_priority"
    )
    assert (
        watchlist_bucket(
            {
                "title": "Reuse legal VTYPE for whole-register moves",
                "stories": [{}] * 24,
                "stages": ["Backend"],
                "domains": ["CPU"],
                "impact_score": 4.0,
            }
        )
        == "needs_inspection"
    )


def test_engineering_lessons_are_evidence_bound():
    from csweekly.reporters.publication import engineering_lessons

    lessons = engineering_lessons(
        [
            {
                "title": "[AMDGPU] Add async barrier workaround",
                "what_changed": (
                    "Async barrier arrivals on gfx1250 need a replay workaround "
                    "when XNACK is enabled."
                ),
                "stages": ["Backend"],
                "stories": [
                    {"paths": ["llvm/lib/Target/AMDGPU/SIInsert.cpp"], "related_ref": "abc"}
                ],
            }
        ],
        limit=2,
    )
    assert lessons
    assert "do not generalize" in lessons[0]["lesson"]
    assert "barrier" in lessons[0]["headline"].lower() or "async" in lessons[0]["headline"].lower()


def test_deterministic_why_avoids_matters_for_boilerplate():
    primary = CommitEvidence(
        sha="abcdef1234567890",
        subject="[AMDGPU] Add async barrier arrive workaround",
        body=(
            "Async barrier arrivals on gfx1250 need a replay workaround when XNACK is enabled.\n\n"
            "Insert the pass before waitcnt insertion."
        ),
        files=["llvm/lib/Target/AMDGPU/SIInsertAsyncBarrierArriveWorkaround.cpp"],
        functions=["mayNeedAsyncBarrierArriveWorkaround"],
        tests=["llvm/test/CodeGen/AMDGPU/async-barrier.ll"],
        additions=200,
        deletions=10,
        diff_excerpt="",
    )
    pack = EvidencePack(
        story_id="amdgpu-barrier",
        title_hint=primary.subject,
        primary=primary,
        related=[],
        related_shas=[],
        stages=["Backend"],
        domains=["GPU"],
        hardware_targets=["AMDGPU"],
        errors=[],
    )
    draft = write_deterministic(pack)
    assert "Matters for GPU compiler engineering" not in draft.why_it_matters
    assert "Lives in the Backend of the pipeline" not in draft.why_it_matters
