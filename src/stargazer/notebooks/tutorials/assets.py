# /// script
# requires-python = ">=3.14"
# dependencies = [
#   "stargazer-bio",
# ]
#
# [tool.uv.sources]
# stargazer-bio = { path = "/stargazer", editable = true }
# ///
"""
### Stargazer asset and types system tutorial.

A guided walkthrough of why typed `Asset` subclasses exist, the three
layers each Asset has (cid, path, fields), defining a new asset class,
and the round-trip from Python object to storage and back.

`SampleSheet` is exported for the later tutorials.

spec: [docs/architecture/types.md](../architecture/types.md)
"""

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")

with app.setup:
    from dataclasses import dataclass, fields
    from typing import ClassVar

    import marimo as mo

    from stargazer.assets.asset import Asset


@app.cell
def _():
    """Intro."""
    mo.md(
        """
        # Stargazer Asset System

        In Stargazer, data knows what it is. Every file is a typed
        `Asset` that carries its identity, its metadata and its links to
        other assets, and together they form the **asset graph**: tasks
        write into it, workflows query it, and anyone who publishes to it
        extends everyone else's.

        This notebook covers what an Asset is, how to add a new kind to
        the graph, and why the graph is worth having. By the end you'll
        have defined a `SampleSheet` asset, uploaded a real CSV through
        it, extended it with a key of your own, and found it again with
        metadata queries.

        The `SampleSheet` you define here is importable — the next three
        tutorials reuse this very class.
        """
    )


@app.cell
def _():
    """Why typed assets exist."""
    mo.md(
        """
        ## Why typed assets?

        Classic bioinformatics pipelines pass file *paths* between
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
        dataclass that carries (a) the content's identity, (b) where
        the stored file lives, and (c) typed metadata fields, including
        links to related assets. Tasks accept and return Assets, not
        strings. Metadata travels with the file, and the asset graph it
        builds is queryable.
        """
    )


@app.cell
def _():
    """The three layers of an Asset."""
    mo.md(
        """
        ## 1. Anatomy of an Asset

        Every Asset has three layers:

        - **`cid`** — a content identifier. Same bytes anywhere → same
          CID. This is the asset's *identity*, independent of where it
          physically lives. CIDs are IPFS hashes (`bafk…` / `bafy…`).
        - **`path`** — where the stored file lives, set by `update()`.
          `fetch()` downloads it and returns the local path, so a
          workflow can refer to data before it has been downloaded.
        - **Typed dataclass fields** — `sample_id`, `organism`,
          `stage`, … whatever the asset type needs. These get
          serialized to a flat `dict[str, str]` for storage via
          `to_keyvalues()` and reconstituted via `from_keyvalues()`.

        Together these let workflows refer to data by *what it is and
        where it came from*, not by where it happens to sit on disk.
        """
    )


@app.cell
def _():
    """Aside — content addressing and IPFS."""
    mo.md(
        """
        ### Aside: content addressing and IPFS

        A CID is a hash of the bytes. Same bytes anywhere → same CID;
        different bytes → different CID. Always. Stargazer computes the
        real **IPFS** hash (`bafy…`) for every file, locally or on a
        hosted deploy alike — so an asset uploaded by you and by a
        colleague resolves to the same identity, and a file published
        publicly is fetchable from any IPFS node that holds the bytes.

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
          handle doesn't care whether the bytes live on local disk,
          in a cloud bucket, or on a stranger's IPFS node. `fetch()`
          resolves it the same way every time.

        This is why Stargazer assets carry `cid` separately from
        `path`: identity travels with the asset; the location is
        materialized lazily.
        """
    )


@app.cell
def _():
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


@app.cell
def _():
    """Section 2 — define a new asset."""
    mo.md(
        """
        ## 2. Define a new asset

        Time to add one. We'll create `SampleSheet` — a CSV mapping
        samples to per-sample metadata for a cohort. In real code this
        would live in `src/stargazer/assets/sample_sheet.py`; here we
        define it as a top-level class right in the notebook (the
        `@app.class_definition` decorator below) so the later tutorials
        can `import` it.

        The template is always the same:

        1. `@dataclass` subclass of `Asset`
        2. `_asset_key: ClassVar[str] = "<unique key>"`
        3. Typed fields with defaults

        Defaults are required because every field becomes optional in
        `from_keyvalues()` — older records may not have newer fields.
        """
    )


@app.class_definition
@dataclass
class SampleSheet(Asset):
    """CSV of per-sample metadata for a cohort."""

    _asset_key: ClassVar[str] = "sample_sheet"
    cohort_id: str = ""
    n_samples: int = 0
    organism: str = ""


@app.cell
def _():
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


@app.cell
def _():
    """Section 3 — round-trip metadata."""
    mo.md(
        """
        ## 3. Round-trip the metadata

        Storage only deals in flat `dict[str, str]` metadata.
        `to_keyvalues()` is the boundary
        function: `str` fields pass through; everything else gets
        `json.dumps`'d. `from_keyvalues()` does the inverse.
        """
    )


