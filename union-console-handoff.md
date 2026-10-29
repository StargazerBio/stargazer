---
title: union-console-handoff
status: done
priority: normal
created: 2026-09-29
pr: 66
---

Add a link from each user's dashboard to the Union console, deep-linked to
their own project, so they can see their runs there (execution graphs, logs,
retries, inputs and outputs) rather than our re-implementing them.

Everything else this ticket covered has shipped, mostly through plan 26's
onboarding. `stargazer-users onboard` creates each user's `u-<handle>`
project, deploys their dashboard into it, and binds built-in `contributor` on
it, and nothing else, to their Union subject. Verified 2026-10-06: the
onboarded test account sees exactly one project in the console, its own.
Union confirmed that console deep links survive the sign-in redirect, so the
user lands where they clicked. The full plan (Pieces 0–7, Union's answers)
is in this file's history on the `planning` branch.

- [x] A link on the dashboard, "View your runs in the Union console" or
      similar, to the dashboard's own project in `development`, not the
      console root. Keep the wording in product terms.
- [x] Docs: `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`.
- [x] Verify on the test account's Union dashboard: the link opens its
      project's runs.

Verified 2026-10-21 (PR #66): the link on `u-pryce`'s dashboard is
`https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs`,
and clicking it as the test account opened `u-pryce`'s runs in Development,
signed in. The host comes from the app pod's `_U_EP_OVERRIDE`, measured as
the bare tenant host. The devbox shows no link.

## Outcome

Shipped in PR #66 (merge `1d55737`): the dashboard header links to its own project's runs in the Union console, with the host from the app pod's `_U_EP_OVERRIDE`. No link off Union.

Verified (measured): unit tier 519 passed, with the new tests failing first. On the test account's deployed dashboard, the link opened `u-pryce`'s runs in Development, signed in. The dashboard was deactivated afterwards, with nothing left running in `u-pryce` or `flytesnacks`.

Left: the sign-in redirect on a deep link wasn't exercised, since the browser was already signed in. No new tickets.
