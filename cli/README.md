# Stargazer CLI Tools

Maintenance scripts. Run them from the repo root.

## upload_to_pinata.py

Uploads files to Pinata's public network with keyvalue metadata. **Anyone can
read what it uploads**: use it for shared data such as reference genomes and
demo bundles. A user's own files go to the object store through
`Asset.update()` instead.

**Usage:**

```bash
# One file, JSON metadata
uv run python cli/upload_to_pinata.py /path/to/file.fa \
  --metadata '{"asset": "reference", "build": "GRCh38"}'

# key=value metadata (repeat -m)
uv run python cli/upload_to_pinata.py results.vcf \
  -m asset=variants -m sample_id=NA12829

# Several files with the same metadata
uv run python cli/upload_to_pinata.py file1.txt file2.txt \
  --metadata '{"asset": "dataset"}'

# JSON plus key=value (key=value wins on a shared key)
uv run python cli/upload_to_pinata.py data.csv \
  --metadata '{"asset": "dataset"}' -m version=2
```

`asset` names the asset type (`reference`, `alignment`, `variants`, …); the
other keys are that type's fields.

**Options:**

- `files`: one or more files to upload (required)
- `--metadata` / `--keyvalues`: metadata as a JSON object
- `-m KEY=VALUE` / `--meta KEY=VALUE`: one metadata pair; repeatable
- `--update-config`: after each upload, fill that file's empty entry in the
  `CIDS` dict of `--config-path` with its CID
- `--config-path PATH`: the Python file holding `CIDS` (default:
  `tests/utils/test_pinata.py`)

**Requirements:** `PINATA_JWT` set to a Pinata API key, from the
[Pinata dashboard](https://app.pinata.cloud/):

```bash
export PINATA_JWT='your_jwt_token_here'
```

**Example output:**

```
Uploading 1 file(s) to Pinata...

Uploading: tests/fixtures/general/GRCh38_TP53.fa
  Size: 39,745 bytes
  Metadata: {'asset': 'reference', 'build': 'GRCh38'}
  Success!
    CID: bafkreib6vj3os7l4lqqytaw5vju46iorcknttfiwfnlbizjcqn7xd5hrvy

============================================================
Upload Summary: 1/1 files uploaded
============================================================
```

### Adding a test fixture's CID

`tests/utils/test_pinata.py` keeps the CIDs Pinata assigned to the fixture
files. To add one, put an empty entry in its `CIDS` dict
(`"new_fixture.fa": "",`), then upload with `--update-config`:

```bash
uv run python cli/upload_to_pinata.py tests/fixtures/general/new_fixture.fa \
  -m asset=reference --update-config
```

An entry that already has a CID is left alone, and the script prints the line
to add by hand.

## devbox-setup.sh

Applies the cluster-side workarounds the local Flyte devbox needs: the storage
signed-URL endpoint, the serving domain, and a CoreDNS wildcard. They're lost
whenever the `flyte-devbox` container is recreated, so re-run it after every
fresh devbox. It's safe to re-run.

```bash
cli/devbox-setup.sh [--dry-run] [--laptop] [--verify-pod] [--domain D]
```

`--laptop` also applies the macOS-side DNS change (needs sudo); without it,
the script prints the commands. `--help` prints the full description. Each
step's rationale is in
[`.opencode/reference/devbox_workarounds.md`](../.opencode/reference/devbox_workarounds.md).

## devbox_dashboard.py

Deploys a dashboard on the devbox, after `devbox-setup.sh`. The devbox has no
Union users or login, so it's one dashboard in the default project for a
stand-in user, `devbox-user`, storing under the devbox's bucket. It holds a
port-forward to the devbox's object store open while it uploads, and refuses
to run unless `STARGAZER_TARGET=devbox` (the default).

```bash
uv run --all-extras python cli/devbox_dashboard.py
```

It prints the dashboard's URL. What each setting is for, and how to send runs'
assets to it:
[`.opencode/reference/devbox_workarounds.md`](../.opencode/reference/devbox_workarounds.md)
→ Devbox dashboard.

## docker_task_tests.py

Runs the GATK and alignment task tests in `gatk_env`'s image, locally in
docker. They skip without `gatk`, `bwa` and `samtools` on your PATH; this
builds that image into your local docker (x86_64, like Union; never pushed)
and runs pytest in it, with the repo mounted. On Apple silicon it runs under
emulation. Source changes need no
rebuild. The run fails if any of those tools is missing from the image, so the
tests can't pass by skipping. Needs docker, not the devbox.

```bash
uv run python cli/docker_task_tests.py [pytest args...]
```

With no arguments it runs `tests/tasks/gatk` and `tests/tasks/general`. It
exits with pytest's exit code. The first build takes a minute or so from a
warm cache; later runs start in seconds. The scRNA tests don't belong here:
they need the `bio` extra, which this image doesn't carry, and they run
locally.
