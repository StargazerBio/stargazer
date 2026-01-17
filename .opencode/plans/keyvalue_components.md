## Type-Component Contract

### Overview

Stargazer types (Reference, Reads, Alignment, Variants) are **component containers**. Each component represents a specific file or group of files identified by the `component` metadata field.

**The Stronger Contract**: Instead of generic `update_component()` methods that route based on metadata, each type implements **named update methods** with **explicit parameter signatures**. This enforces metadata at the type system level, not just validation level.

```python
# Generic approach (old):
alignment.add_files([ipfile])  # Routes based on ipfile.component

# Named methods (new):
alignment.update_alignment(path, sample_id="S123", is_sorted=True)  # Explicit
alignment.update_index(path, sample_id="S123")                      # Type-safe
```

### Core Principles

1. **IPFile is the interface**: All file operations go through IPFile objects
2. **Named update methods**: Each component has a specific update method (e.g., `update_alignment()`, `update_index()`)
3. **Explicit metadata**: Update methods accept named arguments, not kwargs
4. **Updates trigger uploads**: Update methods handle upload, either to IPFS or locally depending on the configuration
5. **Path resolution is explicit**: Access files via `type.component.get_path()`

### Component Structure

Each type defines its expected components as fields with specific update methods:

```python
@dataclass
class Reference:
    """Reference genome with various indices."""
    fasta: Optional[IPFile] = None
    faidx: Optional[IPFile] = None
    bwa_index: Optional[List[IPFile]] = None
    minimap2_index: Optional[List[IPFile]] = None

    # Metadata
    build: str  # e.g., "GRCh38"

@dataclass
class Alignment:
    """BAM/CRAM alignment with indices."""
    alignment: Optional[IPFile] = None  # BAM/CRAM file
    index: Optional[IPFile] = None      # BAI/CRAI file

    # Metadata
    sample_id: str
    is_sorted: bool = False
```

### Named Update Methods

**Every type implements specific update methods for each component.** These methods:
1. Accept explicit named arguments for metadata (no dicts)
2. Call upload internally if given a Path
3. Accept IPFile if already uploaded
4. Validate metadata matches the type

#### Reference Update Methods

```python
class Reference:
    def update_fasta(
        self,
        source: Union[Path, IPFile],
        build: Optional[str] = None,
    ) -> "Reference":
        """
        Update reference FASTA component.

        Args:
            source: Path to upload or existing IPFile
            build: Reference build (uses self.build if not provided)

        Returns:
            Self for chaining
        """
        if isinstance(source, IPFile):
            # Validate existing IPFile
            if source.type != "reference":
                raise ValueError(f"IPFile type must be 'reference', got '{source.type}'")
            if source.component != "fasta":
                raise ValueError(f"IPFile component must be 'fasta', got '{source.component}'")
            self.fasta = source
        else:
            # Upload new file
            from stargazer.utils.pinata import get_client
            client = get_client()

            result = client.upload_file_sync(
                source,
                metadata={
                    "type": "reference",
                    "component": "fasta",
                    "build": build or self.build,
                }
            )
            self.fasta = result.to_ipfile()

        return self

    def update_faidx(
        self,
        source: Union[Path, IPFile],
        build: Optional[str] = None,
    ) -> "Reference":
        """
        Update FASTA index (.fai) component.

        Args:
            source: Path to upload or existing IPFile
            build: Reference build (uses self.build if not provided)

        Returns:
            Self for chaining
        """
        if isinstance(source, IPFile):
            if source.type != "reference":
                raise ValueError(f"IPFile type must be 'reference', got '{source.type}'")
            if source.component != "faidx":
                raise ValueError(f"IPFile component must be 'faidx', got '{source.component}'")
            self.faidx = source
        else:
            from stargazer.utils.pinata import get_client
            client = get_client()

            result = client.upload_file_sync(
                source,
                metadata={
                    "type": "reference",
                    "component": "faidx",
                    "build": build or self.build,
                }
            )
            self.faidx = result.to_ipfile()

        return self

    def update_aligner_index(
        self,
        source: Union[Path, list[Path], IPFile],
        aligner: Literal["bwa", "minimap2"],
        build: Optional[str] = None,
    ) -> "Reference":
        """
        Update aligner index component.

        For BWA: accepts directory Path or list of index file Paths
        For minimap2: accepts single .mmi file Path

        Args:
            source: Path/directory to upload or existing IPFile
            aligner: Aligner name ("bwa" or "minimap2")
            build: Reference build (uses self.build if not provided)

        Returns:
            Self for chaining
        """
        if isinstance(source, IPFile):
            if source.type != "reference":
                raise ValueError(f"IPFile type must be 'reference', got '{source.type}'")
            if source.component != aligner:
                raise ValueError(
                    f"IPFile component must be '{aligner}', got '{source.component}'"
                )

            if aligner == "bwa":
                self.bwa_index = source
            elif aligner == "minimap2":
                self.minimap2_index = source
        else:
            from stargazer.utils.pinata import get_client
            client = get_client()

            metadata = {
                "type": "reference",
                "component": aligner,
                "build": build or self.build,
            }

            # BWA index is typically a directory with multiple files
            if aligner == "bwa" and isinstance(source, Path) and source.is_dir():
                result = client.upload_directory_sync(source, metadata=metadata)
            else:
                # Single file (minimap2 or single BWA file)
                if isinstance(source, list):
                    raise ValueError(
                        "List of paths not yet supported; provide directory Path instead"
                    )
                result = client.upload_file_sync(source, metadata=metadata)

            ipfile = result.to_ipfile()
            if aligner == "bwa":
                self.bwa_index = ipfile
            elif aligner == "minimap2":
                self.minimap2_index = ipfile

        return self
```

