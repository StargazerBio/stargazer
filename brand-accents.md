---
title: brand-accents
status: done
priority: normal
created: 2026-11-18
pr: 42
---

Follow-up to the unslop passes on the landing page and the dashboard. The tighter layout stays, but the landing page gets back its faint violet and green washes, the lily's glow, green terminal accents and a starfield that moves again (drift, twinkle, parallax toward the pointer, a sparse green minority beside the violet). The dashboard stays without the starfield but takes the same violet and green as highlights, so the two read as one product and the app stops looking sterile: the faint washes behind the page, the tile's violet edge on hover, green on Run and violet on Edit.

Two PRs: StargazerBio/stargazer.bio#10 (landing) and StargazerBio/infra#42 (dashboard).

## Outcome

Shipped in StargazerBio/stargazer.bio#10 (landing: washes, the lily's glow, green terminal accents, the moving starfield) and StargazerBio/infra#42 (dashboard: the landing's washes, a violet tile edge on hover, violet Edit, green Run, a ringed live dot). Verified on a local serve of the landing page and on the devbox dashboard at desktop and phone widths; the starfield's motion was inferred, since the browser pane was hidden. Reaching users needs `./stargazer-users upgrade` from an infra checkout pulled past the merge.

Related: [[board]], [[unslop-landing]], [[unslop-dashboard]]
