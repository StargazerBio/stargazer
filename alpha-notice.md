---
title: Alpha notice against uploading sensitive data
status: review
priority: high
created: 2026-10-13
pr: 21
---

Users' storage isn't isolated yet: every project on the tenant runs as one IAM
role, so code in one user's notebook could read another user's objects
([per-user-storage-isolation](per-user-storage-isolation.md)). Until that's
hardened, say plainly what not to upload. The dashboard footer and the asset
page's upload form read "Stargazer is alpha software. Don't upload sensitive
data, such as identifiable patient data." `docs/architecture/app.md` stops
claiming Flyte's per-project storage isolates users.

Decided and built on 2026-10-08 as part of plan 28, on
`feat/private-assets-object-storage`, which never reached `main`. Salvaged onto
`feat/alpha-notice` (80b9465), rebased past the dashboard footer's new deploy
version.

- [x] `app/templates/_alpha_note.html`, included in `dashboard.html`'s footer
      and `assets.html`'s upload form; `docs/architecture/app.md` updated
- [x] Tests in `tests/unit/test_app.py` and `tests/unit/test_assets_routes.py`
      fail with the notice emptied and pass with it; unit tier 400 passed
- [x] Check the footer by eye on a dashboard (version, notice, cleanup
      control), since the footer changed after the first by-eye check:
      deployed on the devbox, checked 2026-10-13
- [x] PR #21
