---
title: delete-running-notebook-resurrects
status: backlog
priority: normal
created: 2026-10-30
---

Deleting a workspace notebook whose pod is up doesn't stick: the pod's last
save writes the notebook back after the delete. Infra's `workspace_delete`
deactivates and deletes the notebook's apps, then deletes `<slug>.py` from the
workspace store, but deactivation only starts the pod's shutdown, and the
pod's final save on the way down (stargazer's save proxy) puts the file back
once the store's delete has already happened. The tile comes back on the next
page load.

Measured on the Union tenant (test account `u-pryce`, 2026-10-30), from the
user bucket's object versions (`aws s3api list-object-versions`), while
verifying ticket `launch-delete-while-serving`:

- `ldws-verify.py`, pod admitted and starting when deleted (dashboard at the
  fix branch): delete marker 15:08:13, then a 1083-byte PUT at 15:08:18 (the
  notebook was 1061 bytes before launch; marimo rewrote it when it opened).
- `ldws-repro.py`, same on `main`: delete marker 15:10:19, PUT at 15:10:24.

A pod that was ready when deleted didn't do it: `ldws-repro2`'s pod, ready
from 15:11:26, deleted at 15:14:37, wrote nothing back (its delete marker is
still the latest version). So the measured cases are pods deleted while
starting, whose shutdown save seems to treat the whole hydrated workspace as
changed (inferred, not traced in the save proxy).

Where the fix goes is open. The dashboard could delete the store file only
after the pod has gone, or delete it again once it has. Or the pod could skip
its final save when its app is being deleted rather than stopped, which would
be a pod contract change in this repo.
