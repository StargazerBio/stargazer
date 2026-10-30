---
title: launch-delete-while-serving
status: review
priority: low
created: 2026-10-29
pr: 16
---

Deleting a workspace notebook removes its launch rows (ticket
`launch-row-on-delete`), but not a serve already under way. When a
notebook's image build has finished and the dashboard is serving its pod
(`_serving` in infra's `app/admin_app.py`), a delete in that window leaves
the serve running: the serve's own settle finds the row gone and writes
nothing, but the pod being served can still come up for a notebook that no
longer exists. Not reproduced; deferred from StargazerBio/infra#13. The fix
would cancel or stop the serve on delete, or stop the app once it settles
with no row.

The PR is StargazerBio/infra#16 (branch `fix/launch-delete-while-serving`).
The fix is the first option: the delete drops the launch rows first, so no
poll can claim one to serve, cancels this process's serve after the build and
waits for it, and only then takes the app down, so an app the serve had
already admitted goes too.

## Verification

Reproduced on the Union tenant (test account `u-pryce`) with `main`: the
delete landed right after the poll that claimed the built launch. The serve
then admitted `nb-ldws-repro2-edit` 3 s later, and it was active ("Service is
ready") within 25 s. `/launch/status` reported it running with no tile, and
the pod wrote a 0-byte `ldws-repro2.py` back over the delete marker. With
the fix, in the same window (`ldws-fix2`), the app never existed (90 one-second
`App.get` polls answered not found), and the delete marker stayed the latest
version. Deleted after admission, while its container was starting
(`ldws-verify`), the app was gone when the 0.38 s delete returned and stayed
gone for 220 polls. Unit: a test of a delete before the built pod is served
failed on `main` and passes with the fix, and one of a delete inside the
serve's watch shows no app is left half-deployed.

Turned up separately: a pod deleted while starting writes its notebook back
on its shutdown save, about 5 s after the delete. That bug is on `main` too
and isn't fixed by infra#16; ticket `delete-running-notebook-resurrects`.

## Verification recipe

Dashboard on Union via `verify-dashboard`'s `union_dashboard.py deploy`.
Create a workspace notebook whose `main_env` declares
`image=notebook_base.with_env_vars({"LDWS_VERIFY": "<unique>"})`, so its
image needs a build. `POST /launch` (202), then wait for the build run to
succeed (`Run.get` in the user's project). Then, from the dashboard page in
one script, `GET /launch/status` (claims the row and starts the serve) and
right away `POST /workspace/delete`. Watch `App.get("nb-<slug>-edit")` every
second: it must never come up. Read the notebook's object versions in the
user bucket (`aws s3api list-object-versions`): the delete marker must stay
the latest. Tear down with `union_dashboard.py teardown`.
