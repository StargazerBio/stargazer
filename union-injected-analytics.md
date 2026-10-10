---
title: Union injects third-party analytics into app pages
status: backlog
priority: high
created: 2026-10-06
---

Every page our apps serve picks up Heap, Userflow, Reo, Google Analytics (via `/cexr/`)
and Cloudflare scripts at Union's edge; Heap's beacon carries the
visitor's subject. Those scripts run on the dashboard and likely on
notebook pages too, where they can read whatever the page shows. Ask
Union whether apps can opt out.
