---
title: Launching a notebook whose image takes minutes to build
status: backlog
priority: low
created: 2026-10-22
---

A notebook that declares its own image in `main_env` is built on Union's
remote builder while `/launch` waits. One apt package builds in about a
minute, but a bioconda layer could take several, and nobody has measured
what happens when the build outlasts the dashboard's request timeout (and
Cloudflare's in front of it). Measure a long build's launch end to end. If
the request dies first, the launch should return while the build continues
and the tile should pick the notebook up when it's served, the way a
hydrated Open does.
