---
title: Split the app into its own repo
status: maybe
priority: low
created: 2026-10-27
blocked_by:
  - sdk-package
---

Move `app/` (the dashboard, notebook pods and dashboard deploy) out of this
repo and leave the SDK (`src/stargazer`) here. It has come up three times,
each time from a different pain, and each time the answer was no:

- **2026-10-14**, from notebook image rebuilds on every release: stay one
  repo and package only the SDK (ticket `sdk-package`). The import-layer rule
  already gives most of what a boundary would.
- **2026-10-21**, "getting out of hand for one repo", as AWS admin calls
  crept into onboarding: onboarding and the AWS stacks moved to
  `StargazerBio/infra`, and `app/` stayed. The note then: once the app can
  pin a released SDK, the app and infra could share a repo as the deploy side.
- **2026-10-27**, while scoping `sdk-package`: shelved, because the SDK runs
  from source everywhere and a split would make an installed-SDK path
  mandatory in every place the app uses it.

Each time, the pain that raised it was fixed in place or by a narrower split.
This ticket holds the comparison so the next round starts from it.

## Pros and cons

Measured 2026-10-27 unless marked.

| Area | For splitting | Against splitting |
|---|---|---|
| Change flow | SDK-only and app-only PRs stop sharing CI and review. | 18 of the last 40 merged PRs touched both `src/` and `app/` (6 SDK only, 12 app only). Each of those becomes an SDK PR, a tag, and an app PR that bumps the pin, verified across both. |
| How the app gets the SDK | — | The app finds the SDK through `PROJECT_ROOT`: task images (`with_uv_project`), the notebook image (copies `src/` to `/stargazer`), the dashboard image, the `.flyte/` config. Split, each needs an installed-SDK path, which is the `sdk-package` work that was shelved for adding that second path. |
| Install for SDK users | An SDK install stops carrying `app/` and its dependencies (today `include = ["stargazer*", "app*"]`). | Fixable in one repo with an SDK-only distribution, the split piece of `sdk-package`. |
| Boundary | A repo boundary can't be crossed by accident, and the contracts (asset keyvalues, the index table, the dashboard-to-pod env vars) become explicit API. | TID251 already bans SDK→app imports. The other way is 20 import lines into 8 SDK modules, 2 of them private: `_stamp_owner` in `app/assets.py`, `_run` in `app/notebook_agent.md`. The contracts are written down in `docs/architecture/app.md`. |
| Compatibility | Versioned contracts, worth having once outside users exist. | An app pinned to SDK N needs a compatibility window for every contract change, against "don't consider backwards compatibility" before 1.0. |
| Versioning | Each side releases at its own pace. | A dashboard reports one commit as its version (`STARGAZER_VERSION`, from `release_version`). Split, it has two. |
| Image rebuilds | — | Doesn't fix the 2026-10-14 trigger by itself: the notebook image bakes `app/proxy.py` and the SDK source either way. Pinning a released SDK and baking less of `app/` fix it, both doable in one repo. |
| Infra | Infra imports `app.deploy`, `app.init` and `app.config` as well as the SDK. With the app and infra in one deploy-side repo, infra would depend on the SDK alone. | Infra is the measured cost of a cross-repo seam: `PYTHONPATH=<checkout>:<checkout>/src` to test against a branch, a `.claude/worktrees/stargazer` link in every infra worktree, a hand-kept list of stargazer names that are API, and merge order between repos. |
| Tooling | Smaller context per repo: an SDK session doesn't load the app's docs or skills (inferred). | AGENTS.md, the skills, pre-commit, the ruff pins, the docs site and its nav, and worktree setup all double. The devbox (`devbox/`, its test tier) and `verify-stargazer` drive the SDK through the app and would straddle both. |
| Visibility | The clean way to have a public SDK and a private platform. | Both are public today, with no plan otherwise. |
| Ownership | Separate owners for the bioinformatics and platform sides. | One owner today. |

## When to revisit

Any one of these:

- The SDK should be public and the platform private.
- Someone outside the team pins SDK versions.
- Separate people own the bioinformatics and platform sides.
- The two sides' release cadences actively fight.
- Far fewer PRs cross the seam than the 18 in 40 above. To rerun:

```bash
git log origin/main --merges --first-parent -n 40 --format=%H | while read h; do git diff --name-only "$h^1" "$h" | cut -d/ -f1 | sort -u | tr '\n' ' '; echo; done | awk '/(^| )src /{s=1} /(^| )app /{a=1} {if(s&&a)b++; else if(s)so++; else if(a)ao++; s=a=0} END{print "both", b, "sdk-only", so, "app-only", ao}'
```

`sdk-package` lands first either way, since a split-off app needs an
installed SDK.

## Open questions

- **Where the app goes.** Its own repo, or into infra as one deploy-side repo
  (the 2026-10-21 leaning).
- **Where the devbox goes.** It runs SDK tasks and deploys a dashboard.
- **Where the notebooks go.** The tutorials teach the SDK; the workspace
  seeds and `notebook_base` are app content (ticket `top-level-notebooks`).
