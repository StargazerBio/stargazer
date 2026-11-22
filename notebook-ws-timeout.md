---
title: notebook-ws-timeout
status: done
priority: high
created: 2026-11-22
pr: 171
---

The marimo terminal in a hosted notebook disappeared while the user was typing (2026-11-22, `nb-crop-gmm-edit` in `u-pryce`). Union serves apps as Knative services, and Knative's queue-proxy cuts every request at the revision's timeout, websockets included: 300 s by default, and the notebook apps (infra `app/per_notebook.py`) set none. Each socket is cut on its own clock, 5 minutes after it opened. The session socket opened at 03:11:43, 03:16:47 and 03:21:51 (queue-proxy logged `Request timeout: 5m0s` at 03:16:43), and marimo reconnects it on its own, showing "session reconnected". The terminal's opened at 03:12:22, 03:17:28 and 03:23:39, each time because the user reopened it after it closed, and those closes didn't follow the reconnects. The pod never restarted. The agent panel's sockets (`/__sg__/agent/<name>`) ride the same timeout.

A longer request timeout only moves the cut: an hour is the most Flyte allows (the tenant's Knative allows 6000 s), and the terminal would still close then. So the connections hand over instead, before the platform cuts them, and the timeout stays at its default (user's call, 2026-11-22). The page reaches marimo and the agents through the pod's proxy (`runtime/proxy.py`), and only the browser's leg is cut.

## Plan

- [x] The proxy keeps each socket's upstream (marimo's socket, an agent's stdio) in a channel named by the page (`__sg_rid`), apart from the browser connection carrying it. A connection naming a channel with `__sg_resume=<K>` takes it over: the proxy waits until it has received the K frames the page sent on the old connection, then sends upstream frames to the new one and closes the old with 4000. A channel with no successor waiting ends when its connection does, as today. Connections that name no channel work as today.
- [x] The page script (today's agent redirect, renamed `sockets.html`) wraps every same-origin websocket. Every 4 minutes it stops sending, opens a successor with the count of frames sent, keeps delivering the old connection's frames until its 4000 close, then delivers the successor's (held until then) and sends what it queued. A successor that fails leaves the old connection in place and retries in 30 s.
- [x] Tests for the handoff against the fake agent; docs (`docs/architecture/runtime.md`).
- [x] On a hosted pod: the terminal, the session and an agent session stay up past 10 minutes, with no "session reconnected", and queue-proxy logs no `Request timeout`. Measured 2026-11-22 on `ghcr.io/stargazerbio/debug:notebook-ws-timeout` (`assets`, edit, `u-pryce`): the same shell from 05:12:40 to 05:23:28 UTC (pid 207, an exported variable kept), an agent socket at the panel's URL answering `initialize` at 05:13:27 and 05:23:13, every socket handed over every four minutes in the pod's log, and no `Request timeout`. The Agents tab wouldn't leave Chat in that notebook, so the agent socket was opened from the page at the panel's URL (`ws://<host>:3017/message`).

Out of scope: a connection dropped by the network, not the platform's timeout, still closes as today.

## Verification recipe

1. `pixi run pytest tests/unit/test_proxy.py`: the handoff tests.
2. Build the branch's image, push it to `ghcr.io/stargazerbio/debug:<tag>`, and deploy the test account's dashboard with it as the notebook image. Launch a notebook in edit mode, open the terminal and the agent panel, and leave them for 10 minutes.
3. The terminal is still open with its shell's history, the agent answers in the same session, and no "session reconnected" appeared. Read-only kubectl (`~/.kube/union`): the pod's queue-proxy logs no `Request timeout`, and its notebook container logs each socket's handoffs every 4 minutes (`WebSocket ... __sg_resume=`).
4. Tear down: deactivate the notebook app and the test account's dashboard.

## Outcome

Shipped in PR 171 (merge `adebe05`): the proxy keeps each socket's upstream in a channel, and `runtime/sockets.html` hands every same-origin socket over to a new connection before the platform's cut. Verified on the tenant on `ghcr.io/stargazerbio/debug:notebook-ws-timeout` (`e4b89096…`): the same shell from 05:12:40 to 05:23:28 UTC, an agent socket answering in one session ten minutes apart, every socket handed over each four minutes, and no `Request timeout`; four handover tests in `tests/unit/test_proxy.py`.

The request timeout was raised to 20 minutes afterwards after all (infra PR 48, ticket notebook-request-timeout), and the handover interval follows it in ticket handover-interval. A connection the network drops still closes as before.

Related: [[board]].
