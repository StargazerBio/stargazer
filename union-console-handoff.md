---
title: Union console handoff (per-user project access)
status: backlog
priority: normal
created: 2026-09-29
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

- [ ] A link on the dashboard, "View your runs in the Union console" or
      similar, to the dashboard's own project in `development`, not the
      console root. Keep the wording in product terms.
- [ ] Docs: `docs/architecture/app.md` and
      `.opencode/reference/architecture/app_internals.md`.
- [ ] Verify on the test account's Union dashboard: the link opens its
      project's runs.
