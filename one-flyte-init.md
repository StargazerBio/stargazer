---
title: one-flyte-init
status: maybe
priority: low
created: 2026-11-16
---

Two pieces of code exist once in each repo, kept alike by hand (read 2026-11-16):

- **Flyte init.** `stargazer.config.init_flyte()` and infra's `app/init.py` both branch on `_U_EP_OVERRIDE` and call `flyte.init_in_cluster(org=…, project=…, domain=…)` from the same variables. Infra's adds an API-key branch for the deployer and takes a config path.
- **The login token check.** `runtime/proxy.py` (`_jwks_client`, `_signing_key`, `_refusal`) and infra's `app/identity.py` (`_jwks_client`, `_signing_key`, `_token_subject`) are the same code, to the comments.

## Plan

- [ ] `init_flyte()` takes an optional config path, and infra's `init()` calls it for the in-cluster and config-file branches, keeping only its API-key branch. The bundle-root `chdir` in `init_flyte()` must not change what a dashboard pod bundles: check a notebook launch on the devbox before and after.
- [ ] The token check: the proxy imports no Stargazer code by design, so it can't take it from the package as things stand. Settle whether a small `stargazer.auth` module that both import is worth giving the proxy that one import, or whether two copies with a comment naming each other is the honest answer.

Related: [[board]], [[internal-address-auth]].
