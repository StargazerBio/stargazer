---
title: onboard-subject-check
status: backlog
priority: high
created: 2026-11-16
---

Onboarding creates a user with `User.create` and keys their project, policy and dashboard on the subject it returns. Unverified: that this is the subject the user's first GitHub sign-in arrives with (`X-User-Subject`). It's the one open check left in ticket [[per-user-dashboard]], and it has to hold before anyone new is onboarded: if the two differ, a new user's sign-in matches no dashboard.

Check it on the tenant with a real second address (not the test account): onboard it, sign in as it for the first time, and compare the dashboard's `X-User-Subject` with what onboarding stored. If it differs, onboarding has to bind the subject at first sign-in instead.

Related: [[board]], [[per-user-dashboard]], [[self-serve-onboarding]], [[reonboard-tenant-check]].
