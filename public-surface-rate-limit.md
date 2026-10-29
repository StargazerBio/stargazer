---
title: public-surface-rate-limit
status: maybe
priority: low
created: 2026-10-22
---

The asset browser's public listing, schema and downloads answer anonymous
requests. The listing comes from an in-process cache refreshed at most once a
minute, and downloads redirect to the account's dedicated gateway, which
meters bandwidth, so heavy anonymous traffic costs gateway bandwidth rather
than Pinata API calls. Nothing limits how often one client asks. Decide
whether a per-client limit is worth adding before the dashboards are opened
more widely.
