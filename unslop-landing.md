---
title: unslop-landing
status: done
priority: normal
created: 2026-11-18
pr: 9
---

A polish pass on the landing page (StargazerBio/stargazer.bio `index.html`, `login/`) to match ticket unslop-dashboard: the radial washes, the lily's glow and the frosted terminal go, the starfield stays but holds still (constellation lines only near the cursor), the ink ramp replaces GitHub's palette, off-white primary button, spacing on a 4px grid. Layout and copy stay. Cut from `feat/waitlist` (stargazer.bio PR 7), so its PR waits for that one.

PR 8 merged into `feat/waitlist` on 2026-11-18 at 19:14:43, 32 seconds after PR 7 had merged `feat/waitlist` into `main`, so its commit `7f38666` is on `feat/waitlist` and `design/unslop-landing` only, not on `main`. stargazer.bio PR 9 takes the same commit into `main`.

## Outcome

Shipped in stargazer.bio PR 9 (merge `62d7b35`, the change's commit `7f38666`): the washes, glow and frosted surfaces are gone, the starfield holds still with constellation lines near the pointer, the ink ramp and a 4px grid replace GitHub's palette, and the login page takes the same tokens. Verified by serving the branch locally at 1440×900 and 375×812 (hero, hover lines, waitlist section, login page, no horizontal scroll on the phone), and by `git merge-tree` against `main`, keeping its Formspree endpoint. The waitlist form's submission and the live site weren't checked. A product view in the hero was considered and dropped. The docs stylesheet shipped with ticket unslop-docs.

Related: [[board]] [[unslop-dashboard]]
