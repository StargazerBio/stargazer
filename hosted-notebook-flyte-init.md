---
title: Hosted notebook kernels never reach the cluster
status: next
priority: high
created: 2026-10-20
blocked_by:
  - notebook-pod-ephemeral-storage
---

In a hosted notebook pod on Union, `flyte.run(...)` from the kernel quietly runs the task inside the pod. The notebooks' setup blocks call `flyte.init_from_config()` (`tutorials/execution.py:38`, `templates/basic.py:49`, `workflows/scrna_pipeline.py:45`). The pod has no Flyte config file, so that call leaves Flyte with no client, and `flyte.run` falls back to an in-process `_InlineRun`. So the Execution tutorial's "Run Remotely" section runs in the pod and shows a local `/tmp/flyte/metadata/...` path as its console URL. The "On the cluster" choice from ticket `local-remote-toggle` (`stargazer.notebooks.ui.dispatch`, which forces `mode="remote"`, merged in #62) fails outright. The MCP server's `flyte.init_from_config()` (`server.py:80`) is inferred to do the same when it runs in a pod.

There are three separate gaps between a hosted kernel and a working cluster run. Only the first one is about init.

1. **No client.** Measured: `flyte.init_in_cluster(org=FLYTE_ORG, project=FLYTE_PROJECT, domain=FLYTE_DOMAIN)` in the kernel gives a working client for the user's project. That's the same call `app/init.py` makes when `_U_EP_OVERRIDE` is set.
2. **No code bundle.** `init_in_cluster` takes its bundle root from the cwd, which is `/workspace`, but SDK and image-baked notebook code lives in `/stargazer/src`. Bundling fails with `CodeBundleError: No files found to bundle in '/workspace'`, before the client is ever called. Measured: run from `/stargazer/src`, the same `init_in_cluster` + `flyte.run` created a run on the cluster.
3. **Wrong task image.** `tutorial_env` declares no image, so the task pod runs stock `ghcr.io/flyteorg/flyte:py3.13-v2.12.0` and fails importing the tutorial module: `ModuleNotFoundError: No module named 'marimo'`. Ticket `notebook-cluster-runs` names the same gap for the template's `my_env`.

## Likely fix

- [ ] One SDK helper for notebook Flyte init, under `src/stargazer/notebooks/` (the SDK can't import `app/`). In a pod (`_U_EP_OVERRIDE` set) it calls `flyte.init_in_cluster(org=FLYTE_ORG, project=FLYTE_PROJECT, domain=FLYTE_DOMAIN)`; elsewhere it calls `flyte.init_from_config()`. The three notebooks' setup blocks call it instead of `flyte.init_from_config()`. The pod already carries every input: `_U_EP_OVERRIDE`, `_UNION_EAGER_API_KEY`, `FLYTE_ORG`, `FLYTE_PROJECT`, `FLYTE_DOMAIN` (measured, below). Consider `server.py` too.
- [ ] A bundle root that covers where the task code lives: `/stargazer/src` for SDK and image-baked notebooks, and `/workspace` for a workspace notebook's own `@app.function` tasks. Only the `/stargazer/src` case is measured. Options (inferred, unmeasured): call `flyte.init_from_api_key(api_key=<injected key>, project=…, domain=…, root_dir=…, image_builder="remote")`, which takes a `root_dir` where `init_in_cluster` doesn't; or `copy_style="none"` for tasks whose image already installs stargazer (`with_uv_project`).
- [ ] Give `tutorial_env` an image that has stargazer and its imports, the way the `config.py` envs use `with_uv_project`.
- [ ] Verify on the real surface: a hosted Execution tutorial, once it can open (ticket `notebook-pod-ephemeral-storage`), shows a real console URL and a succeeded run in the user's project. `dispatch` "On the cluster" does the same from a hosted pod.

A run started this way runs as the pod's platform key, not the user: the measured run's creator is application subject `393067446845621194` (`stargazerbio-EAGER_API_KEY-union-us-west-2`). That's ticket `org-wide-platform-key`.

## Measurements (2026-10-20, test account, project `u-pryce`)

Setup: dashboard deployed with `stargazer-users onboard --email pryce@stargazer.bio` from `main` at `89e637e`. Chrome was signed in as the test account. The Execution tutorial's edit pod was evicted twice before marimo served (ticket `notebook-pod-ephemeral-storage`), so the probe ran in the **Workflows tutorial's edit pod** (`nb-workflows-edit`). Its first added cell makes the same call the Execution setup cell makes. Every reading below comes from **notebook cells in the marimo kernel**, not the terminal overlay.

Cell 1, the Execution tutorial's init plus its inputs:

```python
import flyte

flyte.init_from_config()
sheets = await make_demo_sheets()
# -> sheets: ['demo_alpha', 'demo_beta', 'demo_gamma']
```

Cell 2, config and env as the kernel sees them (secret values replaced by their length):

```
python=/home/flyte/.cache/uv/builds-v0/.tmpziSMUj/bin/python
flyte=2.12.0 cwd=/workspace pid=122 ppid=116
resolve_config_path()=None
exists config.yaml: False
exists .flyte/config.yaml: False
exists ~/.flyte/config.yaml: False
exists ~/.union/config.yaml: False
  AWS_DEFAULT_REGION=us-west-2
  AWS_REGION=us-west-2
  AWS_ROLE_ARN=arn:aws:iam::791359099513:role/union-us-west-2-stargazerbio-userflyterole
  AWS_STS_REGIONAL_ENDPOINTS=regional
  AWS_WEB_IDENTITY_TOKEN_FILE=<set, 55 chars>
  FLYTE_ATTEMPT_NUMBER=0
  FLYTE_DOMAIN=development
  FLYTE_INTERNAL_DOMAIN=development
  FLYTE_INTERNAL_EXECUTION_DOMAIN=development
  FLYTE_INTERNAL_EXECUTION_ID=nb-workflows-edit
  FLYTE_INTERNAL_EXECUTION_PROJECT=u-pryce
  FLYTE_INTERNAL_NAME=nb-workflows-edit
  FLYTE_INTERNAL_PROJECT=u-pryce
  FLYTE_INTERNAL_TASK_DOMAIN=development
  FLYTE_INTERNAL_TASK_NAME=nb-workflows-edit
  FLYTE_INTERNAL_TASK_PROJECT=u-pryce
  FLYTE_INTERNAL_TASK_VERSION=f20b36cd9a2235de5894e0e235d1226b
  FLYTE_INTERNAL_VERSION=f20b36cd9a2235de5894e0e235d1226b
  FLYTE_ORG=stargazerbio
  FLYTE_PROJECT=u-pryce
  FLYTE_SECRETS_ENV_PREFIX=<set, 7 chars>
  HOME=/home/flyte
  HOSTNAME=nb-workflows-edit-00001-deployment-b5fcf9458-nskzb
  SG_ADMIN_SUBJECTS=391057331988775036
  SG_AUTH_ISSUER=https://signin.us-west-2.unionai.cloud
  SG_OWNER_SUBJECT=387300641116005877
  STARGAZER_ADMIN_URL=https://u-pryce.apps.stargazerbio.us-west-2.unionai.cloud
  STARGAZER_INDEX_URL=http://dashboard.u-pryce-development.svc.cluster.local
  STARGAZER_LOCAL=/home/flyte/.stargazer/local
  STARGAZER_NOTEBOOK_IMAGE=791359099513.dkr.ecr.us-west-2.amazonaws.com/union/stargazerbio:notebook-app-495690954aeb79cbb5466b37986b65e3
  STARGAZER_OWNER=387300641116005877
  STARGAZER_STORE_ROOT=s3://union-us-west-2-stargazerbio/stargazer
  STARGAZER_TARGET=union
  STARGAZER_WORKSPACE_ROOT=s3://union-us-west-2-stargazerbio/stargazer
  _F_IMG_ID=ghcr.io/flyteorg/flyte:py3.13-v2.10.7
  _F_PN=nb-workflows-edit-00001-deployment-b5fcf9458-nskzb
  _F_SYS_PATH=./.
  _UNION_EAGER_API_KEY=<set, 164 chars>
  _UNION_PINATA_JWT=<set, 687 chars>
  _U_EP_OVERRIDE=stargazerbio.us-west-2.unionai.cloud
init state after the setup cell's flyte.init_from_config(): {'org': None, 'project': None, 'domain': None, 'root_dir': '/workspace', 'client': None}
```

There's no `FLYTECTL_CONFIG`, `UCTL_CONFIG` or `FLYTE_ADMIN_ENDPOINT`. The pod spec's env names (`kubectl get pod -o jsonpath`, read-only) agree: `_U_EP_OVERRIDE` and `_UNION_EAGER_API_KEY` are injected, and no config path is set.

Cell 3, before any in-cluster init (`summarize_cohort` from the Tasks tutorial, on one sheet):

```
[A] client before: None
[A] flyte.run -> type=_InlineRun name=dry-run url=/tmp/flyte/metadata/738dc5bd-bcd0-469f-ada2-e8bcb5f1a237
[A] outputs: CohortSummary(cid='bafkreif7gpw5k3pjmqzx2aadbhfoqbvytfnxj2yzxhyc2u4jylmdkkhqmq', ..., cohort_id='demo_alpha', n_samples=3, n_organisms=1, ...)
[B] with_runcontext(mode='remote').run raised CodeBundleError: No files found to bundle in '/workspace'.
```

The deployer's run listing for `u-pryce` right after (`Run.listall` against `.flyte/union.yaml`, admin login): no new run. The newest was still `u7lrvnc7fxgf8mzpdt9d`, started 2026-10-20T17:13 UTC.

Cell 4, in-cluster init:

```
[C] init_in_cluster ok: client=ClientSet org=stargazerbio project=u-pryce domain=development root_dir=/workspace
[C] control-plane read, Run.listall -> ['u7lrvnc7fxgf8mzpdt9d', 'urdpj55wqsm25nbs7r5t', 'ucq8npj5zlddknm84wc8']
[D1 cwd=/workspace] flyte.run raised CodeBundleError: No files found to bundle in '/workspace'.
[D2 cwd=/stargazer/src] init_in_cluster ok: client=ClientSet org=stargazerbio project=u-pryce domain=development root_dir=/stargazer/src
[D2 cwd=/stargazer/src] flyte.run -> type=Run name=u2xmf4gdfvr4xltxqhnd url=https://stargazerbio.us-west-2.unionai.cloud/v2/domain/development/project/u-pryce/runs/u2xmf4gdfvr4xltxqhnd
```

The `Run.listall` names match the deployer's listing of `u-pryce`. The deployer sees `u2xmf4gdfvr4xltxqhnd` as the only new run (`tutorial.summarize_cohort`, started 01:06:59 UTC on 10-21, FAILED). It ran on image `ghcr.io/flyteorg/flyte:py3.13-v2.12.0`, and its creator is subject `393067446845621194`. Its log (`flyte get logs`): the bundle had `stargazer/notebooks/tutorials/tasks.py` and the modules it imports, then `File "/home/flyte/./stargazer/notebooks/tutorials/tasks.py", line 26: import marimo` → `ModuleNotFoundError: No module named 'marimo'`.

For comparison, a local run with no config anywhere gives the same shape: `resolve_config_path()=None`, client `None`, `flyte.run` → `_InlineRun` with url `/tmp/flyte/metadata/...`.

Teardown: `nb-workflows-edit`, `nb-execution-edit` and `dashboard` deactivated. Every app in `u-pryce` is STOPPED, `active_runs` is `[]` for `u-pryce` and `flytesnacks`, and `u-pryce-development` has no pods. The probe left three demo `SampleSheet` assets and one `CohortSummary` in the test account's asset store, which is what the Execution tutorial does anyway. The added cells were in the image's copy of the Workflows tutorial, outside `/workspace`, so nothing was saved.
