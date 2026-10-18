---
title: Dashboards get the Pinata key as a secret
status: doing
priority: high
created: 2026-10-17
---

The dashboard declares `secrets=[flyte.Secret(key="PINATA_JWT",
as_env_var="PINATA_JWT")]` on its `AppEnvironment` in `app/admin_app.py`, so
hosted dashboards have the public tier: the asset page's Public tab, public
uploads, publishing, and reading public notebooks (decided 2026-10-17).

## Why

- **The key was kept off dashboards because a user can read their own
  dashboard's app spec.** That was about baking it into `env_vars`, the only
  way the devbox allows (`.opencode/reference/devbox_workarounds.md`,
  "`AppEnvironment(secrets=[...])` is silently dropped").
- **Union injects app secrets, and the value stays out of the app record**
  (measured 2026-10-17, below).
- **Users can already reach the key.** `PINATA_JWT` is an org-wide secret on
  Union, and every task environment declares it (`STARGAZER_SECRETS` in
  `src/stargazer/config.py`). A user can run a task from their notebook that
  declares it and print it. Inferred, not tried. Notebook pods themselves
  don't carry it: none of the five `nb-*` apps in `u-pryce` has it in its spec
  (measured 2026-10-17).

## Measured (2026-10-17)

A throwaway app, `secret-probe`, in `u-pryce`, on the dashboard's image,
declaring the secret as above with `requires_auth=True`. It answered a
bearer-token request with only the key's length and the first 8 hex digits of
its SHA-256.

- The key reached the pod as `PINATA_JWT`: 687 characters, hash prefix
  `93946e8f`, both matching the key in the local `.env`.
- The app record holds only a reference (`key: "PINATA_JWT"`,
  `mount_requirement: ENV_VAR`). Neither the value nor any 40-character slice
  of it appears in it.
- The app was deactivated and deleted straight after.

## Pieces

- [ ] Declare the secret on the dashboard's `AppEnvironment`. No test: it's
      one argument, and the check is the deploy below.
- [ ] The asset page's "isn't available yet" state stays for a dashboard with
      no key (a local `uvicorn`, or the devbox, which drops app secrets).
- [ ] Docs:
  - `.opencode/reference/devbox_workarounds.md`: the app-secrets entry says
    the drop is "reproducible on any cluster". It's the devbox's
    flyte-binary; Union injects them. Say so, and drop "The app tier bakes
    no secrets today" in favour of what the dashboard declares.
  - `.opencode/reference/architecture/app_internals.md`: "Off on hosted
    dashboards" goes.
  - `docs/architecture/app.md` and `docs/architecture/configuration.md`,
    wherever they say hosted dashboards have no public tier.
- [ ] Verify on Union: redeploy the test account's dashboard, then on its
      asset page list the Public tab and upload a small public file. Stop
      the dashboard after.

## Related tickets

- `public-notebooks`: reading the public tier on hosted dashboards was its
  open problem. This solves it.
- `asset-manager-on-index`: the Public tab works on hosted dashboards.
- `tus-browser-uploads`: public uploads go through the dashboard too.
- `publish-asset`: Publish can run on the dashboard.
