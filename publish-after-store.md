---
title: publish-after-store
status: maybe
priority: normal
created: 2026-11-16
---

The dashboard's upload form sends a file to one of two places, and each has its own resumable path in infra's `app/assets.py` (687 lines, 2026-11-16): to the user's store as a multipart upload, or relayed piece by piece to a TUS upload of Pinata's, with the CID worked out alongside and the Pinata file deleted if the two differ. The SDK's `PinataClient` exposes `tus_create` and `tus_patch` publicly for that relay.

`StorageClient.publish(cid)` already moves a stored asset to the public tier with its companions, checks the metadata limits for the whole set first, and handles files over 100 MB. So a public upload could be: store it, then Publish. One upload path, and a file that goes public always has a private copy and its companions with it.

What would go: the Private/Public choice on the upload form, `_patch_public` and the Pinata half of `_TusUpload`, `tus_create`/`tus_patch` as public methods, and `STARGAZER_PUBLIC_ASSETS=off`'s upload branch. What's needed: a Publish action on an owned asset's card in the explorer (the MCP server has `publish_file`; the dashboard has no button for it).

To settle:

- Publishing reads the file back from the store and sends it from the dashboard pod, so a 10 GB public file passes through the pod's disk, which the relay avoids. Whether that's acceptable, or publish should stream.
- Whether anyone uploads public-only on purpose, to keep a file out of their own store's bill.

Related: [[board]], [[private-pinata-key]], [[retire-public-notebooks]].
