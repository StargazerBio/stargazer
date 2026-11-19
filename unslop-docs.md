---
title: unslop-docs
status: done
priority: normal
created: 2026-11-18
pr: 162
---

The docs site's stylesheet (`docs/stylesheets/stargazer.css`) takes the landing page's tokens from ticket unslop-landing: the violet and green wash goes, the dark scheme moves to the ink ramp and its three text roles, headings drop to weight 500, the header and footer sit behind a hairline. Left for after ticket unslop-dashboard deploys: retake `docs/assets/dashboard-assets.jpg`, which shows the old asset explorer.

## Outcome

Shipped in Stargazer PR 162 (`c90ef3b`, 2026-11-18). Verified: `zensical
build --clean` builds clean, and Getting Started and the API reference
served locally at 1440×900 show the ink background, no wash, weight-500
headings. Not checked: the light scheme and phone width. Left: the
Getting Started screenshot, ticket [[retake-dashboard-screenshot]].

Related: [[board]] [[unslop-landing]] [[unslop-dashboard]]
