---
title: simpler-companions
status: later
priority: low
created: 2026-11-16
---

`StorageClient.companions(cid)` picks an asset's companions from three places in order: the user's own rows, public ones the caller published, then public ones from whoever published the parent, one per filename (`utils/storage.py`, read 2026-11-16). The middle step covers one case: a companion the caller published earlier and no longer has in their store. It costs a second owner in the loop and a paragraph in every doc that explains fetching.

Two sources would say the same thing in a sentence: your own companions, then the publisher's. A caller who deleted their copy of a companion they published gets it back only when they also published the parent, which is the usual way a reference goes public (`publish()` sends the set together).

To settle: whether the middle step was added for a case that came up, and if so which. Its tests would say; they weren't read for this ticket.

Related: [[board]], [[asset-storage-index]].
