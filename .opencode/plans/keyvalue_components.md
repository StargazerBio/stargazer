## Type-Component Contract

### Overview

Stargazer types (Reference, Reads, Alignment, Variants) are **component containers**. Each component represents a specific file or group of files identified by the `component` keyvalue field.

**The Stronger Contract**: Instead of generic `add_files()` methods that accept any files, each type implements **named update methods** with **explicit parameter signatures**. This enforces metadata at the type system level, not just validation level.

```python
# Generic approach (old):
await alignment.add_files([path], keyvalues={"component": "alignment"})

# Named methods (new):
ipfile = await alignment.update_alignment(path, sample_id="S123", is_sorted=True)  # Returns IpFile
ipfile = await alignment.update_index(path, sample_id="S123")                      # Type-safe
```

### Core Principles

1. **IpFile is the interface**: All file operations go through IpFile objects
2. **Named update methods for uploads**: Each component has a specific update method (e.g., `update_alignment()`, `update_index()`) that accepts a Path and named metadata
3. **Direct assignment for hydration**: When loading from IPFS, IpFiles are directly assigned to component fields
4. **Explicit metadata via keyvalues**: Update methods accept named arguments that are converted to keyvalues, not dicts or kwargs
5. **Updates trigger uploads**: Update methods handle upload and return the IpFile
6. **Path resolution is explicit**: Download files to cache, then access via `ipfile.local_path`

### Component Structure

Each type defines its expected components as fields with specific update methods:

```python
@dataclass
class Reference:
    """Reference genome with various indices."""
    fasta: Optional[IpFile] = None
    faidx: Optional[IpFile] = None
    bwa_index: Optional[IpFile] = None
    minimap2_index: Optional[IpFile] = None

    # Metadata
    build: str  # e.g., "GRCh38"

@dataclass
class Alignment:
    """BAM/CRAM alignment with indices."""
    alignment: Optional[IpFile] = None  # BAM/CRAM file
    index: Optional[IpFile] = None      # BAI/CRAI file

    # Metadata
    sample_id: str
    is_sorted: bool = False
```

### Named Update Methods

**Every type implements specific update methods for each component.** These methods:
1. Accept a Path to upload
2. Accept named keyword arguments for metadata (no dicts)
3. Upload the file with keyvalues to IPFS (async)
4. Assign the IpFile to the component field
5. Return the resulting IpFile

#### Reference Update Methods

```python
class Reference:
    async def update_fasta(
        self,
        path: Path,
        build: Optional[str] = None,
    ) -> IpFile:
        """
        Upload reference FASTA component.

        Args:
            path: Path to file to upload
            build: Reference build (uses self.build if not provided)

        Returns:
            IpFile representing the uploaded file
        """
        from stargazer.utils.pinata import default_client

        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "reference",
                "component": "fasta",
                "build": build or self.build,
            }
        )
        self.fasta = ipfile
        return self.fasta

    async def update_faidx(
        self,
        path: Path,
        build: Optional[str] = None,
    ) -> IpFile:
        """
        Upload FASTA index (.fai) component.

        Args:
            path: Path to file to upload
            build: Reference build (uses self.build if not provided)

        Returns:
            IpFile representing the uploaded file
        """
        from stargazer.utils.pinata import default_client

        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "reference",
                "component": "faidx",
                "build": build or self.build,
            }
        )
        self.faidx = ipfile
        return self.faidx

    async def update_bwa_index(
        self,
        path: Path,
        build: Optional[str] = None,
    ) -> IpFile:
        """
        Upload BWA index component.

        Args:
            path: Path to index file to upload
            build: Reference build (uses self.build if not provided)

        Returns:
            IpFile representing the uploaded index
        """
        from stargazer.utils.pinata import default_client

        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "reference",
                "component": "bwa",
                "build": build or self.build,
            }
        )
        self.bwa_index = ipfile
        return self.bwa_index

    async def update_minimap2_index(
        self,
        path: Path,
        build: Optional[str] = None,
    ) -> IpFile:
        """
        Upload minimap2 index component (.mmi file).

        Args:
            path: Path to .mmi file to upload
            build: Reference build (uses self.build if not provided)

        Returns:
            IpFile representing the uploaded index
        """
        from stargazer.utils.pinata import default_client

        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "reference",
                "component": "minimap2",
                "build": build or self.build,
            }
        )
        self.minimap2_index = ipfile
        return self.minimap2_index
```

