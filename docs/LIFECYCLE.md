# Weekly publishing lifecycle

CompilerSutra Weekly separates **collection** from **publication**.

```text
RAW DATA → NORMALIZED → CLUSTERED STORIES → EDITORIAL REVIEW → PUBLISHED ISSUE
```

The live site only shows **published** issues. Raw collection never becomes the newsletter automatically.

## Calendar

| | |
| --- | --- |
| Timezone | **Asia/Kolkata** (editorial boundaries) |
| Period | Saturday 00:00 → next Saturday 00:00 (exclusive) |
| Inclusive days | Saturday → Friday |
| Freeze | End of Friday |
| Publish | Saturday |

Example (calendar-correct for 2026):

- Period: Sat 31 Oct → Fri 6 Nov
- Published: Sat 7 Nov (issue `#001`)

Dates are computed by `csweekly week`; do not hardcode them.

## Edition layout

```text
data/editions/
  YYYY/
    YYYY-MM-DD/          # publish Saturday
      edition.yaml       # id, period, status
      raw/stories.jsonl  # retained forever; idempotent merge
      normalized/
      stories/candidates.json
      editorial_report.md
      freeze.json
```

Published artifacts (immutable once shipped):

```text
reports/YYYY/YYYY-MM-DD.md
reports/YYYY/YYYY-MM-DD.changelog.json
reports/YYYY/YYYY-MM-DD.edition.yaml
site/…                   # generated from published reports only
```

### Edition status

`collecting` → `processing` → `review` → `ready` → `published` → `archived`

Do not infer publication from “Markdown exists”.

### Story editorial status

`new` · `candidate` · `selected` · `featured` · `worth_knowing` · `research` ·
`rejected` · `deferred` · `published` · `late` · `next_issue`

Rejected/deferred items stay in the dataset.

## Commands

```bash
csweekly week
csweekly collect          # daily; merges into active edition (idempotent)
csweekly freeze           # Friday close (explicit — process does not freeze)
csweekly process          # normalize + cluster → candidates
csweekly review           # editorial report
csweekly validate         # quality gates
csweekly publish          # Saturday: write reports + mark published + site
csweekly index            # rebuild site (published only)
```

Legacy helpers still work: `report`, `run`, `refresh`.

## Late data

After freeze/publish, new commits go to the **next** edition (or an explicit
addendum). Never silently rewrite a published issue.

## Idempotent collection

Stable keys: `source_id + commit SHA` / PR number / arXiv id / URL.
Re-running collect adds only new unique items.
