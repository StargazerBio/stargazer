<p align="center">
  <img src=".github/images/8-bit_stargazer_no-bg.jpg" alt="Stargazer" width="400">
</p>

# Stargazer

**The perpetual progress machine for computational biology.**

---

Stargazer is an open-science initiative to broaden access to bioinformatics tools, foster collaboration, and align incentives in service of biomedical progress.

### AI Use Disclaimer
If you're going to take the time to README, I'm going to take the time to WRITEIT. Every word of this README was typed out by Pryce. Additionally, every line of code was reviewed by a human and will continue to be. However, Stargazer is an AI-native project and we intend to leverage these impressive models where they shine while relying on human oversight and expertise to guide them.

## Status: ALPHA
Expect breaking changes and bugs. **DO NOT** use with production data or data containing PHI/PII.

## Quickstart
- Head to stargazer.bio 
OR
- `git clone`

## Why Stargazer?

Many researchers are experts in their specific niche, and have then become proficient bioinformaticians through necessity. On the other hand, well-resourced organizations with their own bioinformatics and devops teams will each have their _specific_ way of running Nextflow pipelines on their Slurm cluster and organizing the filesystem. The backdrop to this fragmentation is the constant deluge of new data. Most of it is lucky to be analyzed in a meaningful way, let alone be re-analyzed in the context of new publications. While authors do their best to maintain access to the methods and data that produced their results, tools tend to go unmaintained and download links tend to grow stale. 

## Our Approach

Stargazer lowers the barrier to entry by placing an agent between the researcher and a set of proven workflows made of deeply composable tasks. The resulting executions run on declarative infrastructure against content-addressable data. Ask Stargazer to align WGS reads against GRCh38 using BWA-MEM2 and it will:

1. **Resolve the data** -- Hydrate references, indices, and read files from content-addressable storage using metadata queries instead of fragile file paths.
2. **Compose the workflow** -- Assemble the correct sequence of Flyte tasks or create new ones with strongly typed inputs/outputs, appropriate resources, and a container image with the necessary dependencies.
3. **Execute with full provenance** -- Run the workflow locally or on managed infrastructure with caching, reproducibility, and error-handling built in.
4. **Return actionable results** -- Deliver outputs to the same flexible and robust storage, to be investigated now or used at any point in the future.

## Architecture

### Interface -- Chat Frontend
A familiar interface where researchers express intent. The LLM has access to a registry of Flyte tasks and workflows as well as an MCP server to interact with them. It understands their patterns, resource requirements and type signatures, allowing it to build novel modules for any requirement.

### Orchestrator -- Flyte V2
[Flyte V2's](https://www.union.ai/docs/v2/flyte/user-guide/overview/) pure-Python and async-native orchestration engine does the heavy-lifting of each Stargazer execution. Everything runs in a container, declare task resource requirements and dependencies in-line. Tasks can be nested arbitrarily and executed async with standard Python patterns. Types are enforced at the task boundary and capture inputs and outputs with all necessary metadata.

### Storage -- IPFS via Pinata
Every file in Stargazer is content-addressable on [IPFS](https://docs.ipfs.tech/concepts/how-ipfs-works/) and self-describing via [Pinata](https://pinata.cloud/blog/using-file-centric-architecture-to-build-simple-and-capable-apps/). This powerful combination means that workflows interact with data via their attributes, not their location. Moreover, reproducibility becomes intrinsic as data is identified by an immutable, cryptographic commitment to its content.

## Execution Modes
While it would be nice to have all research be done in the public domain, I acknowledge this isn't realistic in many cases. As such, Stargazer has a few execution modes:
- STARGAZER_MODE=local                        → local exec, local storage
- STARGAZER_MODE=local + PINATA_JWT=xxx       → local exec, pinata storage
- STARGAZER_MODE=cloud                        → union exec, cloud-hosted storage (no JWT needed)

## (Over)engineered for an Open-Future
I've been thinking about and building this before agentic-development for [some time now](https://www.youtube.com/watch?v=F7UUm78iito), and I acknowledge that some of the foundational patterns may be appear rather heavy. Stargazer aims to accomodate as many computational approaches, tools, and lines-of-inquiry as possible and has therefore made every attempt to be flexible and [open](LICENSE.md) with an opinionated core. Within this framework, every user naturally becomes a contributor. My hope is that anyone who derives value from Stargazer will kindly let their reasoning, workflows, and results flow into the public domain. In doing so, they will add momentum to the flywheel of perpetual progress.



- project direction subject to change based on the needs of the community
- commitment to open-source, always
- add video link from scipy
- modes: local, cloud, hybrid, public, private
- 