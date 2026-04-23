"""
### Stargazer asset and types system tutorial.

A guided walkthrough of why typed `Asset` subclasses exist, the three
layers each Asset has (cid, path, fields), defining a new asset class,
and the round-trip from Python object to storage and back.

spec: [docs/architecture/types.md](../../docs/architecture/types.md)
"""

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    """Imports and Flyte init."""
    import asyncio
    import csv
    import tempfile
    from dataclasses import dataclass, fields
    from pathlib import Path
    from typing import ClassVar

    import marimo as mo
    import flyte

    flyte.init_from_config()

    mo.md(
        """
        # Stargazer Asset System

        A walkthrough of *why* Stargazer wraps every file in a typed
        `Asset`, what an Asset actually is, and how to add a new one to
        the system. By the end of this notebook you'll have defined a
        `SampleSheet` asset, uploaded a real CSV through it, and
        rediscovered it via a metadata query.
        """
    )
    return ClassVar, Path, asyncio, csv, dataclass, fields, mo, tempfile


@app.cell
def _(mo):
    """Why typed assets exist."""
    mo.md(
        """
        ## Why typed assets?

        A naive bioinformatics pipeline passes file *paths* between
        functions:

        ```python
        bam = align(fastq_path)
        sorted_bam = sort(bam)
        vcf = call(sorted_bam, ref_path)
        ```

        Fine for one-off scripts; brittle the moment things grow:

        | Pain | Why a path can't help |
        |------|------------------------|
        | "Where did this come from?" | The path tells you *where it lives*, not *what produced it*. |
        | "Show me all alignments for sample X" | Folder conventions only — no querying. |
        | "Did I run this with duplicates marked?" | Lives in someone's notes, not the file. |
        | "Where are the companion files?" | A BAM and its `.bai` are conceptually one thing but two paths. |

        Stargazer's answer: every file is an `Asset` — a small
        dataclass that carries (a) the content's identity, (b) the
        local path once fetched, and (c) typed metadata fields. Tasks
        accept and return Assets, not strings. Metadata travels with
        the file in storage and the storage layer is queryable.
        """
    )
    return


@app.cell
def _(mo):
    """The three layers of an Asset."""
    mo.md(
        """
        ## 1. Anatomy of an Asset

        Every Asset has three layers:

        - **`cid`** — a content identifier. Same bytes anywhere → same
          CID. This is the asset's *identity*, independent of where it
          physically lives. Local CIDs look like `local_<md5>`; remote
          (Pinata/IPFS) ones are `bafy...` hashes.
        - **`path`** — the local filesystem path, set after `fetch()` or
          `update()`. Decoupled from `cid` so a workflow can refer to
          data before it has been downloaded.
        - **Typed dataclass fields** — `sample_id`, `organism`,
          `stage`, … whatever the asset type needs. These get
          serialized to a flat `dict[str, str]` for storage via
          `to_keyvalues()` and reconstituted via `from_keyvalues()`.

        Together these let workflows refer to data by *what it is and
        where it came from*, not by where it happens to sit on disk.
        """
    )
    return


@app.cell
def _(mo):
    """Aside — content addressing and IPFS."""
    mo.md(
        """
        ### Aside: content addressing and IPFS

        The CID is what makes the rest of the system work, so it's
        worth a paragraph on *why* content addressing is the right
        primitive here.

        A traditional path answers *where is this file* but not *what
        is this file*. Two paths can hold identical bytes; one path
        can refer to different bytes after a careless edit. Identity
        by location is fragile — links rot, files move, paths collide.

        A CID is a hash of the bytes. Same bytes anywhere → same CID;
        different bytes → different CID. Always. Stargazer issues
        `local_<md5>` CIDs when running locally (indexed in TinyDB on your machine)
        and real **IPFS** hashes (`bafy…`) when `PINATA_JWT` is set —
        so an asset uploaded by you and by a colleague resolves to the
        same identity and can be fetched from any IPFS node that holds
        the bytes, including the public gateway.

        That tiny shift unlocks four things at once:

        - **Immutability** — a CID never points at "the latest" of
          anything. If the bytes change, the CID changes. No version
          drift hides under a stable name.
        - **Dedup** — re-uploading identical bytes is a no-op. Two
          workflows that produce the same intermediate share storage,
          and downstream tasks get a cache hit.
        - **Reproducibility** — record the input and output CIDs of a
          run once, and you can replay the pipeline on the *exact*
          same bytes months later regardless of where they're hosted.
        - **Location-independence** — a `Reference(cid="bafy…")`
          handle doesn't care whether the bytes live on your laptop,
          in Pinata, or on a stranger's IPFS node. `fetch()` resolves
          it the same way every time.

        This is why Stargazer assets carry `cid` separately from
        `path`: identity travels with the asset; the location is
        materialized lazily.
        """
    )
    return


