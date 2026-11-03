<p align="center">
  <img src=".github/images/8-bit_stargazer_no-bg.jpg" alt="Stargazer" width="400">
</p>

# Stargazer

**The perpetual progress machine for computational biology**

---

Stargazer is an open-science initiative to broaden access to bioinformatics tools, foster collaboration, and align incentives in service of biomedical progress.

## Status: Alpha 🏗️
Collecting early feedback on direction and architecture. Try the quickstart!

## Quickstart

- `docker run -d -p 8080:8080 ghcr.io/stargazerbio/stargazer`
- Work through the tutorial notebooks and explore the agentic [tooling](https://docs.marimo.io/guides/editor_features/agents/)

**OR**

- Log into your hosted [dashboard](https://stargazer.bio) with GitHub

Everything is just a Flyte workflow under the hood; feel free to start the container with `--entrypoint bash` and run any workflows or check out the [TUI](https://www.union.ai/docs/v2/flyte/user-guide/running-locally/#terminal-ui) from there.

Additional quickstart options and details are available in the [docs](https://docs.stargazer.bio/getting-started/).

## Why Stargazer?

Many researchers are experts in their specific niche and became proficient bioinformaticians through necessity. LLMs have all but removed that barrier; however, in removing the friction, we've also left a lot of reproducibility to the vagaries of prompting. Meanwhile, new data arrives faster than it can be analyzed, let alone re-analyzed in the context of new publications. Despite authors' best efforts, tools go unmaintained and download links grow stale.

## Our Approach

Stargazer bakes best practices into the agent harness to enable workflows made of composable tasks in the familiar environment of a notebook. The resulting executions run on declarative infrastructure against a graph of content-addressable data. Ask Stargazer to align WGS reads against GRCh38 using BWA-MEM2 and it will:

1. **Resolve the data** -- Hydrate references, indices, and read files from content-addressable storage using metadata queries instead of fragile file paths.
2. **Compose the workflow** -- Assemble the correct sequence of Flyte tasks or create new ones with strongly typed inputs/outputs, appropriate resources, and a container image with the necessary dependencies.
3. **Execute with full provenance** -- Run the workflow locally or on managed infrastructure with caching, reproducibility, and error handling built in.
4. **Return actionable results** -- Deliver outputs to the same flexible and robust storage, to be investigated now or used at any point in the future.

## Architecture

### Interface - Marimo notebooks
A familiar interface where researchers design by intent. The agent has access to a registry of Flyte tasks and workflows as well as an MCP server to interact with them. Run exploratory analyses directly in the notebook environment or flip a config toggle to run the same workflow on an arbitrarily scalable cluster.

### Orchestrator - Flyte V2
[Flyte V2's](https://www.union.ai/docs/v2/flyte/user-guide/overview/) pure-Python and async-native orchestration engine does the heavy lifting of each Stargazer execution. Everything runs in a container with task resource requirements and dependencies declared inline. Tasks can be nested arbitrarily and executed asynchronously with standard Python patterns. Types are enforced at the task boundary and capture inputs and outputs with all necessary metadata.

### Storage - Content-Addressed Asset Graph
Files in Stargazer are content-addressable, inspired by [IPFS](https://docs.ipfs.tech/concepts/how-ipfs-works/). They are also self-describing via key-value metadata, inspired by [Pinata](https://pinata.cloud/blog/using-file-centric-architecture-to-build-simple-and-capable-apps/). Reproducibility becomes intrinsic as data is identified by an immutable, cryptographic commitment to its content. This powerful combination also means that workflows interact with data via composable queries, not by its location.

## Execution Modes
Stargazer has a few execution modes to control exactly where data is processed and stored.

Locally, the default is fully private compute and storage, with your files under `~/.stargazer`. By adding a `PINATA_JWT` env var, you can push and pull public assets from IPFS via Pinata.

Stargazer is also hosted on [Union](https://www.union.ai/), where you can work on notebooks, workflows, and assets from your browser.

## Perpetual progress machine?
Never before has there been a greater opportunity to unify the fragmented landscape of bioinformatics tools and techniques. Frontier models enable integrating the plurality of inputs and contributions faster and more fairly than ever before. Stargazer doesn't aim to be yet another standard, but an organic substrate that evolves and responds to the needs of discovery in real time.

The foundational patterns of this project [predate](https://www.youtube.com/watch?v=F7UUm78iito) the agentic development era, and they are a divergence from the norm. Stargazer aims to accommodate as many computational approaches, tools, and lines of inquiry as possible and has therefore made every attempt to be flexible and [open](LICENSE) with an opinionated core.

Within this framework, every user naturally becomes a contributor. My hope is that anyone who derives value from Stargazer will kindly let their reasoning, workflows, and results graduate into the public domain. In doing so, they will add momentum to the flywheel of perpetual progress.

> ⚠️ AI Use Disclaimer: If you're going to take the time to README, I'm going to take the time to WRITEIT. Every word of this README was typed out by a human. Additionally, every line of code was reviewed by a human and will continue to be. However, Stargazer is an AI-native project and I intend to leverage these impressive models where they shine while relying on human oversight and expertise to guide them.
