# Stargazer Technical Design Document

## Overview

Stargazer is a bioinformatics workflow orchestration system that combines IPFS decentralized storage (via Pinata) with Flyte v2 for computational genomics pipelines. The core innovation is using IPFS Content Identifiers (CIDs) as universal file identifiers, with query-based dataclass hydration for bioinformatics-specific types.

### Design Principles

1. **PinataClient** is a clean, focused wrapper around three Pinata API v3 endpoints
2. **Query-based hydration** via `.query()` and `.get()` class methods on types
3. **Fluent filtering** with `.with_keyvalue()` chains for building queries
4. **Local Flyte Files** - downloads happen at hydration time, tasks see only local `flyte.io.File` objects
5. **`.pin()` method** for uploading task outputs back to IPFS

### Key Insight

Flyte never talks to IPFS directly. Python code handles Pinata API interactions, downloads files to local disk, and hands Flyte local paths via `flyte.io.File.from_local_sync()`. This clean separation avoids any need to modify Flyte SDK or fsspec.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Code / LLM Frontend                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Stargazer Types                          │
│  Reference.query() / .get() / .from_cid() / .from_local()   │
│  Reads.query() / .get() / .from_cids() / .from_local()      │
│  Alignment.query() / .get() / .from_cids() / .pin()         │
│  Variants.query() / .get() / .from_cids() / .pin()          │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│      PinataClient        │    │      Flyte Tasks         │
│  list_files() → query    │    │  @env.task functions     │
│  get_file() → by ID      │    │  work with local Files   │
│  upload_file() → pin     │    │  subprocess calls        │
│  download() → cache      │    │  bioinformatics tools    │
└──────────────────────────┘    └──────────────────────────┘
              │                               │
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│    IPFS via Pinata       │    │    Compute Backend       │
│  Content-addressable     │    │    Local / K8s / GPU     │
│  Gateway downloads       │    │                          │
└──────────────────────────┘    └──────────────────────────┘
```

---

## Project Structure

```
stargazer/
├── src/
│   └── stargazer/
│       ├── __init__.py           # Package exports
│       ├── utils/
│       │   ├── __init__.py
│       │   └── pinata.py         # Pinata API client
│       ├── types/
│       │   ├── __init__.py
│       │   ├── base.py           # Schema constants, helpers
│       │   ├── reference.py      # Reference genome type
│       │   ├── reads.py          # Sequencing reads type
│       │   ├── alignment.py      # BAM/CRAM type
│       │   └── variants.py       # VCF type
│       ├── tasks/
│       │   ├── __init__.py
│       │   ├── samtools.py       # Samtools operations
│       │   ├── alignment.py      # BWA, minimap2
│       │   └── parabricks.py     # GPU-accelerated tools
│       └── workflows/
│           ├── __init__.py
│           ├── alignment.py      # Alignment pipelines
│           └── germline.py       # Germline variant calling
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── unit/
│   └── integration/
└── pyproject.toml
```

---

## Module 1: Pinata Client (`utils/pinata.py`)

The PinataClient wraps three Pinata API v3 endpoints with a clean, async Python interface.

### Pinata API Endpoints

| Endpoint | Method | URL | Purpose |
|----------|--------|-----|---------|
| List Files | GET | `/v3/files/{network}` | Query files with metadata filters |
| Get File | GET | `/v3/files/{network}/{id}` | Get single file by Pinata ID |
| Upload File | POST | `uploads.pinata.cloud/v3/files` | Upload local file, returns CID |
| Update File | PUT | `/v3/files/{network}/{id}` | Update name/keyvalues |

### Data Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal

@dataclass
class PinataFile:
    """
    Represents a file stored in Pinata.
    This is the core query result that feeds dataclass hydration.
    """
    id: str                              # Pinata's internal ID
    cid: str                             # IPFS CID - the content hash
    name: Optional[str]
    size: int
    mime_type: Optional[str]
    number_of_files: int
    group_id: Optional[str]
    keyvalues: dict[str, str]            # Metadata for querying
    created_at: datetime
    network: Literal["public", "private"] = "public"
    
    @classmethod
    def from_api_response(cls, data: dict, network: str = "public") -> "PinataFile":
        """Parse from Pinata API JSON response."""
        ...
    
    def gateway_url(self, gateway: str = "https://gateway.pinata.cloud") -> str:
        """Get the gateway URL for downloading this file."""
        return f"{gateway}/ipfs/{self.cid}"
    
    def get_keyvalue(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a keyvalue with optional default."""
        return self.keyvalues.get(key, default)


@dataclass
class UploadResult:
    """Result from uploading a file to Pinata."""
    id: str
    cid: str
    name: Optional[str]
    size: int
    mime_type: Optional[str]
    keyvalues: dict[str, str]
    created_at: datetime
    
    @classmethod
    def from_api_response(cls, data: dict) -> "UploadResult":
        ...


@dataclass
class ListFilesQuery:
    """
    Query builder for listing files.
    Supports fluent chaining for building queries.
    """
    name: Optional[str] = None
    cid: Optional[str] = None
    group_id: Optional[str] = None
    mime_type: Optional[str] = None
    keyvalues: dict[str, str] = field(default_factory=dict)
    limit: int = 100
    page_token: Optional[str] = None
    order: Literal["ASC", "DESC"] = "DESC"
    
    def with_name(self, name: str) -> "ListFilesQuery":
        self.name = name
        return self
    
    def with_cid(self, cid: str) -> "ListFilesQuery":
        self.cid = cid
        return self
    
    def with_keyvalue(self, key: str, value: str) -> "ListFilesQuery":
        self.keyvalues[key] = value
        return self
    
    def with_keyvalues(self, keyvalues: dict[str, str]) -> "ListFilesQuery":
        self.keyvalues.update(keyvalues)
        return self
    
    def with_limit(self, limit: int) -> "ListFilesQuery":
        self.limit = min(limit, 1000)  # Pinata max is 1000
        return self
    
    def to_params(self) -> dict:
        """Convert to API query parameters."""
        params = {"pageLimit": self.limit, "order": self.order}
        if self.name:
            params["name"] = self.name
        if self.cid:
            params["cid"] = self.cid
        if self.keyvalues:
            params["metadata[keyvalues]"] = json.dumps(self.keyvalues)
        return params
```

