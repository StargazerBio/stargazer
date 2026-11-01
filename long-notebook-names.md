---
title: long-notebook-names
status: done
priority: normal
created: 2026-10-18
pr: 55
---

A workspace notebook with a long name is created fine but never launches, and
the dashboard says it's still starting forever.

## Measured (2026-10-18, Union, test account, dashboard at `d83b9b0`)

- Created "interval probe 20261018-180932" (slug
  `interval-probe-20261018-180932`, 30 characters). `/launch` answered 503
  "notebook is still starting; please retry in a moment" 31 times over about
  10 minutes.
- `App.get("nb-interval-probe-20261018-180932-edit")` in `u-pryce` failed:
  KService `nb-interval-probe-20261018-180932-edit-u-pryce-development` not
  found. The app was never created; `get app` doesn't list it.
- A notebook named "ivl", on the same dashboard straight after, launched on
  the first try.

## Cause (measured 2026-10-19)

Flyte won't deploy an app whose name is over 30 characters. The app id's
`name` field carries `max_len: 30` in flyteidl2, and Union's server enforces
it. A notebook's app is `nb-<slug>-<mode>`, so a slug over 22 characters
can never launch in edit mode. The project doesn't matter: Knative names the
service after the app alone, inside a `<project>-<domain>` namespace. The
earlier guess (a revision name over Kubernetes' 63 characters, depending on
the project) was wrong.

- Served a bare app into `u-pryce`: a 31-character name was refused at
  deploy, `app.metadata.id.name: must be at most 30 characters
  [string.max_len]`, and `App.get` on it got the same validation error. A
  30-character name deployed: Knative configuration
  `nb-lenprobe-aaaaaaaaaaaaa-edit` in namespace `u-pryce-development`. Its pod
  then failed only because the probe image had no `fserve`. The probe app is
  deleted.
- `/launch` hid this because a serve error followed by a failed `App.get`
  fell through to the 503 "still starting".

## Fix

- [x] Create refuses a name whose slug is over 22 characters (400, "Notebook
  names can be at most 22 characters."). The limit is the same for every
  project, so it's a constant (`NOTEBOOK_SLUG_MAX` in `app/per_notebook.py`).
  Copy derives its slug from a shipped workflow's title, all of which fit.
- [x] `/launch` returns the serve error when the app it would recover doesn't
  exist. It's a 422, not a 502: Cloudflare, in front of Union apps, swaps a
  502's body for its own "Bad gateway" (ticket [[app-502s-behind-cloudflare]]).
- [x] Unit tests: create at 22 characters (accepted) and 23 (refused), and a
  launch whose deploy was refused.

## Verification (2026-10-19, Union, test account's dashboard)

- Before, on `main` (`482b870`): created "long name probe 20261019" (24
  characters, accepted), and `/launch` for it answered 503 "notebook is still
  starting; please retry in a moment".
- After, on the branch (`3741802`): the same `/launch` answered 422 with
  "Failed to deploy app nb-long-name-probe-20261019-edit with image …,
  Error: validation error: - app.metadata.id.name: must be at most 30
  characters [string.max_len]". Create refused "long name probe 2026101x"
  (23) with the 400 above and accepted "limit probe 2026101923" (22). That
  notebook launched in 17 s (app `nb-limit-probe-2026101923-edit`, exactly 30
  characters) and opened in marimo at `/workspace/limit-probe-2026101923.py`.
- Torn down: every app in `u-pryce` stopped, dashboard included, no live
  runs there or in `flytesnacks`. The two probe notebooks are still in the
  test account's workspace.

## Left open

- The create box still lets you type 60 characters. The page's own check
  would need the limit in the dashboard's template context, which PR #53
  also edits, and the server's refusal already says what the limit is.

## Outcome

Shipped in #55 (merged 2026-10-20, `c08cb45`): create refuses a name whose
slug is over 22 characters, and `/launch` returns the deploy's error as a 422
instead of "still starting". Verified on Union before the rebase onto #53
(above); the unit tier passed after it (500), and the tenant check wasn't
repeated. Left: the create box still accepts 60 characters as you type, and
a 502's body is still replaced by Cloudflare's (ticket
[[app-502s-behind-cloudflare]]).
