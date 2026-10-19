---
title: Work out a CID from bytes as they arrive
status: doing
priority: normal
created: 2026-10-18
---

`src/stargazer/utils/cid.py` gets an incremental builder: fed a file's bytes
in pieces of any size, it gives the same CID `compute_cid` gives for the
whole file, and `compute_cid` becomes a wrapper over it, so there's still one
implementation of an asset's identity. Split out of ticket
`tus-browser-uploads`, whose private uploads work out the CID as the chunks
pass through the dashboard, and which can't start until ticket
`asset-manager-on-index` merges. Nothing open touches `cid.py`.

## Design

The builder hashes each full 256 KiB leaf as soon as its bytes are in, and
keeps the leaves' CIDs and sizes plus at most one partial leaf. The tree is
built from the leaves when asked for the CID, as `compute_cid` builds it
now. A 10 GB file is about 41,000 leaves, a few megabytes of state.

## Pieces

- [ ] Tests first, in `tests/utils/test_cid.py`: fed in uneven piece sizes
      (one byte, a prime number of bytes, 48 MiB), the builder gives the
      CIDs the existing tests pin: the empty file, one leaf, one node, two
      levels, and three levels.
- [ ] `CidBuilder` in `cid.py`, and `compute_cid` built on it.
- [ ] Docs: the CID section of `docs/architecture/types.md` if it describes
      how the CID is computed.