#### Alignment Update Methods

```python
class Alignment:
    def update_alignment(
        self,
        source: Union[Path, IPFile],
        sample_id: Optional[str] = None,
        is_sorted: Optional[bool] = None,
    ) -> "Alignment":
        """
        Update alignment (BAM/CRAM) component.

        Args:
            source: Path to upload or existing IPFile
            sample_id: Sample identifier (uses self.sample_id if not provided)
            is_sorted: Whether alignment is sorted (uses self.is_sorted if not provided)

        Returns:
            Self for chaining
        """
        if isinstance(source, IPFile):
            if source.type != "alignment":
                raise ValueError(f"IPFile type must be 'alignment', got '{source.type}'")
            if source.component != "alignment":
                raise ValueError(
                    f"IPFile component must be 'alignment', got '{source.component}'"
                )
            self.alignment = source

            # Update metadata from IPFile
            if is_sorted is not None:
                self.is_sorted = is_sorted
            elif source.get_metadata("is_sorted"):
                self.is_sorted = source.get_metadata("is_sorted").lower() == "true"
        else:
            from stargazer.utils.pinata import get_client
            client = get_client()

            result = client.upload_file_sync(
                source,
                metadata={
                    "type": "alignment",
                    "component": "alignment",
                    "sample_id": sample_id or self.sample_id,
                    "is_sorted": str(is_sorted if is_sorted is not None else self.is_sorted),
                }
            )
            self.alignment = result.to_ipfile()

            if is_sorted is not None:
                self.is_sorted = is_sorted

        return self

    def update_index(
        self,
        source: Union[Path, IPFile],
        sample_id: Optional[str] = None,
    ) -> "Alignment":
        """
        Update alignment index (BAI/CRAI) component.

        Args:
            source: Path to upload or existing IPFile
            sample_id: Sample identifier (uses self.sample_id if not provided)

        Returns:
            Self for chaining
        """
        if isinstance(source, IPFile):
            if source.type != "alignment":
                raise ValueError(f"IPFile type must be 'alignment', got '{source.type}'")
            if source.component != "index":
                raise ValueError(f"IPFile component must be 'index', got '{source.component}'")
            self.index = source
        else:
            from stargazer.utils.pinata import get_client
            client = get_client()

            result = client.upload_file_sync(
                source,
                metadata={
                    "type": "alignment",
                    "component": "index",
                    "sample_id": sample_id or self.sample_id,
                }
            )
            self.index = result.to_ipfile()

        return self
```

### Hydration with Named Update Methods

The `hydrate()` class method queries IPFS and uses named update methods to populate the instance:

