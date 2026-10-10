---
title: App internal addresses skip Union's login
status: backlog
priority: high
created: 2026-10-06
---

Every app answers at `http://<app>.<project>-<domain>.svc.cluster.local` with no login and no
identity headers; a task pod in the same project reached a
`requires_auth=True` app that way (measured, plan 27 Piece 0). Untested:
whether pods in other projects can reach it, and whether a forged
`X-User-Subject` sent there gets through the dashboard's owner check. If
both hold, code in any pod can act as any user on their dashboard. One fix
is to verify the signed `X-User-Token` ID token instead of trusting
`X-User-Subject`; another is per-namespace network policy.
