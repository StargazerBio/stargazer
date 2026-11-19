---
title: retake-dashboard-screenshot
status: review
priority: low
created: 2026-11-19
pr: 168
---

`docs/assets/dashboard-assets.jpg`, on Getting Started, shows the asset explorer from before ticket unslop-dashboard. That redesign is now live on every user's dashboard (infra PR 40, rolled out with release `2026.11.18.1`), so the picture no longer matches what users see. Retake it from the test account's dashboard at the same framing and replace the file.

## Verification recipe

1. Wake the test dashboard (`App.get(name="dashboard", project="u-pryce", domain="development").activate(wait=True)` from an infra checkout with `tenant.env` loaded), sign in to the console in the built-in browser with the GitHub SSO button, and open the dashboard from that page.
2. In Assets, turn off **Mine** and turn on **Public**, leaving **Stargazer** on, in Graph view. Set the viewport to 800×760 so the browser's screenshot is 1:1, and scroll the section's heading to about 20 px from the top.
3. Zoom until labels show (they fade in from zoom 1.1), then pan and drag stars until all of them are in frame. Capture the region from x 12 to 788 and y 0 to 690 with the browser tool's `zoom`, which saves a PNG, and crop 8 px from each side (`sips --cropToHeightWidth 690 760 --cropOffset 0 8`). Save it as JPEG quality 90.
4. Tear down with `union_dashboard.py teardown`: `stopped: ['dashboard']`, `live runs: []`.

Rendering the page with a CDN script and posting the image to localhost was refused by the permission classifier; the browser tool's own saved capture is what works.

Related: [[board]] [[unslop-docs]] [[unslop-dashboard]]