### PinataClient Implementation

```python
import os
import json
import aiohttp
import aiofiles
from pathlib import Path

class PinataClient:
    """
    Async client for Pinata API v3.
    
    Usage:
        client = PinataClient()
        
        # List files with filtering
        async for file in client.list_files().with_keyvalue("type", "reference"):
            print(file.cid)
        
        # Get single file by ID
        file = await client.get_file("file-id-here")
        
        # Upload
        result = await client.upload_file(
            Path("my_file.bam"), 
            keyvalues={"type": "alignment"}
        )
    """
    
    API_BASE = "https://api.pinata.cloud/v3"
    UPLOAD_BASE = "https://uploads.pinata.cloud/v3"
    
    def __init__(
        self,
        jwt: Optional[str] = None,
        gateway: Optional[str] = None,
        cache_dir: Optional[Path] = None,
    ):
        self._jwt = jwt or os.environ.get("PINATA_JWT")
        self.gateway = gateway or os.environ.get(
            "PINATA_GATEWAY", 
            "https://gateway.pinata.cloud"
        )
        self.cache_dir = cache_dir or Path(os.environ.get(
            "STARGAZER_CACHE", 
            Path.home() / ".stargazer" / "cache"
        ))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def jwt(self) -> str:
        if not self._jwt:
            raise ValueError(
                "PINATA_JWT not set. Provide jwt= argument or "
                "set PINATA_JWT environment variable."
            )
        return self._jwt
    
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.jwt}"}
    
    # ========================================================================
    # List Files - Returns async iterator with fluent query builder
    # ========================================================================
    
    def list_files(
        self, 
        network: Literal["public", "private"] = "public"
    ) -> "ListFilesIterator":
        """
        Create a query to list files.
        Returns an async iterator that auto-paginates.
        
        Usage:
            async for file in client.list_files().with_keyvalue("type", "alignment"):
                print(file.cid)
            
            # Get first match
            file = await client.list_files().with_cid("Qm...").first()
        """
        return ListFilesIterator(self, network, ListFilesQuery())
    
    async def _fetch_files_page(
        self, 
        network: str, 
        query: ListFilesQuery
    ) -> tuple[list[PinataFile], Optional[str]]:
        """Fetch a single page of files."""
        url = f"{self.API_BASE}/files/{network}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, 
                headers=self._headers(), 
                params=query.to_params()
            ) as response:
                response.raise_for_status()
                data = await response.json()
                
                files = [
                    PinataFile.from_api_response(f, network) 
                    for f in data.get("data", {}).get("files", [])
                ]
                next_token = data.get("data", {}).get("next_page_token")
                
                return files, next_token
    
    # ========================================================================
    # Get File by ID
    # ========================================================================
    
    async def get_file(
        self, 
        file_id: str, 
        network: Literal["public", "private"] = "public"
    ) -> PinataFile:
        """Get a file by its Pinata ID (not the CID)."""
        url = f"{self.API_BASE}/files/{network}/{file_id}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self._headers()) as response:
                response.raise_for_status()
                data = await response.json()
                return PinataFile.from_api_response(data.get("data", data), network)
    
    async def get_file_by_cid(
        self,
        cid: str,
        network: Literal["public", "private"] = "public"
    ) -> Optional[PinataFile]:
        """Convenience: search by CID and return first match."""
        return await self.list_files(network).with_cid(cid).first()
    
    # ========================================================================
    # Upload
    # ========================================================================
    
    async def upload_file(
        self,
        path: Path,
        name: Optional[str] = None,
        group_id: Optional[str] = None,
        keyvalues: Optional[dict[str, str]] = None,
        network: Literal["public", "private"] = "public",
    ) -> UploadResult:
        """
        Upload a local file to Pinata.
        
        Args:
            path: Local file path
            name: Optional custom name
            group_id: Optional group ID
            keyvalues: Metadata key-value pairs for querying
            network: "public" or "private"
        
        Returns:
            UploadResult with CID
        """
        url = f"{self.UPLOAD_BASE}/files"
        
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', open(path, 'rb'), filename=name or path.name)
            data.add_field('network', network)
            
            if name:
                data.add_field('name', name)
            if group_id:
                data.add_field('group_id', group_id)
            if keyvalues:
                data.add_field('keyvalues', json.dumps(keyvalues))
            
            async with session.post(url, headers=self._headers(), data=data) as response:
                response.raise_for_status()
                result = await response.json()
                return UploadResult.from_api_response(result.get("data", result))
    
    async def upload_directory(
        self,
        path: Path,
        name: Optional[str] = None,
        keyvalues: Optional[dict[str, str]] = None,
        network: Literal["public", "private"] = "public",
    ) -> UploadResult:
        """Upload a directory (preserves structure under single CID)."""
        url = f"{self.UPLOAD_BASE}/files"
        
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(path)
                    data.add_field('file', open(file_path, 'rb'), filename=str(rel_path))
            
            data.add_field('network', network)
            if name:
                data.add_field('name', name)
            if keyvalues:
                data.add_field('keyvalues', json.dumps(keyvalues))
            
            async with session.post(url, headers=self._headers(), data=data) as response:
                response.raise_for_status()
                result = await response.json()
                return UploadResult.from_api_response(result.get("data", result))
    
    # ========================================================================
    # Update Metadata
    # ========================================================================
    
    async def update_file(
        self,
        file_id: str,
        name: Optional[str] = None,
        keyvalues: Optional[dict[str, str]] = None,
        network: Literal["public", "private"] = "public",
    ) -> PinataFile:
        """Update a file's name and/or keyvalues."""
        url = f"{self.API_BASE}/files/{network}/{file_id}"
        
        payload = {}
        if name:
            payload["name"] = name
        if keyvalues:
            payload["keyvalues"] = keyvalues
        
        async with aiohttp.ClientSession() as session:
            async with session.put(
                url,
                headers={**self._headers(), "Content-Type": "application/json"},
                data=json.dumps(payload),
            ) as response:
                response.raise_for_status()
                result = await response.json()
                return PinataFile.from_api_response(result.get("data", result), network)
    
    # ========================================================================
    # Download (via Gateway) - Downloads to local cache
    # ========================================================================
    
    async def download(self, cid: str, dest: Optional[Path] = None) -> Path:
        """
        Download content by CID via gateway.
        Uses local cache to avoid re-downloading.
        
        Args:
            cid: IPFS CID (can include path like "Qmxxx/subdir/file.txt")
            dest: Optional destination path
        
        Returns:
            Local path to downloaded file
        """
        # Cache key based on full CID (including any path)
        cache_key = cid.replace("/", "_")
        cache_path = self.cache_dir / cache_key
        
        # Check cache first
        if cache_path.exists():
            if dest:
                import shutil
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(cache_path, dest)
                return dest
            return cache_path
        
        # Download from gateway
        url = f"{self.gateway}/ipfs/{cid}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(cache_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
        
        if dest:
            import shutil
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(cache_path, dest)
            return dest
        
        return cache_path
    
    def download_sync(self, cid: str, dest: Optional[Path] = None) -> Path:
        """Synchronous download for use in sync contexts."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.download(cid, dest))
```

