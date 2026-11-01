---
title: incremental-cid
status: done
priority: normal
created: 2026-10-18
pr: 45
---

`src/stargazer/utils/cid.py` gets an incremental builder: fed a file's bytes
in pieces of any size, it gives the same CID `compute_cid` gives for the
whole file, and `compute_cid` becomes a wrapper over it, so there's still one
implementation of an asset's identity. Split out of ticket
[[tus-browser-uploads]], whose private uploads work out the CID as the chunks
pass through the dashboard, and which can't start until ticket
[[asset-manager-on-index]] merges. Nothing open touches `cid.py`.

## Design

The builder hashes each full 256 KiB leaf as soon as its bytes are in, and
keeps the leaves' CIDs and sizes plus at most one partial leaf. The tree is
built from the leaves when asked for the CID, as `compute_cid` builds it
now. A 10 GB file is about 41,000 leaves, a few megabytes of state.

## Pieces

- [x] Tests first, in `tests/utils/test_cid.py`: fed in uneven piece sizes
      (one byte, a prime number of bytes, 48 MiB), the builder gives the
      CIDs the existing tests pin: the empty file, one leaf, one node, two
      levels, and three levels.
- [x] `CidBuilder` in `cid.py`, and `compute_cid` built on it.
- [x] Docs: no architecture doc describes the computation beyond
      `configuration.md`'s identity paragraph, which still holds. The module
      docstring, rendered in the API reference, covers the builder.

## Verified (2026-10-18)

- **Unit tier:** 465 passed. The 10 new tests failed against a stub first.
- **Pinata tier:** `tests/pinata/test_cid_drift.py` passed 4 of 4 against the
  real API: one block, three chunks, two levels, and the resumable upload
  past 100 MB.
- **Speed on a 1 GiB random file:** `main`'s `compute_cid` took 0.51 s and
  0.49 s, the branch's 0.48 s and 0.48 s, and the builder fed 48 MiB pieces
  0.55 s. All gave the same CID.

## Outcome

Merged in #45 (2026-10-18). `CidBuilder` works out a file's CID from bytes
fed in pieces of any size, and `compute_cid` is the builder fed a file.
Verified with the unit tier, the Pinata drift test against the real API
(4 of 4), and a 1 GiB timing at the same speed as before (above).

Left: nothing uses the builder yet. Ticket [[tus-browser-uploads]] will, to
work out an upload's CID as its chunks pass through the dashboard.
