---
title: notebook-environment
status: done
priority: normal
created: 2026-10-16
pr: 79
---

A notebook declares what its pod runs on in two places, in two formats:

- **System tools** are `main_img`, a Python expression in the setup block,
  which the dashboard evaluates at launch.
- **CPU and memory** are `[tool.stargazer]` TOML in the PEP 723 header. The
  dashboard parses it as text, and the gear edits it.

Both belong to the notebook (decided 2026-10-16), and they should be one
declaration. The pod is a Flyte app, and the dashboard already serves it as
a `flyte.app.AppEnvironment` (`per_notebook_env` in `app/per_notebook.py`,
then `serve`). So the declaration is that same object, written in the
notebook.

## How Colab does it

Checked 2026-10-16.

- **One dialog sets both.** Runtime → Change runtime type picks the hardware
  (CPU, a GPU or TPU type, high RAM) and the runtime version. The runtime
  version is a dated image that Colab manages, such as 2026.04, and past
  versions stay available for a year.
  ([runtime version FAQ](https://research.google.com/colaboratory/runtime-version-faq.html))
- **Both are saved with the notebook.** Google says a runtime version can be
  frozen at the notebook level
  ([blog](https://developers.googleblog.com/google-colab-adds-more-back-to-school-improvements/)).
  From memory, not checked: the hardware choice is saved in the `.ipynb`
  metadata.
- **Users don't build images.** Packages beyond the image are
  `pip install`ed in cells, every session.
- **Each notebook gets its own runtime, and there's no notebook picker inside
  one.** The Files panel shows the runtime's own disk (`/content`), not your
  notebooks, which live in Drive. You open a notebook through File → Open
  notebook. Colab Enterprise's docs say several notebooks can share a
  runtime, but recommend against it: the notebooks split its compute and can
  change each other's state
  ([docs](https://docs.cloud.google.com/colab/docs/manage-runtimes)).
- **Colab Enterprise moves hardware out of the notebook** into runtime
  templates an admin defines: machine type, accelerators, disk, network
  ([docs](https://docs.cloud.google.com/colab/docs/runtimes)). A secondary
  source says it has no custom images.

In Stargazer terms:

- Colab's runtime version is our `notebook-app` image release.
- `main_img` goes further than Colab does, since a notebook can add system
  tools.
- The PEP 723 header is Colab's pip cell, kept with the notebook.
- Colab's runtime type is our resources.

## Proposal

**The notebook declares an `AppEnvironment` in its setup block.** It's built
from a `notebook_env` that `stargazer.notebooks` provides beside
`notebook_base`:

```python
with app.setup:
    import flyte
    from stargazer.notebooks import notebook_base, notebook_env

    main_env = notebook_env.clone_with(
        name="my-analysis",
        image=notebook_base.with_apt_packages("bcftools"),
        resources=flyte.Resources(cpu=2, memory="4Gi"),
    )
```

**At launch the dashboard puts its own fields on top and serves the result.**
It evaluates `main_env` the way it evaluates `main_img` today, then calls
`main_env.clone_with(...)` (`AppEnvironment.clone_with` in flyte 2.10.7) with
the fields it owns, and serves the clone. A notebook without a `main_env`
gets `notebook_env`, which means the standard image and `DEFAULT_RESOURCES`.

| Field | Owner | Why |
|---|---|---|
| `image` | notebook | Must be built on `notebook_base`, which has the proxy, the launch script and the tools. The dashboard checks this, as it does today. |
| `resources` | notebook | |
| `env_vars` | both | The notebook's entries are kept. The dashboard's entries win on a clash. |
| `name` | dashboard | `nb-<slug>-<mode>`, which tile state and cleanup find apps by. |
| `args`, `port` | dashboard | The launch script, the mode picked on the tile, the notebook's path, and the proxy's port. |
| `requires_auth` | dashboard | Always `True`: the platform login is the pod's only access control. |
| `domain` | dashboard | The notebook-named URL. |
| the owner's env vars | dashboard | Owner, index URL, store root and org belong to whoever launches the notebook, not whoever wrote it. That decides it once public notebooks exist (ticket [[public-notebooks]]). |
| `scaling` | dashboard for now | `(0, 1)` replicas, 30 minutes to scale down. A notebook could own `scaledown_after` later. |

**Why an `AppEnvironment` and not a `TaskEnvironment`.** An earlier draft of
this ticket used a `TaskEnvironment`, so the notebook's own tasks could reuse
it with `@main_env.task`. But tasks belong in the SDK, where each gets an
environment in `config.py`, and the pod isn't a task. An `AppEnvironment` is
the real type of the pod, and it's the object `serve` already takes.

**The gear stops editing code.** The `[tool.stargazer]` resources go, and so
do the gear's resource fields. The environment is edited in the notebook,
just as Colab's dialog belongs to the notebook. That leaves the pod as the
only thing that writes a notebook's code. Today the gear rewrites the stored
source while a running pod holds its own copy, so a later save from the pod
overwrites the gear's change. That's inferred from the code, not reproduced.

Overtaken 2026-10-21, before this ticket started: commit `1e93fd5` (riding on
PR #67) moved the resources into the setup block as `main_resources` and made
the gear an editor on the whole setup block. So `[tool.stargazer]` and the
gear's resource fields were already gone, and the gear stays a setup-block
editor here: its save now evaluates `main_env` as launch does. The race with a
running pod's save is unchanged and still unreproduced.

**One notebook per pod** (dropped in review, 2026-10-22: other notebooks
open in the pod and run in its environment, as the docs say). The proxy refuses a kernel session for any
notebook other than the one the pod was launched for, and sends the user to
launch that notebook from the dashboard, on its own pod. That matches Colab,
and it keeps the declaration true: a notebook always runs on its own
environment. Importing a sibling notebook still works, since it runs as code
in the launched notebook's kernel, not as a session. All the files stay
visible in the explorer.

## Known from the flyte source (2.10.7, read, not run)

- **`AppEnvironment.clone_with`** takes `name`, `image`, `resources`,
  `env_vars`, `args`, `port`, `requires_auth`, `scaling`, `domain` and the
  rest. So the dashboard's layer is one call.
- **Building an environment registers it.** Every `Environment` appends
  itself to the global `_ENVIRONMENT_REGISTRY` in `__post_init__`. So every
  launch would add two environments to the dashboard process's registry: the
  evaluated declaration and its clone. Find out whether `serve` reads the
  registry. Either way, remove both after serving, so a long-lived dashboard
  doesn't keep growing it.
- **An environment records the file it was declared in**
  (`_declaring_file`). The clone is built inside `app/per_notebook.py`, as
  the environment is today, so serving should see the same file. Inferred.

## Open questions

- [x] **Which requests open a notebook from the explorer?** Both. Measured
      on marimo 0.23.6 (2026-10-21), launched on `alpha.py`: `/?file=beta.py`
      opened beta.py in the same server, and its page then opens
      `/ws?session_id=…&file=…`. Edit mode adds any `file` to its allowlist
      (`SessionManager.create_session` → `register_allowed_path`); run mode
      keeps a fixed one. The launched notebook's own page and socket carry no
      `file`. The frontend builds `?file=<encoded path>` for "Open notebook",
      and `?file=__new__<id>` for a new notebook.
- [ ] **Should a notebook own `scaledown_after`?** Leave it with the
      dashboard until a notebook needs it.

## Pieces (once the proposal is agreed)

- [x] `notebook_env` in `stargazer.notebooks`, beside `notebook_base`.
- [x] Find and evaluate `main_env` in `app/notebook_image.py`, the way
      `main_img` is found and evaluated, and layer the dashboard's fields in
      `per_notebook_env`. Tests:
  - a notebook declaring `cpu=2, memory="4Gi"` and an apt package → the
    served environment has that image and those resources, and the
    dashboard's name, args and `requires_auth=True`
  - a declaration with `requires_auth=False` → served with `True`
  - a declaration whose `env_vars` include `SG_OWNER_SUBJECT` → served with
    the launcher's value
  - no declaration → the standard image and `DEFAULT_RESOURCES`
  - an expression that raises, or an image not built on `notebook_base` →
    a 422, as `main_img` gives today
  - the registry is the same size before and after a launch
- [x] The proxy refuses sessions for other notebooks and links to the
      dashboard. Test it against marimo's real requests, once the first open
      question is answered.
- [x] Remove the `[tool.stargazer]` resources, `main_img`, and the gear's
      resource fields. The workspace template declares a `main_env`.
- [x] Docs:
  - `docs/architecture/notebook.md`: Notebook Environment
  - `docs/architecture/app.md`: "Resources live in the notebook" and
    "So does the image"
  - `.opencode/reference/architecture/app_internals.md`: the `main_img` and
    per-notebook resources sections
- [x] Verify on Union with the `union-main-img` feature. Check the pod's
      cgroup limits against the declared resources, and check that opening a
      second notebook from the explorer sends you to the dashboard.

## Progress

Branch `feat/notebook-environment`, worktree `.claude/worktrees/notebook-environment`.

- `5544c68` `main_env`: `notebook_env` and the default resources in
  `stargazer.notebooks`; `app/notebook_environment.py` (renamed from
  `notebook_image.py`) finds and evaluates it, and `forget_new_environments`
  takes what a launch or gear save registered back out of flyte's registry
  (only the CLI reads it, not `serve`). `per_notebook_env(declared=…)` clones
  the declaration with the dashboard's fields; fields it doesn't set (pod
  template, service account, interruptible, timeouts) pass through. An image
  with no layers of its own serves as the prebuilt one, so sizing a pod works
  on the devbox. Both templates declare a `main_env`.
- `802cd02` one notebook per pod: the dashboard sets `SG_NOTEBOOK_PATH`, and
  the proxy's `_OneNotebook` (inside the token gate) answers a request whose
  `file` names another notebook, or `__new__…`, with a 409 page linking the
  dashboard, or closes its websocket. Measured locally with the real proxy in
  front of marimo 0.23.6 in Chrome: the refusal page for `?file=beta.py`, both
  `beta.py` sockets refused before marimo, the launched notebook's socket
  accepted.
- `9801642` docs, and the verify-stargazer feature renamed `union-main-env`.
- Unit tier: 553 passed.
- Union, 2026-10-21, `u-pryce` with the dashboard deployed from `9801642`: a
  Basic-template notebook built `notebook-custom-cc5b5552…` (run
  `u6zxzm27jzptvdngsrvb`), and section 0 read `bcftools → /usr/bin/bcftools`.
  The spec requested CPU 2, MEMORY 4Gi and EPHEMERAL_STORAGE 20Gi; the Edit
  pod's `cpu.max` was `200000 100000` and `memory.max` was `4294967296`. The
  Edit relaunch reused the image, with no new build. `?file=limit-probe-…py`
  in the Edit pod showed the dashboard page, and its link landed on the
  dashboard. A gear save of a `main_env` with an undefined name returned a
  400, with the block unchanged. Everything was torn down afterwards.
- Rebased onto #78 (DSQL switchover) as `c41fc33`. Conflicts: two docstrings
  and the launch's `index_url` argument. Unit tier: 533 passed. Re-checking it
  on Union was cut short: another session (`feat/tus-public-uploads`)
  redeployed the shared test dashboard from its own branch minutes after my
  redeploy. Only my notebook app was stopped, and that session's dashboard
  was left running. Not re-run, per the user.
- In review as PR #79.
- Review (2026-10-22): don't enforce one notebook per pod; marimo opening
  other notebooks is fine, and a line in the docs says they run in the
  launched notebook's environment. `7c28e90` reverts the proxy refusal and
  `SG_NOTEBOOK_PATH` and adds that line. Unit tier: 521 passed.

## Outcome

Shipped in PR #79 (merge `f978578`). A notebook declares its pod as `main_env`, an `AppEnvironment` cloned from `stargazer.notebooks.notebook_env`. The dashboard evaluates it at launch and in the gear's save, clones it with the fields it owns, and takes both environments back out of flyte's registry. `main_img` and `main_resources` are gone. Review dropped the one-notebook-per-pod refusal (`7c28e90`): other notebooks open in the pod and run in its environment, as `docs/architecture/notebook.md` says.

Verified on Union with the test account from `9801642`: a custom image with `bcftools` built and served, and the Edit pod's cgroup limits matching the declared 2 CPU and 4Gi. Unit tier 521 after the review commit. The rebased branch wasn't re-run on Union, per the user.

Left: the race between a gear save and a running pod's save (ticket [[gear-save-race]]). Whether a notebook should own `scaledown_after` stays open until one needs it.

## Verification recipe: Notebook-declared environments on Union

A workspace notebook that sets `main_env` in its setup block launches in that environment: on its image, with its resources. The basic workspace template declares one (2 CPUs, 4Gi, `bcftools` in the image), so a notebook created from it exercises the whole path. The first launch after an image change waits while Union's remote builder builds the image (the tile spins), then the notebook opens with the declared tools on its PATH. A relaunch reuses the built image. This runs on the Union tenant as the test account, because only Union has an image builder.

### Sub-features

- `main-env-build` builds the declared image on the first launch and serves the notebook on it.
- `main-env-kernel` gives the notebook's kernel a `notebook_base` on the deployed notebook image and a `notebook_env` to clone.
- `main-env-resources` gives the pod the declared CPU and memory, and the default disk.
- `main-env-reuse` serves a stopped notebook again on the same image, with no build.

### How to get to it (user POV)

- On the dashboard, create a notebook from **Basic** and launch it. Its section 0 shows where `bcftools` resolves.
- Or open any workspace notebook's gear and edit `main_env` in its setup block (`notebook_env.clone_with(name=..., image=notebook_base.with_apt_packages("<package>"), resources=flyte.Resources(...))`), then launch it again.

### Driving it

Driven through the test account's dashboard in Chrome (Claude in Chrome), with a helper script for deploying, checking and tearing down.

Preconditions:

- `.flyte/union.yaml` is linked into the checkout, and the Flyte CLI is signed in as an org admin.
- Chrome is signed in to GitHub as the test account. Sign in to the console (`https://stargazerbio.us-west-2.unionai.cloud/v2`) with its **Continue with Github (Stargazer Bio)** button, then open app URLs from that page with `location.href`; a direct navigate through the login redirect lands in the wrong tab.
- Export `STARGAZER_TARGET=union` for every `union_dashboard.py` call.

Steps:

- **Deploy.** With the tenant's `STARGAZER_WORKSPACE_ROOT` and `STARGAZER_DSQL_CLUSTER_ARN` exported (from infra's `tenant.env`), `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy` redeploys only the test account's dashboard from the checkout and prints its URL.
- **Create.** In the dashboard's create tile, type a name not used before (an existing one is refused), choose **Basic**, and click **Create**. A tile for it appears in Workspace.
- **Launch.** Click **Run** on that tile by its coordinates. On the first launch of a template notebook since the last deploy, it spins through the build and the deploy (about a minute for one apt package), then shows **Open: Run Mode** and **Stop**. Open it: section 0 reads `bcftools → /usr/bin/bcftools`. This covers `main-env-build`.
- **Check.** `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py check nb-<slug>-run`: the served image is `…:notebook-custom-<hash>`, the requests are the declared `CPU` and `MEMORY` with the default `EPHEMERAL_STORAGE` (the spec carries no limits; Union applies the requests as limits, which the Resources step shows), the pod's `STARGAZER_NOTEBOOK_IMAGE` is the deployed `…:notebook-app-<hash>`, and the newest run is a succeeded `build-image` (or no new run, when another notebook already built the same declaration on this base). This covers `main-env-kernel` together with section 0 rendering at all, since the setup block imports `notebook_base` and `notebook_env`.
- **Resources.** Launch the same notebook in **Edit**, open the dropdown terminal (Ctrl+`) and run `cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max`: the CPU quota over its period is the declared CPUs, and the memory is the declared limit in bytes. This covers `main-env-resources`.
- **Reuse.** Click **Stop**, then **Run** again. `check` shows the same served image and no new `build-image` run. This covers `main-env-reuse`.
- **Teardown.** `uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py teardown` stops the notebook's app and the dashboard and prints `live runs: []`.
- **Proof.** Keep section 0's text from the launch and the `check` output from the launch and the reuse. The created notebook stays in the test account's workspace; delete it from its tile if you want it gone.

### Gotchas

- `stargazer-users upgrade` redeploys every user's dashboard. Use `union_dashboard.py deploy`, which deploys only the test account's.
- Clicking tile buttons by element reference (`ref_…`) can fail to submit; click by coordinates from a screenshot.
- A failed launch raises a browser alert, which blocks Claude in Chrome. Cover the failure cases with `tests/unit/test_notebook_environment.py` and `tests/unit/test_app.py`, or call `/launch` with `fetch` from the dashboard page and read the JSON.
- A workspace notebook is a copy of the template at creation, so a template change needs a newly created notebook to show up.

Related: [[board]].