### ListFilesIterator (Auto-pagination with fluent API)

```python
class ListFilesIterator:
    """
    Async iterator for listing files with auto-pagination.
    Supports method chaining for building queries.
    """
    
    def __init__(self, client: PinataClient, network: str, query: ListFilesQuery):
        self._client = client
        self._network = network
        self._query = query
        self._buffer: list[PinataFile] = []
        self._next_token: Optional[str] = None
        self._exhausted = False
    
    # Query builder methods (return self for chaining)
    def with_name(self, name: str) -> "ListFilesIterator":
        self._query.with_name(name)
        return self
    
    def with_cid(self, cid: str) -> "ListFilesIterator":
        self._query.with_cid(cid)
        return self
    
    def with_keyvalue(self, key: str, value: str) -> "ListFilesIterator":
        self._query.with_keyvalue(key, value)
        return self
    
    def with_keyvalues(self, keyvalues: dict[str, str]) -> "ListFilesIterator":
        self._query.with_keyvalues(keyvalues)
        return self
    
    def with_limit(self, limit: int) -> "ListFilesIterator":
        self._query.with_limit(limit)
        return self
    
    # Async iterator protocol
    def __aiter__(self) -> "ListFilesIterator":
        return self
    
    async def __anext__(self) -> PinataFile:
        if self._buffer:
            return self._buffer.pop(0)
        
        if self._exhausted:
            raise StopAsyncIteration
        
        self._query.page_token = self._next_token
        files, self._next_token = await self._client._fetch_files_page(
            self._network, self._query
        )
        
        if not files:
            self._exhausted = True
            raise StopAsyncIteration
        
        if not self._next_token:
            self._exhausted = True
        
        self._buffer = files[1:]
        return files[0]
    
    # Convenience methods
    async def first(self) -> Optional[PinataFile]:
        """Get first result or None."""
        try:
            return await self.__anext__()
        except StopAsyncIteration:
            return None
    
    async def all(self) -> list[PinataFile]:
        """Collect all results (caution on large sets)."""
        results = []
        async for file in self:
            results.append(file)
        return results
```

### Module-level Client Management

```python
_default_client: Optional[PinataClient] = None

def get_client() -> PinataClient:
    """Get or create the default client instance."""
    global _default_client
    if _default_client is None:
        _default_client = PinataClient()
    return _default_client

def set_client(client: PinataClient) -> None:
    """Set the default client instance."""
    global _default_client
    _default_client = client

def reset_client() -> None:
    """Reset the default client (useful for testing)."""
    global _default_client
    _default_client = None

```