@app.cell
def _(fields, mo):
    """Inspect an existing Asset class to ground the abstraction."""
    from stargazer.assets.scrna import AnnData

    _rows = [
        {
            "field": _f.name,
            "type": getattr(_f.type, "__name__", str(_f.type)),
            "default": repr(_f.default),
        }
        for _f in fields(AnnData)
    ]
    mo.vstack(
        [
            mo.md(
                """
                ### A real example: `AnnData`

                Here is the scRNA-seq asset declaration as it lives in
                `src/stargazer/assets/scrna.py`:

                ```python
                @dataclass
                class AnnData(Asset):
                    _asset_key: ClassVar[str] = "anndata"
                    sample_id: str = ""
                    n_obs: int = 0
                    n_vars: int = 0
                    stage: str = ""
                    organism: str = ""
                    source_cid: str = ""
                ```

                And here are its fields as Python's `dataclasses` sees
                them — note that `cid` and `path` come from the `Asset`
                base class, while everything else is `AnnData`-specific:
                """
            ),
            mo.ui.table(_rows, selection=None),
        ]
    )
    return


@app.cell
def _(mo):
    """Why _asset_key is special."""
    mo.md(
        """
        The `_asset_key` `ClassVar` is the load-bearing piece:

        - **Auto-registration.** `Asset.__init_subclass__` adds the
          class to `Asset._registry` (a `dict[str, type[Asset]]`)
          keyed by `_asset_key`. No manual registration needed.
          This is mainly important for the MCP server.
        - **Storage tag.** `to_keyvalues()` writes `"asset":
          "<_asset_key>"` so storage records know their type.
        - **Specialization.** When `assemble()` queries storage, it
          gets back generic records; `specialize(record)` looks up
          `_asset_key` in the registry to rebuild the correct subclass.
        - **Companion linking.** Related files (e.g. an index for a
          BAM) reference their parent via `<_asset_key>_cid`
          keyvalues. `fetch()` follows those links automatically.
        """
    )
    return


@app.cell
def _(mo):
    """Section 2 — define a new asset."""
    mo.md(
        """
        ## 2. Define a new asset

        Time to add one. We'll create `SampleSheet` — a CSV mapping
        samples to per-sample metadata for a cohort. In real code this
        would live in `src/stargazer/assets/sample_sheet.py`; here we
        define it inline so we can poke at it.

        The template is always the same:

        1. `@dataclass` subclass of `Asset`
        2. `_asset_key: ClassVar[str] = "<unique key>"`
        3. Typed fields with defaults

        Defaults are required because every field becomes optional in
        `from_keyvalues()` — older records may not have newer fields.
        """
    )
    return


@app.cell
def _(ClassVar, dataclass):
    """Define SampleSheet by subclassing Asset."""
    from stargazer.assets.asset import Asset

    @dataclass
    class SampleSheet(Asset):
        """CSV of per-sample metadata for a cohort."""

        _asset_key: ClassVar[str] = "sample_sheet"
        cohort_id: str = ""
        n_samples: int = 0
        organism: str = ""

    return (SampleSheet,)


@app.cell
def _(SampleSheet, mo):
    """Confirm the new asset registered itself."""
    from stargazer.assets import ASSET_REGISTRY

    _registered = SampleSheet._asset_key in ASSET_REGISTRY
    _resolved = ASSET_REGISTRY.get(SampleSheet._asset_key)
    mo.md(
        f"""
        Just by defining the class, `__init_subclass__` ran and
        registered it:

        - `SampleSheet._asset_key` → `"{SampleSheet._asset_key}"`
        - `"{SampleSheet._asset_key}" in ASSET_REGISTRY` → **{_registered}**
        - `ASSET_REGISTRY["{SampleSheet._asset_key}"]` → `{_resolved.__name__ if _resolved else None}`

        That registration is what lets `assemble()` rebuild the right
        Python type from a flat storage record later.
        """
    )
    return


@app.cell
def _(mo):
    """Section 3 — round-trip metadata."""
    mo.md(
        """
        ## 3. Round-trip the metadata

        Storage backends (TinyDB locally, Pinata remotely) only deal in
        flat `dict[str, str]`. `to_keyvalues()` is the boundary
        function: `str` fields pass through; everything else gets
        `json.dumps`'d. `from_keyvalues()` does the inverse.
        """
    )
    return