@app.cell
def _():
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
def _(sheet):
    """Round-trip via from_keyvalues()."""
    _kv = sheet.to_keyvalues()
    rehydrated = SampleSheet.from_keyvalues(_kv)
    return (rehydrated,)


@app.cell
def _(rehydrated, sheet):
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


@app.cell
def _():
    """Section 4 — persist to storage."""
    mo.md(
        """
        ## 4. Persist via `update()`

        `Asset.update(path, **kwargs)` is the canonical "write this to
        storage" call:

        1. Sets any field kwargs on the asset
        2. Works out the file's content ID (`cid`) from its bytes
        3. Uploads the file to your storage (a folder on this machine
           by default, the cloud bucket on a hosted deploy) and records
           the asset's metadata so it can be found later
        4. Sets `self.cid`, and `self.path` to the stored file

        We'll write a tiny CSV to a temp file and push it through.
        """
    )


@app.cell
async def _():
    """Write a CSV and upload it as a SampleSheet."""
    import csv
    import tempfile
    from pathlib import Path

    _tmpdir = Path(tempfile.mkdtemp(prefix="stargazer_assets_"))
    csv_path = _tmpdir / "demo_cohort.csv"
    with csv_path.open("w", newline="") as _fh:
        _w = csv.writer(_fh)
        _w.writerow(["sample_id", "organism", "tissue"])
        _w.writerow(["s1d1", "human", "PBMC"])
        _w.writerow(["s1d3", "human", "PBMC"])

    uploaded_sheet = SampleSheet()
    await uploaded_sheet.update(
        path=csv_path,
        cohort_id="assets_demo",
        n_samples=2,
        organism="human",
    )

    mo.md(
        f"""
        Wrote `{csv_path.name}` to a temp dir and called
        `update()`. The asset now has both an identity and a location:

        - `uploaded_sheet.cid` → `{uploaded_sheet.cid}`
        - `uploaded_sheet.path` → `{uploaded_sheet.path.path}`
        - `uploaded_sheet.cohort_id` → `{uploaded_sheet.cohort_id!r}`
        - `uploaded_sheet.n_samples` → `{uploaded_sheet.n_samples}`

        The CID is the file's IPFS content ID, computed from its bytes
        alone, so it's the same wherever the file is stored and the same
        ID it keeps if you ever publish it. `path` is where the stored
        copy lives.
        """
    )
    return (uploaded_sheet,)


@app.cell
def _():
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


@app.cell
async def _(uploaded_sheet):
    """Query for our newly uploaded sheet."""
    from stargazer.assets.asset import assemble

    found = await assemble(asset="sample_sheet", cohort_id="assets_demo")
    _hit = next((_a for _a in found if _a.cid == uploaded_sheet.cid), None)

    mo.md(
        f"""
        ```python
        found = await assemble(
            asset="sample_sheet", cohort_id="assets_demo"
        )
        ```

        - Returned `{len(found)}` asset(s)
        - Each is a `{type(_hit).__name__ if _hit else "—"}` (note: a
          real subclass, not a generic `Asset`) — that's `specialize()`
          using the registry to pick the right Python class.
        - `found[0].cid == uploaded_sheet.cid` → **{_hit is not None}**
        - `isinstance(found[0], SampleSheet)` → **{isinstance(_hit, SampleSheet) if _hit else False}**

        From this point a downstream task can take the `SampleSheet`
        as a typed argument and call `await sheet.fetch()`, which
        downloads the file and returns its local path.
        """
    )


@app.cell
def _():
    """Section 6 — companion pattern."""
    mo.md(
        """
        ## 6. The companion pattern

        Many bioinformatics files come in pairs: BAM + BAI, FASTA +
        FAI, BED + index. Stargazer handles this with a convention:

        > A companion asset stores the parent's CID in `companion_of`.
        > `parent.fetch()` finds the assets whose `companion_of` is
        > its CID and downloads them too.

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
            companion_of: str = ""   # ← the Reference's CID
        ```

        When you call `await ref.fetch()`, the base implementation
        does:

        1. Download the FASTA itself
        2. Find every asset whose `companion_of` is `ref.cid`: yours,
           in your storage or published, and the public ones from
           whoever published the reference
        3. Download every match into the same folder
        4. Return the FASTA's local path

        So the BAI lands next to the BAM, the FAI next to the FASTA,
        without each task having to know about the pairing. Yours come
        first, and the publisher's fill in only the files you don't
        have. Anyone else's public companions are never taken.

        A `<parent>_cid` field is a different link: it records which
        asset this one was made from, and
        `assemble(sample_sheet_cid=sheet.cid)` finds it. The
        `CohortSummary` in the next tutorial records its `SampleSheet`
        that way. It's an output, not a file a tool needs beside the
        sheet, so `sheet.fetch()` leaves it behind.

        These two links are the edges of the asset graph: `companion_of`
        means *belongs beside*, and `<parent>_cid` means *made from*.
        """
    )


