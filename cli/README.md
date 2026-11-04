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
pixi run python cli/upload_to_pinata.py /path/to/file.fa \
  --metadata '{"asset": "reference", "build": "GRCh38"}'

# key=value metadata (repeat -m)
pixi run python cli/upload_to_pinata.py results.vcf \
  -m asset=variants -m sample_id=NA12829

# Several files with the same metadata
pixi run python cli/upload_to_pinata.py file1.txt file2.txt \
  --metadata '{"asset": "dataset"}'

# JSON plus key=value (key=value wins on a shared key)
pixi run python cli/upload_to_pinata.py data.csv \
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
  `tests/pinata/test_client.py`)

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

`tests/pinata/test_client.py` keeps the CIDs Pinata assigned to the fixture
files. To add one, put an empty entry in its `CIDS` dict
(`"new_fixture.fa": "",`), then upload with `--update-config`:

```bash
pixi run python cli/upload_to_pinata.py tests/fixtures/general/new_fixture.fa \
  -m asset=reference --update-config
```

An entry that already has a CID is left alone, and the script prints the line
to add by hand.

## lock_envs.py

Locks each task environment: the header of each `env.py` under
`src/stargazer/` (a domain's, and the core one) into the `env.py.pixi.lock`
beside it, which the image's `pixi install --locked` installs. It locks the
pixi manifest Flyte renders from the header, with the pixi version Flyte's
image builder runs, fetched from conda-forge by `pixi exec`, since a newer
pixi's lock (`pixi lock --script`) is one the builder refuses. Run it after
changing a header.

```bash
pixi run python cli/lock_envs.py [--check] [--update] [env.py ...]
```

With no paths it locks every environment. The existing lock is kept where the
header still allows it; `--update` solves from scratch. `--check` changes
nothing and exits 1 if a lock is out of date, as the pre-commit hook does when
a header or lock changes.

## docker_task_tests.py

Runs the tasks test tier: `tests/tasks`, each domain's tests in the image
its tasks run in (`IMAGES` in the script): `gatk/` and `general/` in
`gatk_env`'s, which carries gatk, bwa, bwa-mem2 and samtools, and `scrna/` in
`scrna_env`'s. This builds each image into your local docker as a task pod
gets it (x86_64 like Union, emulated on Apple silicon; never pushed) and runs
pytest in it against the stargazer the image installs. Only `tests/` and
`pyproject.toml` are mounted, so a source change builds the images again
first. Needs docker, not the devbox.

```bash
pixi run python cli/docker_task_tests.py [paths or -k EXPR]
```

With no arguments it runs every test under `tests/tasks`; paths or `-k` pick
a subset. The tests are collected in the dev environment, which has no
domain's packages (a test imports them inside its body), and their IDs passed
to pytest in each container. It exits 0 when every image's run passes, otherwise with the
first failing run's pytest exit code.


## diagrams.sh

Draws import graphs with [pydeps](https://github.com/thebjorn/pydeps) into
`diagrams/`, which is gitignored. Draw them when you need them; don't commit
them. It runs in pixi's `diagrams` environment: pydeps, and pygraphviz, whose
wheels bundle Graphviz, so nothing is installed outside pixi.

```bash
cli/diagrams.sh                                                     # the standard set
cli/diagrams.sh src/stargazer/server.py src/stargazer/registry.py  # one diagram per module
```

The standard set is `sdk.svg` (the SDK by package, the layers at a glance) and
`sdk-modules.svg` (every SDK module). Given module files, it draws each one with everything it
imports, directly or not, as `diagrams/<module>.svg`
(`diagrams/stargazer.server.svg`). It takes files rather than directories,
because pydeps given a subpackage draws the whole package around it. Arrows
point from importer to imported. The options every diagram shares are under
`[tool.pydeps]` in `pyproject.toml`. The standard set takes about a minute
with every extra installed.

## wiki_lint.py

Checks the agent wiki in `.claude/context/` (see the `wiki` skill) and prints one
line per problem: a `[[wikilink]]` or `#heading` that doesn't resolve, a page
missing from `index.md`, a raw source no page cites, a path in a page's
`sources` that doesn't exist, two files with the same name, or a page with a
`status` property, which would put it on the ticket board. The tickets in
`planning/` share its directory, so only their names are checked. It also warns,
without failing, about each page whose `sources` name a file the branch
changes (against its merge base with `origin/main`) while leaving the page
alone. Pre-commit runs it on every commit.

```bash
pixi run python cli/wiki_lint.py
```
