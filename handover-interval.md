---
title: handover-interval
status: done
priority: normal
created: 2026-11-22
pr: 172
---

The page hands each socket over every four minutes (`ROTATE_MS` in `runtime/sockets.html`), sized for the platform's five-minute default. The notebook pods' request timeout is now 20 minutes (ticket notebook-request-timeout), so the handover moves to every 19 minutes, a minute inside it, which leaves room for one retry after a failed handover. The pod contract in `docs/architecture/runtime.md` asks the pod manager for a request timeout of at least 20 minutes, since a shorter one cuts the sockets before their handover.

## Plan

- [x] `ROTATE_MS` to 19 minutes; the runtime doc and the pod contract.
- [x] On a hosted pod with the 20-minute timeout: a socket handed over at about 19 minutes and still open past 20, with no `Request timeout`. Measured 2026-11-22 on `ghcr.io/stargazerbio/debug:notebook-ws-timeout` (`f6a6c33e…`): the session and agent sockets opened at 19:08:14 UTC, their successors joined the same channels at 19:27:15, and at 19:30:52 none had been opened afresh and queue-proxy had logged no timeout.

## Verification recipe

1. Build the branch's image and push it to `ghcr.io/stargazerbio/debug:<tag>`; deploy the test account's dashboard from infra `main` with it as `STARGAZER_NOTEBOOK_IMAGE`.
2. Launch a notebook in edit mode and open it in the browser; its page has `ROTATE_MS = 19 * 60 * 1000`.
3. After 22 minutes, read-only kubectl (`KUBECONFIG=~/.kube/union`, `-n u-pryce-development`): the notebook container's log shows each socket's successor (`__sg_resume=`) at about 19 minutes and no close of the channel, and queue-proxy logs no timeout.
4. Tear down: `union_dashboard.py teardown`.

## Outcome

Shipped in PR 172 (merge into `main` 2026-11-22): the page hands each socket over every 19 minutes, and the pod contract asks the pod manager for a request timeout of at least 20 minutes. Verified on the tenant on the branch's debug image: the session and agent sockets' successors joined their channels 19 min 1 s after they opened, and past the 20-minute mark none had been opened afresh and queue-proxy had logged no timeout. The PR drew no review comments. Nothing left.

Related: [[board]], [[notebook-ws-timeout]], [[notebook-request-timeout]].