#### Alignment Update Methods

```python
class Alignment:
    async def update_alignment(
        self,
        path: Path,
        sample_id: Optional[str] = None,
        is_sorted: Optional[bool] = None,
    ) -> IpFile:
        """
        Upload alignment (BAM/CRAM) component.

        Args:
            path: Path to file to upload
            sample_id: Sample identifier (uses self.sample_id if not provided)
            is_sorted: Whether alignment is sorted (uses self.is_sorted if not provided)

        Returns:
            IpFile representing the uploaded file
        """
        from stargazer.utils.pinata import default_client

        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "alignment",
                "component": "alignment",
                "sample_id": sample_id or self.sample_id,
                "is_sorted": str(is_sorted if is_sorted is not None else self.is_sorted),
            }
        )
        self.alignment = ipfile

        if is_sorted is not None:
            self.is_sorted = is_sorted

        return self.alignment

    async def update_index(
        self,
        path: Path,
        sample_id: Optional[str] = None,
    ) -> IpFile:
        """
        Upload alignment index (BAI/CRAI) component.

        Args:
            path: Path to file to upload
            sample_id: Sample identifier (uses self.sample_id if not provided)

        Returns:
            IpFile representing the uploaded file
        """
        from stargazer.utils.pinata import default_client

        ipfile = await default_client.upload_file(
            path,
            keyvalues={
                "type": "alignment",
                "component": "index",
                "sample_id": sample_id or self.sample_id,
            }
        )
        self.index = ipfile
        return self.index
```

### Hydration from IPFS

The `hydrate()` class method queries IPFS and directly assigns IpFiles to component fields:

```python
@classmethod
async def hydrate(
    cls,
    build: str,
    components: Optional[list[str]] = None,
    **filters
) -> "Reference":
    """
    Hydrate a Reference from IPFS.

    Args:
        build: Reference build (GRCh38, GRCh37, etc.)
        components: Optional list of components to fetch
                   If None, fetches all available
        **filters: Additional metadata filters

    Returns:
        Hydrated Reference instance
    """
    from stargazer.utils.pinata import default_client

    ref = cls(build=build)

    # Build query
    keyvalues = {"type": "reference", "build": build, **filters}

    # Fetch files from IPFS
    ipfiles = await default_client.query_files(keyvalues)

    # Directly assign IpFiles to component fields
    for ipfile in ipfiles:
        component = ipfile.keyvalues.get("component")

        # Filter by requested components
        if components and component not in components:
            continue

        # Assign to appropriate field
        if component == "fasta":
            ref.fasta = ipfile
        elif component == "faidx":
            ref.faidx = ipfile
        elif component == "bwa":
            ref.bwa_index = ipfile
        elif component == "minimap2":
            ref.minimap2_index = ipfile
        else:
            import warnings
            warnings.warn(f"Unknown component '{component}' for Reference type")

    return ref


@classmethod
async def hydrate(
    cls,
    sample_id: str,
    components: Optional[list[str]] = None,
    **filters
) -> "Alignment":
    """
    Hydrate an Alignment from IPFS.

    Args:
        sample_id: Sample identifier
        components: Optional list of components to fetch
        **filters: Additional metadata filters

    Returns:
        Hydrated Alignment instance
    """
    from stargazer.utils.pinata import default_client

    alignment = cls(sample_id=sample_id)

    # Build query
    keyvalues = {"type": "alignment", "sample_id": sample_id, **filters}

    # Fetch files from IPFS
    ipfiles = await default_client.query_files(keyvalues)

    # Directly assign IpFiles to component fields
    for ipfile in ipfiles:
        component = ipfile.keyvalues.get("component")

        if components and component not in components:
            continue

        if component == "alignment":
            alignment.alignment = ipfile
            # Extract is_sorted from keyvalues
            is_sorted_str = ipfile.keyvalues.get("is_sorted")
            if is_sorted_str:
                alignment.is_sorted = is_sorted_str.lower() == "true"
        elif component == "index":
            alignment.index = ipfile
        else:
            import warnings
            warnings.warn(f"Unknown component '{component}' for Alignment type")

    return alignment
```

