---
title: Notebooks declare their own app environment
status: doing
priority: normal
created: 2026-10-16
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
| the owner's env vars | dashboard | Owner, index URL, store root and org belong to whoever launches the notebook, not whoever wrote it. That decides it once public notebooks exist (ticket `public-notebooks`). |
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

**One notebook per pod.** The proxy refuses a kernel session for any
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
- [ ] Verify on Union with the `union-main-img` feature. Check the pod's
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
