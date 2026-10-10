---
title: Self-serve onboarding
status: backlog
priority: high
created: 2026-10-06
---

New users are onboarded by an org admin (`stargazer-users onboard`, which sends Union's invite), since Union
doesn't auto-provision users on first sign-in. Unverified: that the
subject `User.create` returns is the one the user's first GitHub sign-in
arrives with; check with a real second address before onboarding anyone
new. If Union adds self-serve sign-up, onboarding could run on first
sign-in instead.