```python
@classmethod
def hydrate(
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
    from stargazer.utils.pinata import get_client
    import asyncio

    client = get_client()
    ref = cls(build=build)

    # Build query
    query_metadata = {"type": "reference", "build": build, **filters}

    # Fetch files from IPFS
    async def fetch_files():
        files = []
        query = client.list_files().with_metadata_dict(query_metadata)
        async for ipfile in query:
            files.append(ipfile)
        return files

    # Run async query
    loop = asyncio.get_event_loop()
    ipfiles = loop.run_until_complete(fetch_files())

    # Route files to appropriate update methods based on component
    for ipfile in ipfiles:
        component = ipfile.component

        # Filter by requested components
        if components and component not in components:
            continue

        # Call appropriate update method
        if component == "fasta":
            ref.update_fasta(ipfile)
        elif component == "faidx":
            ref.update_faidx(ipfile)
        elif component in ["bwa", "minimap2"]:
            ref.update_aligner_index(ipfile, aligner=component)
        else:
            # Unknown component - log warning or raise?
            import warnings
            warnings.warn(f"Unknown component '{component}' for Reference type")

    return ref


@classmethod
def hydrate(
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
    from stargazer.utils.pinata import get_client
    import asyncio

    client = get_client()
    alignment = cls(sample_id=sample_id)

    # Build query
    query_metadata = {"type": "alignment", "sample_id": sample_id, **filters}

    # Fetch files from IPFS
    async def fetch_files():
        files = []
        query = client.list_files().with_metadata_dict(query_metadata)
        async for ipfile in query:
            files.append(ipfile)
        return files

    # Run async query
    loop = asyncio.get_event_loop()
    ipfiles = loop.run_until_complete(fetch_files())

    # Route files to appropriate update methods
    for ipfile in ipfiles:
        component = ipfile.component

        if components and component not in components:
            continue

        if component == "alignment":
            alignment.update_alignment(ipfile)
        elif component == "index":
            alignment.update_index(ipfile)
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
4. **Type instance is updated** with new IPFile

```python
@env.task
def sort_bam(alignment: Alignment) -> Alignment:
    """Sort a BAM file."""
    from stargazer.utils.pinata import get_client

    client = get_client()

    # Get unsorted BAM path
    unsorted_path = alignment.alignment.get_path()

    # Sort in place (cache directory)
    sorted_path = client.cache_dir / f"{alignment.sample_id}.sorted.bam"
    subprocess.run([
        "samtools", "sort",
        "-o", str(sorted_path),
        str(unsorted_path)
    ], check=True, cwd=str(client.cache_dir))

    # Update alignment with sorted BAM - upload happens automatically
    alignment.update_alignment(
        sorted_path,
        sample_id=alignment.sample_id,
        is_sorted=True
    )

    return alignment


@env.task
def index_bam(alignment: Alignment) -> Alignment:
    """Index a BAM file."""
    from stargazer.utils.pinata import get_client

    client = get_client()

    # Get BAM path
    bam_path = alignment.alignment.get_path()

    # Index in cache directory
    index_path = bam_path.with_suffix(bam_path.suffix + ".bai")
    subprocess.run([
        "samtools", "index",
        str(bam_path),
        str(index_path)
    ], check=True, cwd=str(client.cache_dir))

    # Update index component - upload happens automatically
    alignment.update_index(
        index_path,
        sample_id=alignment.sample_id
    )

    return alignment
```

### Path Resolution Pattern

Access files through components with explicit path resolution:

```python
# Get path to reference FASTA
fasta_path = reference.fasta.get_path()

# Pass explicit path to command
subprocess.run([
    "bwa", "mem",
    str(fasta_path),
    str(reads_r1.get_path()),
    str(reads_r2.get_path())
], cwd=str(client.cache_dir), check=True)
```

### Command Execution Pattern

All commands run in the cache directory with explicit paths:

```python
from stargazer.utils.pinata import get_client

client = get_client()

# All file operations happen in cache_dir
subprocess.run(
    ["gatk", "HaplotypeCaller",
     "-R", str(reference.fasta.get_path()),
     "-I", str(alignment.bam.get_path()),
     "-O", str(client.cache_dir / "output.vcf")
    ],
    cwd=str(client.cache_dir),  # Always run in cache
    check=True
)
```

### Benefits of This Contract

1. **Type safety**: Components are typed fields, not dict keys
2. **Explicit metadata**: Required fields enforced at IPFile creation
3. **Version tracking**: Each update creates a new CID with updated metadata
4. **Path clarity**: No ambiguity about where files live
5. **Cache efficiency**: Single directory simplifies management

---