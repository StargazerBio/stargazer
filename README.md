# Stargazer

**The perpetual progress machine for computational biology.**

---

Stargazer is an open-science initiative to democratize access to bioinformatics tools. Our mission is to break down silos, foster collaboration, and make reproducibility a painless guarantee rather than a burden.

## Why Stargazer?

Modern bioinformatics is fragmented. Researchers spend more time wrestling with toolchains than doing science. Fire-and-forget bash pipelines with opaquely versioned tools produce results that are difficult to reproduce and impossible to trace. Data provenance is an afterthought, collaboration is friction-laden, and scaling up means starting over.

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

## Current Focus: NVIDIA Parabricks

We're starting with [NVIDIA Clara Parabricks](https://developer.nvidia.com/clara-parabricks) to accelerate the pace of discovery and make the most of modern hardware. GPU-accelerated tools like `fq2bam` and `DeepVariant` can process whole genomes in minutes instead of hours.

### Available Tasks

| Task | Description |
|------|-------------|
| `samtools_faidx` | Create FASTA index (.fai) |
| `bwa_index` | Create BWA alignment indices |
| `fq2bam` | FASTQ to BAM (alignment + sort + markdup) |
| `deepvariant` | GPU-accelerated germline variant calling |
| `haplotypecaller` | GATK HaplotypeCaller for germline SNV/indel calling |

### Example Workflow

```python
from stargazer.workflows.parabricks import wgs_germline_snv
import flyte

flyte.init_from_config()

# Run complete germline variant calling pipeline
run = flyte.run(
    wgs_germline_snv,
    sample_id="NA12878",
    ref_name="GRCh38.fa",
    run_deepvariant=True,
    run_haplotypecaller=True,
)

print(run.url)  # Track progress in Flyte console
run.wait()

alignment, dv_vcf, hc_vcf = run.outputs
```

## Getting Started

### Prerequisites

- Python 3.13+
- [UV](https://github.com/astral-sh/uv) for dependency management
- Access to a Flyte cluster (or local execution mode for testing)
- NVIDIA GPU with Parabricks (for GPU-accelerated tasks)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/stargazer.git
cd stargazer

# Install with UV
uv pip install -e .

# Install dev dependencies
uv pip install -e ".[dev,test]"
```

### Configuration

Set environment variables for IPFS storage:

```bash
# Required for IPFS uploads
export PINATA_JWT="your-pinata-jwt-token"

# Optional: custom gateway
export PINATA_GATEWAY="https://gateway.pinata.cloud"

# Optional: local-only mode for testing (no IPFS uploads)
export STARGAZER_LOCAL_ONLY=true

# Optional: upload to public IPFS (default: private)
export STARGAZER_PUBLIC=false
```

### Running Tests

```bash
# Run all tests
pytest

# Run with local-only mode (no IPFS)
STARGAZER_LOCAL_ONLY=true pytest
```

## Contributing

Stargazer grows through collaboration. Whether you're adding support for a new tool, improving documentation, or fixing bugs—your contributions are welcome.

1. Check the existing tasks in `src/stargazer/tasks/` for patterns
2. Define types in `src/stargazer/types/` for structured I/O
3. Write tests before implementation
4. Keep commits small and meaningful

## Roadmap

- [x] Core infrastructure (Flyte v2, IPFS storage)
- [x] Germline variant calling (DeepVariant, HaplotypeCaller)
- [ ] Somatic variant calling (DeepSomatic, Mutect2)
- [ ] RNA-seq alignment and quantification
- [ ] Structural variant calling
- [ ] Long-read sequencing support (Minimap2, pbmm2)
- [ ] Quality control workflows (FastQC, MultiQC)
- [ ] Protein structure prediction (ColabFold)

## License

MIT

---

*Stargazer: Making computational biology reproducible, accessible, and collaborative—one workflow at a time.*