@app.cell
def _(SampleSheet, mo):
    """Show to_keyvalues() output."""
    sheet = SampleSheet(cohort_id="demo_cohort", n_samples=12, organism="human")
    _kv = sheet.to_keyvalues()

    mo.vstack(
        [
            mo.md(
                """
                Construct an instance with normal Python types:

                ```python
                sheet = SampleSheet(
                    cohort_id="demo_cohort", n_samples=12, organism="human"
                )
                ```

                `sheet.to_keyvalues()` flattens it for storage. Notice
                `n_samples` (an `int`) becomes the JSON-encoded string
                `"12"`, while the strings pass through untouched:
                """
            ),
            mo.ui.table(
                [{"key": _k, "value": _v} for _k, _v in _kv.items()],
                selection=None,
            ),
        ]
    )
    return (sheet,)


@app.cell
def _(SampleSheet, sheet):
    """Round-trip via from_keyvalues()."""
    _kv = sheet.to_keyvalues()
    rehydrated = SampleSheet.from_keyvalues(_kv)
    return (rehydrated,)


@app.cell
def _(mo, rehydrated, sheet):
    """Confirm the round-trip preserves typed values."""
    mo.md(
        f"""
        Going the other direction:

        ```python
        rehydrated = SampleSheet.from_keyvalues(sheet.to_keyvalues())
        ```

        - `rehydrated.cohort_id` → `{rehydrated.cohort_id!r}` (str pass-through)
        - `rehydrated.n_samples` → `{rehydrated.n_samples!r}` ({type(rehydrated.n_samples).__name__}, decoded from JSON)
        - `rehydrated.organism` → `{rehydrated.organism!r}`
        - `rehydrated == sheet` → **{rehydrated == sheet}**

        The coercion happens at the storage boundary so callers always
        see real Python types.
        """
    )
    return


@app.cell
def _(mo):
    """Section 4 — persist to storage."""
    mo.md(
        """
        ## 4. Persist via `update()`

        `Asset.update(path, **kwargs)` is the canonical "write this to
        storage" call:

        1. Sets any field kwargs on the asset
        2. Sets `self.path` to the file you're publishing
        3. Hashes the file contents and uploads to the configured
           backend (local TinyDB by default, Pinata if `PINATA_JWT` is
           set)
        4. Sets `self.cid` to the resulting content ID

        We'll write a tiny CSV to a temp file and push it through.
        """
    )
    return


@app.cell
async def _(Path, SampleSheet, asyncio, csv, mo, tempfile):
    """Write a CSV and upload it as a SampleSheet."""
    _tmpdir = Path(tempfile.mkdtemp(prefix="stargazer_assets_tutorial_"))
    csv_path = _tmpdir / "demo_cohort.csv"
    with csv_path.open("w", newline="") as _fh:
        _w = csv.writer(_fh)
        _w.writerow(["sample_id", "organism", "tissue"])
        _w.writerow(["s1d1", "human", "PBMC"])
        _w.writerow(["s1d3", "human", "PBMC"])

    uploaded_sheet = SampleSheet()
    await uploaded_sheet.update(
        path=csv_path,
        cohort_id="assets_tutorial_demo",
        n_samples=2,
        organism="human",
    )
    # Tiny pause so the spinner has something to show on cached re-runs
    await asyncio.sleep(0)

    mo.md(
        f"""
        Wrote `{csv_path.name}` to a temp dir and called
        `update()`. The asset now has both an identity and a location:

        - `uploaded_sheet.cid` → `{uploaded_sheet.cid}`
        - `uploaded_sheet.path` → `{uploaded_sheet.path}`
        - `uploaded_sheet.cohort_id` → `{uploaded_sheet.cohort_id!r}`
        - `uploaded_sheet.n_samples` → `{uploaded_sheet.n_samples}`

        The CID prefix `local_` tells you this lives in TinyDB on this
        machine. With `PINATA_JWT` set, the same call would push to
        Pinata and return an IPFS-style hash instead.
        """
    )
    return (uploaded_sheet,)


@app.cell
def _(mo):
    """Section 5 — discover via assemble()."""
    mo.md(
        """
        ## 5. Discover with `assemble()`

        `assemble(**filters)` queries storage by keyvalue filters,
        deduplicates by CID, and returns specialized subclass instances
        — the registry from earlier earns its keep here. No file path
        conventions, no folder scanning.
        """
    )
    return