### Workflow Pattern: Version Updates

As files flow through workflows, they often get updated (e.g., unsorted → sorted BAM). The pattern:

1. **Task produces new file** in cache directory
2. **Call named update method** with Path and explicit metadata arguments
3. **Upload happens inside the update method**
4. **Type instance is updated** with new IpFile

```python
@env.task
async def sort_bam(alignment: Alignment) -> Alignment:
    """Sort a BAM file."""
    from stargazer.utils.pinata import default_client

    # Download unsorted BAM to cache
    await default_client.download_file(alignment.alignment)
    unsorted_path = alignment.alignment.local_path

    # Sort in place (cache directory)
    sorted_path = default_client.cache_dir / f"{alignment.sample_id}.sorted.bam"
    subprocess.run([
        "samtools", "sort",
        "-o", str(sorted_path),
        str(unsorted_path)
    ], check=True, cwd=str(default_client.cache_dir))

    # Update alignment with sorted BAM - upload happens automatically
    await alignment.update_alignment(
        sorted_path,
        sample_id=alignment.sample_id,
        is_sorted=True
    )

    return alignment


@env.task
async def index_bam(alignment: Alignment) -> Alignment:
    """Index a BAM file."""
    from stargazer.utils.pinata import default_client

    # Download BAM to cache
    await default_client.download_file(alignment.alignment)
    bam_path = alignment.alignment.local_path

    # Index in cache directory
    index_path = bam_path.with_suffix(bam_path.suffix + ".bai")
    subprocess.run([
        "samtools", "index",
        str(bam_path),
        str(index_path)
    ], check=True, cwd=str(default_client.cache_dir))

    # Update index component - upload happens automatically
    await alignment.update_index(
        index_path,
        sample_id=alignment.sample_id
    )

    return alignment
```

### Path Resolution Pattern

Access files through components with explicit path resolution:

```python
# Download files to cache first
await default_client.download_file(reference.fasta)
await default_client.download_file(reads_r1)
await default_client.download_file(reads_r2)

# Get paths from IpFile local_path
fasta_path = reference.fasta.local_path
r1_path = reads_r1.local_path
r2_path = reads_r2.local_path

# Pass explicit paths to command
subprocess.run([
    "bwa", "mem",
    str(fasta_path),
    str(r1_path),
    str(r2_path)
], cwd=str(default_client.cache_dir), check=True)
```

### Command Execution Pattern

All commands run in the cache directory with explicit paths:

```python
from stargazer.utils.pinata import default_client

# Download files to cache
await default_client.download_file(reference.fasta)
await default_client.download_file(alignment.alignment)

# All file operations happen in cache_dir
subprocess.run(
    ["gatk", "HaplotypeCaller",
     "-R", str(reference.fasta.local_path),
     "-I", str(alignment.alignment.local_path),
     "-O", str(default_client.cache_dir / "output.vcf")
    ],
    cwd=str(default_client.cache_dir),  # Always run in cache
    check=True
)
```

### Benefits of This Contract

1. **Type safety**: Components are typed fields, not dict keys
2. **Explicit metadata**: Required fields enforced at IpFile creation via keyvalues
3. **Version tracking**: Each update creates a new CID with updated keyvalues
4. **Path clarity**: No ambiguity about where files live (always in cache after download)
5. **Cache efficiency**: Single directory simplifies management
6. **Async-first**: All upload/download operations are async for better performance

---