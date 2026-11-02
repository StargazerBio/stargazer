---
title: production-context-files
status: done
priority: normal
created: 2026-05-19
pr: 63
---

An agent launched from a notebook's terminal overlay opens in the workspace
directory (`app/launch-notebook.sh`), and no context file ships there; the
only condensed copy of the authoring conventions is `marimo.toml`'s `[ai]`
rules (ticket [[marimo-toml]]).

`app/notebook_agent.md` is the one condensed context file, baked into both notebook images at `/home/flyte/.claude/CLAUDE.md`, Claude Code's user-level memory for the `flyte` user they run as (PR #63). It covers where the agent is, marimo's conventions, the task, asset and workflow patterns from `marimo.toml`'s `[ai] rules`, and how runs go local or to the cluster. Verified in a local build of both images and a Union remote build: the file is at that path, readable by `flyte`, `/workspace` untouched, and Claude Code 2.1.153 sends it as user memory (captured with a fake Messages API).

## Outcome

Shipped in PR #63 (merge `956ea36`). `app/notebook_agent.md` is the one condensed context file for agents in a notebook's terminal. Both notebook images bake it as `/workspace/AGENTS.md`, where the terminal starts Claude Code, and pin Claude Code 2.1.304, the first line that reads a folder's `AGENTS.md`. That replaces the `~/.claude/CLAUDE.md` placement described above. Riding along: `marimo.toml` deleted (ticket [[marimo-toml]]), the local image opening on the Assets tutorial with the other notebooks in the file explorer, and a rule in `AGENTS.md` and the test agent against restating configuration in tests.

Verified (measured): the local image and the hosted recipe (built locally, not pushed), each run as `flyte`, have Claude Code 2.1.304 and a `flyte`-owned `/workspace/AGENTS.md` identical to the source. `claude -p` from `/workspace` against a fake Messages API sent it as `Contents of /workspace/AGENTS.md` with default settings. The proxy's own hydrate and sync showed the baked copy isn't saved until edited, and an edited copy wins at the next launch. Unit tier 515 passed.

Left: the new recipe wasn't built on Union's remote builder (the earlier run built the `~/.claude` placement), and the hosted images rebuild at the next `stargazer-users onboard` or `upgrade`. The published `ghcr.io/stargazerbio/stargazer:latest` predates this change and #65's; ticket [[publish-stargazer-image]].

Related: [[board]].
