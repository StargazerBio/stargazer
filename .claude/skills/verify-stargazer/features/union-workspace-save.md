# Saving the workspace on Union

Everything a user keeps in a notebook's workspace is there the next time they open one: the notebooks, and any other file at its path, folders included. A file deleted in the workspace stays deleted. A file over 100 MB isn't saved; the notebook page shows a banner naming it, with a cell that stores it as an asset instead. Pods save every 5 seconds and once more when they stop. This runs on the Union tenant as the test account, because only Union has the bucket and the pods' shutdown path.

## Sub-features

- `workspace-save-shutdown` saves the workspace when the pod gets SIGTERM. Checking it on its own needs the interval at 0, which nothing sets until ticket `dashboard-settings`. It was checked that way on 2026-10-18 (ticket `save-whole-workspace`), with a deploy setting since removed.
- `workspace-save-files` saves and restores files in folders at their paths, and leaves out dotfiles, `__marimo__/` and `__pycache__/`.
- `workspace-save-deletes` deletes from the store a file deleted in the workspace.
- `workspace-save-interval` saves while the pod runs, every 5 seconds.
- `workspace-save-big-files` leaves files over 100 MB out, names them in the banner, and the banner's cell stores one as an asset.

## How to get to it (user POV)

- Open any workspace notebook from the dashboard. In the dropdown terminal (Ctrl+`), write files under `/workspace`, delete some, or make one over 100 MB. Close the notebook with **Stop** on its tile, then open it again.
- The banner appears in the notebook's bottom right within 10 seconds of a file passing 100 MB.

## Driving it

Driven from the shell with `scripts/union_pod.py`, which reaches the dashboard and the pods as the CLI's signed-in user, and runs commands through the pod's own terminal. The banner is checked once in Chrome as the test account.

Preconditions:

- `.flyte/union.yaml` is linked into the checkout, and the Flyte CLI is signed in as an org admin.
- Export `STARGAZER_TARGET=union` for every `union_dashboard.py` call.

Steps:

- **Deploy.** `STARGAZER_WORKSPACE_ROOT=s3://union-us-west-2-stargazerbio/stargazer STARGAZER_STORE_REGION=us-west-2 uv run --all-extras python .claude/skills/verify-stargazer/scripts/union_dashboard.py deploy`. A change to the proxy or its HTML rebuilds the notebook image first (several minutes).
- **Launch.** `union_pod.py create "<new name>"`, then `union_pod.py launch <slug>` and `union_pod.py ready <url>`.
- **Write.** `union_pod.py sh <url> '<command>'` to write `data/counts.csv`, `data/old.csv` and `lib/helpers.py`, append a line to the notebook, and add `.env`, `__marimo__/c.json` and `truncate -s 150M data/big.bin`. Wait 10 seconds, then `union_pod.py store <url>`: the edited notebook and the three files are there, and `.env`, `__marimo__/` and `data/big.bin` aren't. `union_pod.py status <url>` lists `data/big.bin`. This covers `workspace-save-interval`.
- **Stop and reopen.** `union_pod.py stop <slug>`, wait 45 seconds so the old pod's shutdown save finishes before the new pod loads, then launch and wait again. `sh <url> 'find /workspace -type f'` shows the edited notebook and the three files at their paths. `store` lists exactly those four. This covers `workspace-save-files`.
- **Delete.** In the new pod, `rm /workspace/data/old.csv`, stop, wait, reopen: `old.csv` is gone from the pod and from `store`. This covers `workspace-save-deletes`.
- **Big file.** Write a file over 100 MB, open the notebook in Chrome as the test account (sign in to the console with **Continue with Github (Stargazer Bio)**, then set `location.href` to the pod's URL), and read the banner. Then run the banner's cell in the pod's kernel environment: the kernel runs in marimo's sandbox venv, `/home/flyte/.cache/uv/builds-v0/.tmp*/bin/python` (find it under `/proc/*/cmdline`), with the cell inside `asyncio.run`. It prints the stored asset's `s3://…/assets/<cid>/<name>`, and `default_client.query({"asset": …})` returns its row. This covers `workspace-save-big-files`.
- **Teardown.** `union_dashboard.py teardown` stops the notebook's app and the dashboard and prints `live runs: []`.

## Gotchas

- The login shell's `python` has no `flyte`; the base image's Python, which the proxy runs on, is `/opt/venv/bin/python`.
- A relaunch straight after Stop can hydrate before the old pod's shutdown save lands. Wait 45 seconds between them.
- A launch straight after a redeploy can reach the old dashboard revision, and its pod gets that revision's settings. `union_dashboard.py check dashboard` prints the dashboard pod's `STARGAZER_NOTEBOOK_IMAGE`; launch once it names the image the deploy just built.
- Keep probe notebook names short (`ivl`, not `interval probe 20261018-180932`). A long name is created but never launches, and `launch` answers 503 "still starting" indefinitely (ticket `long-notebook-names`).
- The files the check writes stay in the test account's workspace and show up in its later pods. Delete them from a pod's terminal if they get in the way.
