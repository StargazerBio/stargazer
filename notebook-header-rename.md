---
title: Saved notebooks name stargazer-bio in their headers
status: backlog
priority: high
created: 2026-10-28
---

The package is `stargazer-bio` from the split (ticket `split-app-repo`) on,
but every notebook a user saved before it names the old one in its PEP 723
header:

```
# dependencies = [
#   "stargazer",
# ]
# [tool.uv.sources]
# stargazer = { path = "/stargazer", editable = true }
```

The image's `/stargazer` is now `stargazer-bio`, and uv refuses the mismatch
(`Package metadata name stargazer-bio does not match given name stargazer`,
measured in the image), so the notebook's sandbox never builds and it won't
open. All 7 of the test account's saved notebooks have the old header
(measured on the tenant, 2026-10-28); every user's copies of the templates and
workflows will too.

Rewrite those two lines (and `"stargazer[...]"` extras) in every user's
workspace store, `<STARGAZER_WORKSPACE_ROOT>/users/<subject>/workspace/*.py`,
once, before the first `stargazer-users upgrade` onto a renamed release. A
one-off admin step in infra, run by an org admin with the tenant bucket's
access: it changes users' files, so it reports what it would change first.
Published notebooks on Pinata keep their old header; a copy into a workspace
would need the same rewrite.
