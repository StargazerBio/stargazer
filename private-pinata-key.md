---
title: private-pinata-key
status: done
priority: normal
created: 2026-10-18
tags:
  - security
pr: 161
---

The org's Pinata key is shared by every user, and any user can read it:
it's in every task pod, every dashboard and every notebook pod, and
anyone who can run a task can declare the org-wide secret. Measured on
2026-10-18 (ticket [[notebook-pinata-key]]): from a notebook with no key in
its environment, a ten-line task declaring the secret got the full key.
Whoever holds it can upload, edit metadata and delete any file on the org's
public Pinata account, shared reference data included.

## Outcome

Every public write on the tenant goes through `stargazer-publisher`, a
Lambda outside Union whose key only its own role can read, and the org's
`PINATA_JWT` is a read key (`org:files:read`). Shipped in Stargazer PR 161
(the publisher client), PR 165 (task images build from their headers, so
an installed release runs its tasks), release `2026.11.18.1`, and infra PR
41 (the Lambda, the dashboard through it, the pin), then rolled out to
`u-pryce` and `u-lily` with `upgrade`. The full key was rotated, the old
one revoked and refused (401). Verified on the tenant as the test account:
pod publishing (P2–P4) and dashboard upload and edit (P6–P7) on the
release, the read key refused every write from a pod, and the pinata tier
on the new key. The 5 March admin uploads owned by
`LilyAdastra`, which isn't a subject, were re-owned to the admin's subject
`391057331988775036` on 2026-11-19 (only `_owner` changed, CIDs and the
demo bundles untouched), so every public file has an owner a dashboard can
act for.

Left:

- The Lambda reads its key once per warm container, so a future rotation
  has to wait for a cold start before revoking (as this one did).

Related: [[board]], [[notebook-pinata-key]], [[org-wide-platform-key]].
