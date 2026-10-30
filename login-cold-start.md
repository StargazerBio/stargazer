---
title: login-cold-start
status: backlog
priority: low
created: 2026-10-30
---

The login app (infra `app/login.py`) scales to zero after an hour idle, like the dashboard, so the first login after a quiet hour waits for its pod to start, and then for the dashboard's if that's asleep too. Measure the login app's cold start on the tenant: let it scale to zero, then time `stargazer.bio/login` to the dashboard rendering. If the wait is noticeable, keep one replica running (`Scaling(replicas=(1, 1))` on `login_env`) and note what that costs.