@app.cell
def _():
    """Section 7 — extend the graph with your own keys."""
    mo.md(
        """
        ## 7. Extend the graph

        The graph grows with your work. Any asset can carry keys its
        type doesn't declare, its *extras*, and they're queryable like
        declared fields. `SampleSheet` has no `lab` field, but a sheet
        can still be tagged with one:

        ```python
        sheet = SampleSheet()
        sheet.keyvalues["lab"] = "tutorial_lab"
        await sheet.update(path, cohort_id="extras_demo", ...)

        await assemble(asset="sample_sheet", lab="tutorial_lab")
        ```

        A typo in a *declared* field still fails loudly
        (`sheet.cohrt_id = ...` raises `AttributeError`), so extras add
        flexibility without giving up the typed fields.
        """
    )


@app.cell
async def _():
    """Tag a new SampleSheet with an extra key and query on it."""
    import tempfile as _tempfile
    from pathlib import Path as _Path

    from stargazer.assets.asset import assemble as _assemble

    _csv = _Path(_tempfile.mkdtemp(prefix="stargazer_extras_")) / "extras.csv"
    _csv.write_text("sample_id,organism,tissue\ns2d1,mouse,liver\n")

    tagged_sheet = SampleSheet()
    tagged_sheet.keyvalues["lab"] = "tutorial_lab"
    await tagged_sheet.update(
        path=_csv, cohort_id="extras_demo", n_samples=1, organism="mouse"
    )

    _found = await _assemble(asset="sample_sheet", lab="tutorial_lab")
    _hit = next((_a for _a in _found if _a.cid == tagged_sheet.cid), None)

    mo.md(
        f"""
        - `tagged_sheet.keyvalues` → `{tagged_sheet.keyvalues}`
        - `assemble(asset="sample_sheet", lab="tutorial_lab")` found it →
          **{_hit is not None}**, still a
          `{type(_hit).__name__ if _hit else "—"}`, with
          `cohort_id` `{_hit.cohort_id if _hit else "—"!r}` and
          `lab` `{_hit.keyvalues.get("lab") if _hit else "—"!r}`

        Two more ways the graph stays open:

        - **Files no type describes yet.** A bare `Asset` holds
          free-form metadata. Define a matching type later and those
          records come back as that type on the next query.
        - **Types that change.** Every field has a default, so records
          written before a field existed still load.
        """
    )
    return (tagged_sheet,)


@app.cell
def _():
    """Section 8 — why the asset graph pays off."""
    mo.md(
        """
        ## 8. Why the asset graph pays off

        Working alone on one machine, you could glob a folder and read
        the file. The asset graph earns its keep in two places where
        that stops working: compute that moves, and work that's shared.

        **Compute that moves.** Flyte runs each task in its own
        container, scattered **geographically** (no shared filesystem
        with the task that made its inputs) and **temporally** (a retry,
        a re-run a year later or a parameter sweep all land on fresh
        containers with empty disks). There *is* no shared path. A
        container finds its inputs by asking the graph for "the asset
        with these properties" with `assemble()`, and the BAI lands next
        to the BAM everywhere because of `companion_of`. The
        **Execution** tutorial runs identical code on a remote cluster,
        with inputs resolved by CID and no paths to line up.

        **Work that's shared.** The same property lets people build on
        each other's work. A workflow asks the graph for
        `build="GRCh38"`, and any reference published with that metadata
        answers it, whoever uploaded it and wherever its bytes sit.
        Their outputs link back to it by CID, and your name stays on it
        as its owner. Nobody agrees on folder layouts, file names or a
        hand-off first: that's **collaboration without coordination**.

        Locally the graph is a folder and an index file on this
        machine; on a hosted deploy it's a cloud bucket and your
        dashboard's asset explorer, which draws it. Same API either way.
        """
    )


@app.cell
def _():
    """Section 9 — recap."""
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
        | `companion_of` and `<parent>_cid` | The asset graph's edges: belongs beside, made from |
        | Extras in `keyvalues` | Your own queryable keys on any asset |

        That's the whole asset graph.

        ### → Next: `tasks.py`

        The follow-on notebook **imports the `SampleSheet` you defined
        here** and wraps a Flyte task around it. From there the arc is:

        1. **Tasks** — define one task over typed assets.
        2. **Workflows** — compose tasks into a fan-out workflow.
        3. **Execution** — the same code on a remote cluster, no changes.

        Each tutorial imports the previous one's objects, so the whole
        sequence runs on a single shared `SampleSheet`. Open `tasks.py`
        next.
        """
    )


if __name__ == "__main__":
    app.run()
