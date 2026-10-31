---
title: login-cold-start
status: review
priority: low
created: 2026-10-30
pr: 26
---

The login app (infra `app/login.py`) scales to zero after an hour idle, like the dashboard, so the first login after a quiet hour waits for its pod to start, and then for the dashboard's if that's asleep too. Measure the login app's cold start on the tenant: let it scale to zero, then time `stargazer.bio/login` to the dashboard rendering. If the wait is noticeable, keep one replica running (`Scaling(replicas=(1, 1))` on `login_env`) and note what that costs.

## Measured (2026-10-30, kubectl events and container logs, the test account's first login after both apps scaled to zero)

97 s from the login pod's creation (18:08:48 UTC) to the dashboard being ready (18:10:25). The browser stays on GitHub's sign-in page for the first 58 s, while Union's gate holds the redirect to the cold login app.

- Login app, 58 s: 33 s for Karpenter to bring up an r7i.2xlarge (no user-workload node was left once both apps scaled down), 3 s to pull the login image, 16 s to pull Knative's queue-proxy sidecar from gcr.io onto the fresh node, then 4 s for `fserve` and uvicorn to start.
- Dashboard, 39 s, on the node that was now warm: 4 s image pull, then 26 s inside the container before uvicorn logs "Started server process", then Flyte init (2 s) and the readiness probe. Not yet split: the code bundle is 795 KiB, and importing `app.admin_app` takes ~1 s warm and ~3 s with no bytecode cache locally.

App pods only schedule on the `union-us-west-2-awsr7i2xlarge` pool (the m7a default nodes fail the pods' node affinity), so one always-on login replica keeps a whole r7i.2xlarge running.

## Pieces

- [x] The dashboard's CPU: it set none, so Union capped it at 100m and startup took ~26 s. `cpu=("100m", "1")` brings it to 3.9 s from container start to uvicorn (infra `fix/dashboard-cpu`, PR #20). Cause measured in a probe task with the dashboard's image and `fserve` command: 25.6 s at 100m, 2.5 s at 1 CPU
- [x] An "Opening your workspace" page: the login app answers 200 with a `Refresh` header to the dashboard instead of a 302, so the browser shows that page, not GitHub's, while the dashboard starts (StargazerBio/infra#26). Held cold start on the tenant (2026-10-31, Union's app conditions, both apps at zero since ~22:45 UTC, `stargazer.bio/login` opened at 00:22:45): login woke 00:22:48 and was ready 00:23:48 (60 s), the dashboard woke 00:23:50 and was ready 00:24:03 (13 s, the CPU fix), and the browser landed on the dashboard. That the page showed for those 13 s is inferred (the browser pane was hidden, so no screenshot)
- [ ] Keeping the login app warm, which means keeping an r7i.2xlarge up (~$385/month, a guess from list price): now the larger part of a cold login (60 s on GitHub's page against the dashboard's 13 s). Ask Union whether always-on apps can run on a smaller pool, and whether new nodes can have the queue-proxy image cached (16 s of every new node's first app)
