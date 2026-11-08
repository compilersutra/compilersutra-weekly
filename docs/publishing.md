# Publishing

1. Friday→Friday UTC window closes.
2. Saturday job: `csweekly run` (or collect subset) → `reports/YYYY/YYYY-MM-DD.md`.
3. `csweekly index` copies reports into `site/` for GitHub Pages.

Enable Pages on the repo: **Settings → Pages → Deploy from GitHub Actions** (workflow `pages.yml`).

CompilerSutra.com should only link to the Pages URL / repo — no Vercel Python.
