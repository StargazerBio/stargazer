# Stargazer CLI Tools

This directory contains command-line tools for managing Stargazer data and IPFS uploads.

## Available Tools

### upload_to_pinata.py

Generic file uploader for Pinata IPFS storage with custom metadata support.

**Features:**
- Upload any file(s) to Pinata IPFS
- Support for JSON metadata or key=value pairs
- Automatically updates `tests/config.py` with CIDs (optional)
- Upload multiple files with the same metadata
- Flexible metadata specification

**Usage:**

```bash
# Upload a single file with JSON metadata
python cli/upload_to_pinata.py /path/to/file.fa \
  --metadata '{"type": "reference", "build": "GRCh38", "env": "test"}'

# Upload using key=value metadata pairs (simpler syntax)
python cli/upload_to_pinata.py myfile.txt \
  -m type=data \
  -m env=test \
  -m version=1.0

# Upload and automatically update tests/config.py
python cli/upload_to_pinata.py tests/fixtures/GRCh38_TP53.fa \
  -m type=reference -m build=GRCh38 -m region=TP53 -m env=test \
  --update-config

# Upload multiple files with the same metadata
python cli/upload_to_pinata.py file1.txt file2.txt file3.txt \
  --metadata '{"type": "test", "env": "dev"}'

# Combine JSON and key=value (key=value takes precedence)
python cli/upload_to_pinata.py data.csv \
  --metadata '{"type": "dataset"}' \
  -m env=production -m version=2.0
```

**Metadata Formats:**

1. **JSON format** (`--metadata`):
   ```bash
   --metadata '{"type": "reference", "build": "GRCh38", "env": "test"}'
   ```

2. **Key=value pairs** (`-m` or `--meta`):
   ```bash
   -m type=reference -m build=GRCh38 -m env=test
   ```

3. **Combined** (key=value overrides JSON):
   ```bash
   --metadata '{"type": "reference"}' -m env=production
   ```

**Options:**

- `files` - One or more file paths to upload (required)
- `--metadata` / `--keyvalues` - Metadata as JSON string
- `-m KEY=VALUE` / `--meta KEY=VALUE` - Metadata as key=value pairs (repeatable)
- `--update-config` - Update tests/config.py with uploaded CIDs
- `--config-path PATH` - Custom path to config file (default: tests/config.py)

**Requirements:**
- `PINATA_JWT` environment variable must be set with your Pinata API key

**Example Output:**
```
Uploading 1 file(s) to Pinata...

Uploading: tests/fixtures/GRCh38_TP53.fa
  Size: 39,745 bytes
  Metadata: {'type': 'reference', 'build': 'GRCh38', 'region': 'TP53', 'env': 'test'}
  ✓ Success!
    CID: bafkreib6vj3os7l4lqqytaw5vju46iorcknttfiwfnlbizjcqn7xd5hrvy
    ID: 019b56fb-605b-79a6-96f5-571cdee82c9a

============================================================
Upload Summary: 1/1 files uploaded
============================================================
```

## Setting up Pinata API Key

Get your JWT token from [Pinata Dashboard](https://app.pinata.cloud/):

```bash
export PINATA_JWT='your_jwt_token_here'
```

## Common Use Cases

### Uploading Test Fixtures

Upload all TP53 reference files for testing:

```bash
# Upload main reference file
python cli/upload_to_pinata.py tests/fixtures/GRCh38_TP53.fa \
  -m type=reference -m build=GRCh38 -m region=TP53 -m env=test \
  --update-config

# Upload index files
python cli/upload_to_pinata.py tests/fixtures/GRCh38_TP53.fa.fai \
  -m type=reference -m build=GRCh38 -m region=TP53 -m tool=samtools_faidx -m env=test \
  --update-config

python cli/upload_to_pinata.py \
  tests/fixtures/GRCh38_TP53.fa.{amb,ann,bwt,pac,sa} \
  -m type=reference -m build=GRCh38 -m region=TP53 -m tool=bwa_index -m env=test \
  --update-config
```

### Uploading Analysis Results

```bash
python cli/upload_to_pinata.py results/variant_calls.vcf \
  -m type=results -m analysis=variant_calling -m sample=NA12829 -m date=2025-12-25
```

### Uploading Documentation

```bash
python cli/upload_to_pinata.py docs/README.md \
  --metadata '{"type": "documentation", "version": "1.0", "format": "markdown"}'
```
