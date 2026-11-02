---
title: internal-address-auth
status: done
priority: high
created: 2026-10-06
pr: 51
---

Every app answers at `http://<app>.<project>-<domain>.svc.cluster.local` with no login and no
identity headers; a task pod in the same project reached a
`requires_auth=True` app that way (measured, [[asset-storage-index|plan 27]] Piece 0). Untested:
whether pods in other projects can reach it, and whether a forged
`X-User-Subject` sent there gets through the dashboard's owner check. If
both hold, code in any pod can act as any user on their dashboard. One fix
is to verify the signed `X-User-Token` ID token instead of trusting
`X-User-Subject`; another is per-namespace network policy.

## Measured (2026-10-18)

Before the fix, from a task in `flytesnacks` sending forged `X-User-Subject`,
`X-User-Claim-Email` and `X-User-Token` to apps in `u-pryce`:

- **Echo app:** an echo app (`hdr-probe`) received all three headers
  unchanged. Pods in other projects reach the address, and nothing rewrites
  what they send.
- **Dashboard:** the test account's dashboard served its home page and the
  owner's private asset list (200) (run `u8knfxlzj8pwx2f5g4ps`). Any non-empty
  subject would have done, since `current_user` keyed every visitor to the
  owner.
- **Notebook:** a notebook pod served marimo's editor page (200) (run
  `uzj7qjnrxf4868sbbdgq`). Its kernel runs with `--no-token`.

Through the public address with the CLI, Union overwrote a forged
`X-User-Subject`. `X-User-Token` was `Bearer` plus an RS256 JWT from
`https://signin.us-west-2.unionai.cloud`, whose `sub` equals the subject and
whose `kid` is among the keys at `/oauth/v2/keys`.

## Fix

On Union, identity is the signed token alone: its signature (the issuer's
published keys), its issuer and its expiry are checked, and the subject is
its `sub`. The visitor must be the owner, or one of `STARGAZER_ADMIN_SUBJECTS`,
a new deploy setting. Without it, an org admin with their own valid token
would get every dashboard on the in-cluster address too, where Union's
project check never runs.

- The dashboard checks in `app.identity`.
- Notebook pods check in the proxy's `_TokenGate`, on every HTTP and
  websocket request.
- `/index/*` stays open: tasks and notebooks call it with no token. It goes
  away with ticket [[dsql-asset-index]].

## Verified (2026-10-18, PR #51)

Test dashboard deployed from `1875752`, my subject in
`STARGAZER_ADMIN_SUBJECTS`:

- **Forged headers from `flytesnacks`:** 401 on the dashboard home, the
  private assets, the notebook page and `/__sg__/ready`.
- **A genuine Union token belonging to someone else**, the platform key's
  subject minted in a pod: 403 on both. Union's public gate refused it
  outright (302).
- **Admin CLI token on the public address:** home 200, launch 200, the
  terminal opens.
- **Chrome as the test account:** dashboard 200, private assets 200,
  notebook cells loaded, the terminal ran a command.

## Outcome

Merged as PR #51 (2026-10-19). On Union the dashboard and notebook pods take
identity from Union's signed token alone, and admit the owner or a subject in
`STARGAZER_ADMIN_SUBJECTS`. Verified on the tenant as above: forged headers
from another project get 401, someone else's genuine token gets 403, and the
owner and an admin get through. Left: `/index/*` is still open on the
in-cluster address until ticket [[dsql-asset-index]] removes it, and code in any
pod can still act in any project with the org key (ticket
[[org-wide-platform-key]]).

Related: [[board]].
