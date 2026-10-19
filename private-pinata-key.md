---
title: Keep the org's Pinata key out of user code
status: maybe
priority: normal
created: 2026-10-18
---

The org's Pinata key is shared by every user, and any user can read it:
it's in every task pod, every dashboard and every notebook pod, and
anyone who can run a task can declare the org-wide secret. Measured on
2026-10-18 (ticket `notebook-pinata-key`): from a notebook with no key in
its environment, a ten-line task declaring the secret got the full key.
Whoever holds it can upload, edit metadata and delete any file on the org's
public Pinata account, shared reference data included.

Keeping it private would mean only the dashboard holds it:

- Tasks and notebooks lose it. Public reads go through the dashboard's
  public listing, and downloads use the gateway, which needs no key.
- Publishing goes through the dashboard: its own uploads, and Pinata
  signed URLs it mints, as the asset page does now.
- No user code runs in the dashboard. Today it evaluates a notebook's
  `main_img` there (`app/notebook_image.py`), so that would move or go.
- A user who can run tasks must not be able to declare the secret. It's
  org-wide today, so this needs Union to scope it, or a project-scoped
  secret only the dashboards' project can mount. Unchecked.

Related: `org-wide-platform-key` (the platform key in every pod) and
`per-user-storage-isolation` (one IAM role for every project).
