---
title: login-cold-start
status: backlog
priority: low
created: 2026-10-30
---

The login app (infra `app/login.py`) scales to zero after an hour idle, like the dashboard, so the first login after a quiet hour waits for its pod to start, and then for the dashboard's if that's asleep too. Measure the login app's cold start on the tenant: let it scale to zero, then time `stargazer.bio/login` to the dashboard rendering. If the wait is noticeable, keep one replica running (`Scaling(replicas=(1, 1))` on `login_env`) and note what that costs.

## Measured (2026-10-30, kubectl events and container logs, the test account's first login after both apps scaled to zero)

97 s from the login pod's creation (18:08:48 UTC) to the dashboard being ready (18:10:25). The browser stays on GitHub's sign-in page for the first 58 s, while Union's gate holds the redirect to the cold login app.

- Login app, 58 s: 33 s for Karpenter to bring up an r7i.2xlarge (no user-workload node was left once both apps scaled down), 3 s to pull the login image, 16 s to pull Knative's queue-proxy sidecar from gcr.io onto the fresh node, then 4 s for `fserve` and uvicorn to start.
- Dashboard, 39 s, on the node that was now warm: 4 s image pull, then 26 s inside the container before uvicorn logs "Started server process", then Flyte init (2 s) and the readiness probe. Not yet split: the code bundle is 795 KiB, and importing `app.admin_app` takes ~1 s warm and ~3 s with no bytecode cache locally.

App pods only schedule on the `union-us-west-2-awsr7i2xlarge` pool (the m7a default nodes fail the pods' node affinity), so one always-on login replica keeps a whole r7i.2xlarge running.
