---
title: One environment declaration per notebook
status: backlog
priority: normal
created: 2026-10-16
---

A notebook declares what its pod runs on in two places, in two formats:

- **System tools** are `main_img`, a Python expression in the setup block,
  which the dashboard evaluates at launch.
- **CPU and memory** are `[tool.stargazer]` TOML in the PEP 723 header. The
  dashboard parses it as text, and the gear edits it.

Both belong to the notebook (decided 2026-10-16), and they should be one
declaration.

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
- **Each notebook gets its own runtime.**
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

Declare both in the setup block as one SDK object, which the dashboard
evaluates the same way it evaluates `main_img` today:

```python
with app.setup:
    import flyte
    from stargazer.notebooks import notebook_base

    main_env = flyte.TaskEnvironment(
        name="my-analysis",
        image=notebook_base.with_apt_packages("bcftools"),
        resources=flyte.Resources(cpu=2, memory="4Gi"),
    )
```

- **The pod uses it.** The dashboard reads `main_env.image` and
  `main_env.resources` for the pod. A notebook without a `main_env` gets the
  standard image and `DEFAULT_RESOURCES`.
- **It carries over to production.** The notebook's own tasks can be
  decorated with `@main_env.task`, so what an analysis needs in production is
  declared once, in the form a production task uses. That's already the
  point of `main_img`; this extends it to resources.
- **The pod becomes the only thing that writes a notebook's code.** The
  `[tool.stargazer]` resources go, and so do the gear's resource fields. The
  environment is edited in the notebook, just as Colab's dialog belongs to
  the notebook. Today the gear rewrites the stored source while a running pod
  holds its own copy, so a later save from the pod overwrites the gear's
  change. That's inferred from the code, not reproduced.

**A smaller alternative** is `main_resources = flyte.Resources(...)` beside
`main_img`. It's the same place and format, but it's two names, and nothing
carries over to tasks.

## Open questions

- [ ] Does building a `TaskEnvironment` in the dashboard process have side
      effects, such as an environment registry or names clashing between
      notebooks? Not checked.
- [ ] A notebook opened from the file explorer runs in the pod it was opened
      in, on that pod's environment. This was measured locally (ticket
      `notebooks-as-assets`). Colab avoids it by giving each notebook its own
      runtime. Accept it and document it, or show the pod's environment in
      the notebook?

## Pieces (once the proposal is agreed)

- [ ] Find and evaluate `main_env` in `app/notebook_image.py`, the way
      `main_img` is found and evaluated. Tests:
  - a notebook declaring `cpu=2, memory="4Gi"` and an apt package →
    `per_notebook_env` gets that image and those resources
  - no declaration → the standard image and `DEFAULT_RESOURCES`
  - an expression that raises → a 422, as `main_img` gives today
- [ ] Remove the `[tool.stargazer]` resources, `main_img`, and the gear's
      resource fields.
- [ ] The workspace template declares a `main_env`.
- [ ] Docs:
  - `docs/architecture/notebook.md`: Notebook Environment
  - `docs/architecture/app.md`: "Resources live in the notebook" and
    "So does the image"
  - `.opencode/reference/architecture/app_internals.md`: the `main_img` and
    per-notebook resources sections
- [ ] Verify on Union with the `union-main-img` feature, and check the pod's
      cgroup limits against the declared resources.
