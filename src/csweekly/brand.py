# SPDX-License-Identifier: Apache-2.0
"""Public URLs for CompilerSutra Weekly."""

from __future__ import annotations

import os

REPO_URL = "https://github.com/compilersutra/compilersutra-weekly"
# Canonical public URL (proxied on compilersutra.com). GitHub Pages remains the origin.
PAGES_URL = "https://www.compilersutra.com/weekly/"
GITHUB_PAGES_URL = "https://compilersutra.github.io/compilersutra-weekly/"
EDU_URL = "https://www.compilersutra.com/"
ISSUES_URL = f"{REPO_URL}/issues"
# Cloudflare Web Analytics (cookieless). Set via env in Pages deploy, or leave empty.
CLOUDFLARE_WEB_ANALYTICS_TOKEN = (
    os.environ.get("CSWEEKLY_CF_BEACON_TOKEN", "").strip()
)
PROJECT_NAME = "CompilerSutra Weekly"
# Short nav chip — specific, not a slogan about "the ecosystem"
BRAND_TAG = "LLVM · GCC · MLIR · GPU — curated weekly"
META_DESCRIPTION = (
    "A weekly brief of selected LLVM, GCC, MLIR and GPU compiler changes, "
    "with context on what changed and why it matters."
)
HERO_KICKER = "Weekly compiler intelligence"
HERO_TITLE = "The compiler changes worth understanding"
HERO_LEDE = (
    "LLVM, GCC, MLIR and GPU compiler developments — filtered, explained, "
    "and connected to the compiler pipeline."
)
# Editorial week: Saturday→Friday (Asia/Kolkata); public site shows published editions only
CADENCE = (
    "Published every Saturday. Each edition covers Saturday→Friday "
    "(Asia/Kolkata), frozen at end of Friday. Raw collection stays private; "
    "only the curated edition is published."
)
CONTACT_NOTE = (
    "Corrections and questions: open a GitHub issue on the weekly repository."
)
# Same Google Form used on compilersutra.com (“Weekly Compiler Notes”) —
# no separate Mailchimp/SendGrid stack for this static Pages site.
NEWSLETTER_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSebP1JfLFDp0ckTxOhODKPNVeI1e21rUqMJ0fbBwJoaa-i4Yw/viewform"
)
NEWSLETTER_FORM_LABEL = "Subscribe by email"
