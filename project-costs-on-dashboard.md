---
title: project-costs-on-dashboard
status: later
priority: low
created: 2026-11-21
---

Show each user their own project's share of the tenant's AWS spend on their dashboard, from the daily cost report (ticket [[project-costs-daily]]). The report runs in the `admin` project, which no user can read, so its numbers have to reach each dashboard some other way: written per project where that project's dashboard can read it, or served by something that holds the admin's view and answers each user for their project alone.

Related: [[board]], [[project-costs]], [[project-costs-daily]].
