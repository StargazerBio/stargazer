---
title: unhydrated-notebook-banner
status: done
priority: normal
created: 2026-10-30
pr: 108
---

A pod whose notebook isn't in `/workspace` after the hydrate opens it blank
and never saves it (`SG_UNSAVED_NOTEBOOK`, from ticket
`delete-running-notebook-resurrects`). That's right when the notebook was
deleted, since the pod is being torn down anyway. After a failed hydrate,
though, the user sees a blank notebook, and what they type into it is lost
without a word.

The save banner (`runtime/save_banner.html`, polling `/__sg__/save-status`)
already names files the pod won't save because they're too big. It should
name this one too, saying the notebook didn't load and edits here won't be
saved, so the user reloads instead of working in it.

## Verification recipe: unhydrated-notebook-banner

A notebook pod whose notebook didn't load opens a blank in its place. The banner on the page says so, that nothing typed into it is saved, and links to the dashboard to stop and reopen it.

### Sub-features

- NL-1: `/__sg__/save-status` returns the notebook as `not_loaded`.
- NL-2: the banner leads with it, headed "This notebook isn't being saved", with a link to `/__sg__/dashboard`.
- NL-3: a pod whose notebook did load shows no banner (`not_loaded` is `null`).

### How to get to it (user POV)

Open a workspace notebook from the dashboard when its pod can't load the workspace.

### Driving it

Build the branch's image, then run the hosted launch script with a store it can't reach, so the hydrate fails. With no `SG_AUTH_ISSUER` the proxy lets every request through.

```bash
docker build -f runtime/Dockerfile -t stargazer-verify:unhydrated-banner .
docker run --rm -d --name sg-nl -p 8093:8080 \
  -e STARGAZER_WORKSPACE_ROOT=s3://sg-verify-no-such-bucket-unhydrated \
  -e SG_OWNER_SUBJECT=verify -e AWS_ACCESS_KEY_ID= -e AWS_SECRET_ACCESS_KEY= \
  --entrypoint launch-notebook.sh stargazer-verify:unhydrated-banner edit /workspace/qc.py
curl -s localhost:8093/__sg__/save-status   # NL-1: "not_loaded":"qc.py"
```

Open `http://localhost:8093/` in a browser: the banner shows (NL-2). For NL-3, run the same image with no store (`STARGAZER_WORKSPACE_ROOT` unset) on a notebook that exists, such as `/workspace/tutorials/assets.py` via the default entrypoint, and check `not_loaded` is `null` and no banner shows. `docker rm -f sg-nl` after.

### Gotchas

- The empty `AWS_*` values make the hydrate fail on S3's list request (a 400 for the missing bucket), which is the failure this needs; the launch script logs `warning: could not load saved notebooks` and carries on.
- marimo writes a one-cell blank `qc.py` into `/workspace` as it opens, so the file exists after start; `SG_UNSAVED_NOTEBOOK` is set before marimo starts, from the hydrate's result.

## Outcome

Shipped in PR #108 (merge 94955cc). `/__sg__/save-status` returns the notebook that didn't hydrate as `not_loaded`, and the save banner leads with it: the notebook opened blank, nothing typed into it is saved, and stopping it from the dashboard and opening it again gets it back (reloading wouldn't, since the hydrate only runs at pod start).

Verified with the recipe above on the branch's image run locally through the hosted launch script: NL-1, NL-2 and NL-3 passed. Unit tier 282 passed. Not driven on the Union tenant.

Left: a pod whose notebook was deleted while it started shows the banner too until it's torn down, and there the line "Your saved notebook is unchanged" doesn't hold.
