---
title: public-companion-owners
status: done
priority: normal
created: 2026-10-21
pr: 75
---

The two commits from ticket `public-companion-curation` that didn't make it into PR #74's merge, cherry-picked unchanged onto branch `fix/public-companion-owners`:

- **Every public record needs an owner.** `PinataClient` refuses an upload, signed upload URL or metadata edit whose keyvalues have no `_owner`, before any request, and `query` and `get` skip public files with none. Anyone with the key can upload straight to Pinata, so the read side is what holds.
- **`fetch()` takes the caller's public companions too.** `StorageClient.companions` returns the user's own rows, then public companions the caller published, then the parent publisher's, skipping a name already taken. Anyone else's are left out.

## Pieces

- [x] Cherry-pick `749b9aa` and `fbd956f` (`git range-diff`: identical)
- [x] The pinata tier: its fixture sets `STARGAZER_OWNER`, and the signed-URL test passes `_owner`. Seven of its tests failed on the first commit without it.
- [x] Check that the read filter hides nothing: the public network on the tier's Pinata account holds 6 files, all with `_owner` (measured 2026-10-21)
- [x] PR #75

## Verification so far

Unit tier 551 passed; pinata tier 14 passed (7 failed before the fixture fix, 14 passed on `main`).

## Outcome

Shipped in PR #75 (merge `0cdc32d`): every public record needs an `_owner` (unowned writes refused, unowned files skipped on read), `fetch()` takes the caller's public companions before the publisher's, and the pinata tier uploads as an owner. Verified with the unit tier (551 passed) and the pinata tier against the real API (14 passed); the tier's Pinata account held 6 public files, all owned. Not driven live: `fetch()` choosing between publishers, since the public tier holds no companions. No comments on the PR; nothing left.
