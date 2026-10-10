---
title: Union session cookies reach notebook pods
status: backlog
priority: high
created: 2026-10-05
---

Union forwards the visitor's session cookies to the app. The proxy strips them before
marimo, but code in a pod could still capture a visiting org member's
token. Look for a way to have Union drop them for an app, or isolate the
proxy from notebook code.
