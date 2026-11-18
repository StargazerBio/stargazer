# Design Choices

The rest of the architecture docs say what Stargazer is. This one says what it was chosen over and what each choice costs, since a design is easier to trust, and to change, when its alternatives are on the page. Mechanics are in the docs linked from each section and aren't repeated here.

## Data

### Metadata over paths

**Files are found by what they are, not where they sit.** A path carries meaning by convention: `NA12878/GRCh38/aligned.bam` says a sample, a build and a stage, and only to people who know the layout. Rename a folder and the meaning is lost without an error; copy the BAM without its `.bai` and a tool fails three steps later. Pipeline frameworks that infer inputs from filename patterns inherit the same fragility, since the pattern is the contract.

Typed keyvalues make the contract explicit and queryable: `assemble(sample_id=..., build=...)` finds data wherever it lives, a workflow takes a question instead of a file list, and a new key is available to queries the moment it's written. Companion links replace the rule that an index sits beside its file.

**Cost:** the discipline moves to whoever writes an asset. An untagged file is hard to find, and a query that matches nothing looks the same as a typo. Types and the task boundary catch the common cases; the rest is convention. See [Types](types.md).

### Content addressing over locations

**An asset's identity is a hash of its bytes.** A location names a place, and what's there can change without the name changing. An S3 key or URL says nothing about whether this week's object is last week's, and a result that cites one can't prove which bytes it came from. A CID can: it commits to the exact content, anyone holding the bytes can check it, and two copies of a reference genome are one asset.

Public availability isn't the difference. A public bucket object is fetchable by anyone too, and usually faster. What differs is that a CID stays valid when the bytes move: between a local disk, a bucket and the public network, the reference to the data doesn't change, and nobody has to be trusted for the bytes to be right.

