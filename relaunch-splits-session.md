---
title: relaunch-splits-session
status: doing
priority: high
created: 2026-11-24
---

Opening a running notebook from the dashboard (Open, or Edit/Run again)
POSTs `/launch`, which re-serves the app to reconcile it to the current spec.
That's meant to be a no-op for a warm, current pod, but it isn't: Flyte's
default app version is an md5 over `cloudpickle.dumps` of the environments,
the dashboard's code bundle and the image cache. Those bytes change whenever
the dashboard's own image or code changes, even when the pod's spec doesn't.
A new version is a new Knative revision, and the new revision takes all new
traffic while the open tabs' websockets keep the old pod alive. The page then
talks to two pods: its sockets go to the old one, its HTTP calls (run, save,
takeover) to the new one, whose marimo answers 401.

Seen on the test account 2026-11-24 (`nb-crop-gmm-edit`): the dashboard was
redeployed at 18:47 UTC, and the next Open at 19:19:49 made revision 00002.
The two revisions' pod specs were identical apart from the version (same
image digest, same `--tgz`, same `--image-cache`). The new tab came up as a
marimo reader, and its three Take over POSTs got `401` from the new pod.

## Plan

Fix is in `StargazerBio/infra`, branch `fix/relaunch-splits-session`.

- [ ] Version a per-notebook app by its spec: the md5 of the app spec Flyte
      deploys (`translate_app_env_to_idl`, with the version left empty),
      passed to `with_servecontext(version=...)`. Same spec, same version, so
      no new revision. Any real change (image, resources, env, settings)
      still makes a new version.
- [ ] Serve per-notebook apps with `copy_style="none"`: the pod runs the
      image's launch script, and the dashboard's code bundle in its spec
      only ties notebook pods to dashboard code changes.
- [ ] Unit test: two separately built envs for one launch get the same
      version, and changing what the pod runs changes it.
- [ ] Verify on the tenant: Open a running notebook, then redeploy the
      dashboard and Open again. The revision count stays at one and the open
      tab keeps editing. Stop then Launch still brings the pod back, and a
      changed setting still redeploys it.

A real spec change on Open still replaces a pod that has a tab open, with
the same split. That's left for a follow-up, if it bites.

Related: [[board]]
