# Publishing

1. Friday→Friday UTC window closes.
2. Saturday job: `csweekly run` (or collect subset) → `reports/YYYY/YYYY-MM-DD.md`.
3. `csweekly index` copies reports into `site/` for GitHub Pages.

Enable Pages on the repo: **Settings → Pages → Deploy from GitHub Actions** (workflow `pages.yml`).

CompilerSutra.com should only link to the Pages URL / repo — no Vercel Python.

## Discovery and traffic

`csweekly index` writes:

- `site/sitemap.xml` — all public HTML URLs
- `site/robots.txt` — `Allow: /` plus `Sitemap:` pointing at the Pages sitemap

**Google Search Console (compilersutra.com property):** Weekly is served at
`https://www.compilersutra.com/weekly/` (Vercel rewrite → GitHub Pages). Submit
`weekly/sitemap.xml` on the existing `www.compilersutra.com` property. Do not
submit the github.io sitemap there.

**Analytics (pageviews):** Cloudflare Web Analytics (cookieless). Create a beacon in
the Cloudflare dashboard, then set repo secret `CSWEEKLY_CF_BEACON_TOKEN`. The Pages
workflow injects it into every page via `_shell`. Leave the secret empty to ship
without analytics.
