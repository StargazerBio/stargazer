<p align="center">
  <img src=".github/images/8-bit_stargazer_no-bg.jpg" alt="Stargazer" width="400">
</p>

# Stargazer

**The perpetual progress machine for computational biology.**

---

Stargazer is an open-science initiative to democratize access to bioinformatics tools. Our mission is to break down silos, foster collaboration, and make reproducibility a painless guarantee rather than a burden.

## Status: ALPHA
Expect breaking changes and bugs. **DO NOT** use with production data or data containing PHI/PII.

## Why Stargazer?

Modern bioinformatics is fragmented. Researchers spend more time wrestling with toolchains than doing science. Fire-and-forget bash pipelines with opaquely versioned tools produce results that are difficult to reproduce and impossible to trace. Data provenance and availability requires maintenance, collaboration is friction-laden, and scaling up means starting over.

Stargazer changes that.

**Reproducibility by default.** Every task execution is tracked, versioned, and auditable. No more "works on my machine"—if it ran once, it will run the same way forever.

**Data provenance as a first-class citizen.** Built on IPFS-backed storage, every input and output is content-addressed and traceable. Know exactly what data produced what results.

**Orchestration at the core.** Powered by [Flyte](https://flyte.org), Stargazer handles workflow orchestration, parallelism, and massive scale out of the box. Focus on your science, not your infrastructure.

**Agentic development, provider-agnostic.** While the code and architecture are carefully supervised, Stargazer embraces agentic development practices. The goal is for this project to grow organically to enable everyone's workflows, no matter how niche.

## Architecture

Stargazer's design is simple and opinionated—admittedly overengineered for small tasks, but this ensures that as the project grows, all the pieces continue to work together seamlessly.

```
stargazer/
├── src/stargazer/
│   ├── tasks/       # Individual Flyte tasks (one tool, one task)
│   ├── workflows/   # Composed pipelines (tasks calling tasks)
│   ├── types/       # Structured I/O dataclasses
│   └── utils/       # IPFS client, subprocess helpers
└── tests/           # Unit and integration tests
```

### Core Concepts

- **Tasks** are atomic units of work: alignment, variant calling, indexing
- **Workflows** compose tasks into end-to-end pipelines
- **Types** define structured inputs and outputs with full type safety
- **IPFS Storage** provides content-addressed, immutable data storage

## License

MIT

---