**Cost:** identity doesn't give durability. A CID with one provider is exactly as available as that provider, and public IPFS retrieval is slower and less predictable than a bucket, especially for large files. A dedicated gateway and the user's own object store carry the speed; the public network carries sharing. See [Configuration](configuration.md#identity-and-layout).

### Provenance in the data

**Lineage is a property of the asset, not of the run that made it.** Every output records the CIDs of what it was made from. Execution logs and orchestrator lineage record the same thing, but they live with the run, the cluster or the vendor, and they don't travel with a file that's shared or moved. A link on the asset does, so a published VCF still leads back to its alignments, reads and reference for someone who never saw the run.

**Cost:** it records inputs, not environment. What ran, with which image and parameters, is in the run's record; the asset says what it was made from and nothing more. See [Types](types.md#companions).

### An index beside the object store

**Bytes go to a store built for bytes and metadata to a database built for queries.** Object stores list by prefix, not by predicate, so "every alignment of NA12878 against this reference" is a scan. An index answers it directly, and it runs the same on a SQLite file locally, Postgres on the devbox and Aurora DSQL on Union. A pinning service's keyvalues can't be the only index, since they're capped, strings only, and exist only for public files.

**Cost:** two systems must agree. Rows are written after their bytes so an index never points at a missing file, but the reverse can leave orphaned bytes, and the index is one more thing to run.

### A public tier on IPFS, opt-in

**Sharing needs a place that no single user owns.** Public references and bundles live on the IPFS network through a pinning service, and each user's own data stays in storage only they can reach. The tier is opt-in so the default is fully private, and since it's the same asset graph, public records join queries without a separate API.

**Cost:** public means public, with no access control to build on. A limit that a user can route around isn't offered, so nothing here pretends otherwise: `_owner` is attribution, not permission. Pinning-service limits (the keyvalue cap on new files) shape what public records can carry.

## Orchestration

### Flyte v2

**The orchestrator is plain Python, so agents and people write the same thing.**

| Alternative | What it gives | Why not |
|-------------|---------------|---------|
| Nextflow, Snakemake | Mature bioinformatics ecosystems, many community pipelines | A DSL beside the code. Snakemake derives its graph from filename patterns, which is the path-as-contract problem again |
| WDL with Cromwell or miniwdl | A portable spec | A separate language and type system to keep in step with the Python around it |
| Airflow, Prefect | General scheduling | Built around fixed, scheduled DAGs, not compute that fans out as data arrives, and without typed task boundaries |

In Flyte v2 a workflow is a task that calls tasks, control flow is `if`, loops and `asyncio.gather`, and types are enforced where tasks meet. The same function runs in a notebook, an IDE or a cluster, and an agent that writes Python writes a workflow with nothing else to learn. See [Workflows](workflows.md).

**Cost:** v2 is new, so its ecosystem is smaller than Nextflow's, and hosted runs depend on Union. The local devbox and a notebook's own process run the same code without it, but a self-hosted production cluster is more to operate than a hosted one.

### A container per task

**Each task declares its own image and resources.** A bioinformatics step is a tool with a pinned version and a memory appetite: a workflow-wide environment makes one tool's upgrade everyone's, and one memory ceiling serves nobody. Per-domain environments keep GATK's pins from constraining scanpy's, and make "what ran" an image tag. See [Configuration → Container Images](configuration.md#container-images).

**Cost:** a first run builds or pulls images, and a tool a task wraps has to be in the right environment's header before the task works.

### One code path from notebook to cluster

**Where a run goes is a switch, not a rewrite.** Exploratory code that must be ported before it can scale gets ported wrongly, or not at all, and results from the two versions differ. Running tasks in the notebook's own process or on a cluster through one call keeps the exploratory version and the production version identical. See [Where Your Code Runs](../guides/where-your-code-runs.md).

**Cost:** a notebook's header has to list what its local runs import, since the cluster's images don't help the kernel.

## Interface

### marimo over Jupyter

**A notebook that is a program can be treated like one.** A marimo notebook is a Python file, so it diffs and reviews in git, imports functions from other notebooks and runs as a script. Its cells form a dependency graph, so state can't depend on execution order, which is how analyses stop reproducing. The same file runs as an app in run mode, which is how an exploratory notebook becomes the front end of a pipeline. Per-notebook sandboxes keep each notebook's dependencies in its own header.

**Cost:** Jupyter is what most users already know, and its tooling and extensions are far larger.

### Agents over a typed registry

**An agent can only be trusted with what it can't get wrong silently.** Free-form shell access to bioinformatics tools produces analyses that nobody can rerun. Stargazer serves its tasks and workflows to agents through an MCP server with typed signatures, and primes them with its conventions, so a wrong call fails at the task boundary and a right one lands in the asset graph with its provenance. The agent's output is code and assets, the same artifacts a person would produce. See [MCP Server](mcp-server.md).

**Cost:** the agent is held to what the SDK exposes. A new capability is a task someone has to write, which is also how it becomes reusable.

### Wrap tools, don't reimplement them

**GATK, BWA and scanpy stay the source of truth.** Their results are what the literature cites, so a task wraps the tool and types its inputs and outputs. See [Tasks](tasks.md).

## Alternatives that overlap

| Tool | Overlap | Difference |
|------|---------|------------|
| DVC, lakeFS | Hash-based data versioning | Versions live in a git repo or a branchable bucket and are found by path; there are no typed, queryable assets or cross-user public tier |
| Galaxy | Reproducible analyses from a browser | A server-side tool wrapper catalog and histories; analyses are not code a user owns and promotes into a library |
| Terra, Dockstore | Hosted WDL workflows and shared pipelines | Data tables tied to one cloud's workspaces; sharing is of workflows, not of the data they ran on |
| nf-core | Curated, versioned pipelines | Pipelines as the unit, with samplesheets and paths as the data contract |

Stargazer doesn't try to replace these. A task can wrap any of their tools, and the asset graph holds what they produce.

## What this costs

- **Availability is the provider's.** A CID doesn't keep itself alive; a file that matters needs a second copy.
- **Public retrieval is uneven**, and large files are better served from object storage.
- **Metadata is a discipline** that authors carry, since nothing checks that a tag was added.
- **Flyte v2 and Union are young dependencies**, with a smaller ecosystem than the established workflow engines.
- **marimo is less familiar** than Jupyter.
- **Two stores must agree**, the index and the object store.