@app.cell
async def _(SampleSheet, mo, uploaded_sheet):
    """Query for our newly uploaded sheet."""
    from stargazer.assets.asset import assemble

    found = await assemble(asset="sample_sheet", cohort_id="assets_tutorial_demo")
    _hit = next((_a for _a in found if _a.cid == uploaded_sheet.cid), None)

    mo.md(
        f"""
        ```python
        found = await assemble(
            asset="sample_sheet", cohort_id="assets_tutorial_demo"
        )
        ```

        - Returned `{len(found)}` asset(s)
        - Each is a `{type(_hit).__name__ if _hit else "—"}` (note: a
          real subclass, not a generic `Asset`) — that's `specialize()`
          using the registry to pick the right Python class.
        - `found[0].cid == uploaded_sheet.cid` → **{_hit is not None}**
        - `isinstance(found[0], SampleSheet)` → **{isinstance(_hit, SampleSheet) if _hit else False}**

        From this point a downstream task can take the `SampleSheet`
        as a typed argument, call `await sheet.fetch()` to pull the
        bytes, and read `sheet.path`.
        """
    )
    return


@app.cell
def _(mo):
    """Section 6 — companion pattern."""
    mo.md(
        """
        ## 6. The companion pattern

        Many bioinformatics files come in pairs: BAM + BAI, FASTA +
        FAI, BED + index. Stargazer handles this with a convention:

        > A companion asset stores `<parent_asset_key>_cid` pointing at
        > the parent's CID. `parent.fetch()` queries for assets where
        > that key matches and downloads them too.

        Real example from `src/stargazer/assets/reference.py`:

        ```python
        @dataclass
        class Reference(Asset):
            _asset_key: ClassVar[str] = "reference"
            build: str = ""

        @dataclass
        class ReferenceIndex(Asset):
            _asset_key: ClassVar[str] = "reference_index"
            build: str = ""
            tool: str = ""
            reference_cid: str = ""   # ← link back to the Reference
        ```

        When you call `await ref.fetch()`, the base implementation
        does:

        1. Download the FASTA itself
        2. `assemble(reference_cid=ref.cid)` to find any companions
        3. Download every match alongside

        So the BAI lands next to the BAM, the FAI next to the FASTA,
        without each task having to know about the pairing.

        For our `SampleSheet` we don't need a companion (it's a single
        file), but if we ever wanted, say, a per-cohort QC report, it
        would carry `sample_sheet_cid` and ride along automatically.
        """
    )
    return


@app.cell
def _(mo):
    """Section 7 — why the indirection is worth it."""
    mo.md(
        """
        ## 7. "Isn't this overkill for a local filesystem?"

        Honest question. On a single laptop with a fixed directory, you
        could skip all of this — glob the right folder, read the file,
        done. `assemble()` is a metadata query against a flat-file
        TinyDB; companion fetching is two steps where one would do.

        The machinery earns its keep the moment compute stops being
        local and persistent. Stargazer tasks run inside Flyte v2,
        which means each one gets its own Docker container, and those
        containers are scattered:

        - **Geographically.** Different machines, often different
          regions. There is no shared filesystem between a task and the
          one that produced its inputs.
        - **Temporally.** A retry lands on a fresh container with an
          empty disk. A workflow re-run a year later resolves inputs
          from cold storage. A parameter sweep spins up dozens of
          containers in parallel that each need the same reference.

        In that world, path-based pipelines stop working: there *is* no
        shared path. The only way for a container to find its inputs is
        to ask the storage layer "give me the asset with these
        properties" — that's `assemble()`. The only way to make sure
        the BAI lands next to the BAM in every container, without each
        task carrying layout knowledge, is the companion convention.

        Content-addressing is the other half of the trick. A container
        in `us-east` can pull the same `bafy…` reference that a
        container in `eu-west` already pinned, with no coordination —
        identical bytes resolve to identical CIDs, and any IPFS node
        that has them can serve them. Caching across runs and
        deduplication across users both fall out for free.

        The local TinyDB mode you're using right now is the same API
        with a one-machine backend. The investment in Asset / CID /
        keyvalues looks like ceremony when you're alone on your laptop
        but it really shines once compute is ephemeral.
        """
    )
    return


@app.cell
def _(mo):
    """Section 8 — recap."""
    mo.md(
        """
        ## Recap

        | Concept | What it gives you |
        |---------|-------------------|
        | `Asset` base + `_asset_key` | A typed, registered, queryable file |
        | `cid` vs `path` | Identity vs location, decoupled |
        | `to_keyvalues()` / `from_keyvalues()` | Round-trip across a flat-string storage boundary |
        | `update(path, **kwargs)` | Single call: set fields, upload, get a CID |
        | `assemble(**filters)` | Discovery by metadata, not folders |
        | Companion pattern via `<key>_cid` | Index/data pairs travel together |

        That's the whole system. The next notebook —
        `tasks_tutorial` — picks up from here, showing how Stargazer
        tasks consume and produce these typed assets, and how those
        tasks compose into Flyte workflows.
        """
    )
    return


if __name__ == "__main__":
    app.run()
