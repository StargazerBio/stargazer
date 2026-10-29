---
title: dashboard-pinata-key
status: done
priority: high
created: 2026-10-17
pr: 40
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

Branch `feat/dashboard-pinata-key`.

- [x] Declare the secret on the dashboard's `AppEnvironment`
      (`secrets=STARGAZER_SECRETS`). No unit test: it's one argument, and
      the check is the deploy below.
- [x] **The asset page goes public-only** (decided 2026-10-17). With the
      org's shared key on every dashboard, Pinata's private network would
      keep nothing private between users. The Private tab and the network
      choice in the upload form go, and every route answers a network other
      than public with a 400. Private assets come back on the user's own
      store in `asset-manager-on-index`, which also drops the client's
      `network` parameter. Tests in `tests/unit/test_assets_routes.py`:
      private list, sign, update and download → 400 with nothing sent to
      Pinata; signing defaults to public; the signed-in page has the upload
      panel, no Private tab and no private option. All seven failed before
      the change, for the missing behavior.
- [x] The "isn't available yet" state stays for a dashboard with no key (a
      local `uvicorn`, or the devbox, which drops app secrets).
- [x] Docs: `.opencode/reference/devbox_workarounds.md` (the drop is the
      devbox's, Union injects), `.opencode/reference/architecture/app_internals.md`,
      `docs/architecture/app.md`, `docs/architecture/configuration.md`, and
      the `PinataClient` docstrings.
- [x] Verified on Union, 2026-10-17 (below).

## Verified on Union (2026-10-17)

The test account's dashboard, redeployed from the branch (`37dfeeb`) with
`union_dashboard.py deploy`. Before: its spec had no `PINATA_JWT` and no
secrets, so the asset routes 503.

- The app record has one secret reference, `PINATA_JWT`, and no
  `PINATA_JWT` env var. Neither the key nor any 40-character slice of it is
  in the record.
- `GET /assets/list` → 200 with the six public records (anndata,
  known_sites, r1, r2, reference). `network=private` on list and download →
  400, "Only public assets are available here."
- In Chrome as the test account: the asset page shows the Public tab, the
  graph of the six records, and the upload panel, which says "Uploads are
  public: anyone on the internet can browse them." A custom `verify_probe`
  upload from the form → "Uploaded ✓", then on Pinata's public network as
  `bafkreidir322j53anwo7wmt3c4ak4narsw4uhvi3wmd65kpwwfw3zaqpiy`, `_owner` the
  test account's subject, nothing on the private network. Deleted from
  Pinata straight after.
- Torn down: the dashboard stopped, no active apps or live runs in `u-pryce`
  or `flytesnacks` (where the image built).

## Related tickets

- `public-notebooks`: reading the public tier on hosted dashboards was its
  open problem. This solves it.
- `asset-manager-on-index`: the Public tab works on hosted dashboards.
- `tus-browser-uploads`: public uploads go through the dashboard too.
- `publish-asset`: Publish can run on the dashboard.

## Outcome

Merged as PR #40 (2026-10-18). Hosted dashboards declare `PINATA_JWT` as a
Flyte secret and have the public tier: the asset page lists and uploads to
Pinata's public network. The page is public-only, and every route refuses
another network with a 400. A follow-up commit on the PR corrected the docs
that said the dashboard holds no secrets, which is how `main_img`'s eval of
the owner's code was justified: its one secret is the org key the owner can
already read from any task. Verified on the test account's dashboard (above).

Left: `PinataClient`'s unused `network` parameter and `_get_signed_url`, and
a Private tab on the user's own store, both in `asset-manager-on-index`.
