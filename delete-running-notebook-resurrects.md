---
title: delete-running-notebook-resurrects
status: review
priority: normal
created: 2026-10-30
pr: 106
---

Deleting a workspace notebook whose pod is up or starting doesn't stick: the
pod writes the notebook back after the delete, and the tile comes back on the
next page load. There are two paths:

- **A pod that hydrated the notebook** uploads it again on a pass after the
  delete, because it changed since the pod's last pass. A starting pod's
  always has, since marimo rewrites a notebook as it opens it. Infra's
  `workspace_delete` stopped the pods before deleting from the store, so the
  shutdown pass ran while the notebook was still stored.
- **A pod that starts after the delete** finds no notebook in `/workspace`.
  marimo opens a blank one, and the pod saves it as a new file: an empty
  notebook comes back. A failed hydrate did the same over a stored notebook,
  with nothing deleted at all.

The fix is in two PRs, StargazerBio/stargazer#106 (the pod) and
StargazerBio/infra#17 (the dashboard):

- [x] Pod: a changed file it hydrated or saved is uploaded only if the store
  still has it.
- [x] Pod: a workspace notebook missing after the hydrate
  (`SG_UNSAVED_NOTEBOOK`, set by the launch script) is never uploaded.
- [x] Dashboard: delete the notebook from the store before stopping its pods.
- [ ] Release with stargazer#106, then bump infra's pin. The dashboard change
  only takes effect with pods that keep the rule.

## Verification

On the Union tenant, as the test account `u-pryce` (save interval 5 s), read
from the user bucket's object versions:

| Pods | Dashboard | Deleted | Came back |
|---|---|---|---|
| release | `main` | `ldws-verify`, `ldws-repro`, while starting | yes: 1083-byte PUTs 5 s after their delete markers |
| release | `main` | `ldwr-base`, as its launch returned | yes: a 0-byte PUT 44 s after the marker |
| stargazer#106 | `main` | `ldwr-fix-d{0,6,10,15}` | 2 of 4: PUTs 1–2 s after their markers (old delete order) |
| stargazer#106 | infra#17 | `ldwr-v2-d{0,20,45,60,70,85}`, that many seconds after launch | none, at 2–3 min after the deletes |
| stargazer#106 | infra#17 | four leftovers, including `ldwr-img` with a ready pod | none, at 67 s after the deletes |

Inside a running pod, `flyte.storage.exists` on S3 answered `False` for a key
whose latest version is a delete marker. New unit tests:
`test_a_file_deleted_from_the_store_is_not_put_back` and
`test_a_notebook_that_did_not_hydrate_is_never_saved` (stargazer), and
`test_delete_removes_the_notebook_before_stopping_its_pods` (infra). Each
failed before its fix.

Left: a pass whose `exists` check runs just before the delete still uploads
just after it, which only a conditional write would close. Edits made in a
pod whose hydrate failed are now silently unsaved, and the save banner
doesn't say so yet.

## Verification recipe

1. Build stargazer's branch image for amd64 and push it as
   `ghcr.io/stargazerbio/debug:<slug>`.
2. Deploy the test dashboard from infra's branch with
   `STARGAZER_NOTEBOOK_IMAGE` set to it (`verify-dashboard`'s
   `union_dashboard.py deploy`). Confirm the served image with
   `union_dashboard.py check nb-<slug>-edit`.
3. From the dashboard page, in one script, create several workspace
   notebooks, `POST /launch` each, and `POST /workspace/delete` each a
   different number of seconds after its launch returns: 0, 20, 45, 60, 70,
   85. That spans the image pull, the hydrate, marimo's rewrite, and after.
4. A couple of minutes later, list the object versions under
   `users/<subject>/workspace/` in the user bucket
   (`aws s3api list-object-versions`). Every notebook's latest version must
   be its delete marker.
5. Tear down with `union_dashboard.py teardown`.
