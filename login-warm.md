---
title: login-warm
status: maybe
priority: low
created: 2026-10-30
---

A cold login now waits ~60 s on GitHub's page while the login app (infra `app/login.py`) starts, against ~13 s for the dashboard behind it (measured in ticket [[login-cold-start]]). Keeping one login replica up (`Scaling(replicas=(1, 1))` on `login_env`) would remove that wait, but app pods only schedule on the `union-us-west-2-awsr7i2xlarge` pool, so it keeps a whole r7i.2xlarge running (~$385/month, a guess from list price).

Before deciding, ask Union:

- whether always-on apps can run on a smaller pool;
- whether new nodes can have Knative's queue-proxy image cached (16 s of every new node's first app).
