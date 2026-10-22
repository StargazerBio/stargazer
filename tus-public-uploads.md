---
title: Public uploads over TUS, up to 10 GB
status: doing
priority: normal
created: 2026-10-21
---

The Pinata half of ticket `tus-browser-uploads`, split out when its store
half went to review as PR #72. Public uploads from the asset page still use a
Pinata signed URL, capped at 100 MB.

- [ ] A public upload's `POST /assets/tus` creates a Pinata TUS upload, each
      `PATCH` is passed on to it as one `PATCH`, and Pinata's CID has to equal
      `CidBuilder`'s, as `StorageClient.publish` checks.
- [ ] The form sends public uploads to `/assets/tus` too, and `/assets/sign`
      and the browser→Pinata upload go.
- [ ] Tests against a fake Pinata TUS endpoint: three chunks passed on in
      order, and a CID mismatch → an error and no record kept.
- [ ] Docs: the upload path in `docs/architecture/app.md` and
      `app_internals.md`, and the public limit on the form.
- [ ] Verify on Union with the test account: upload a public file over
      100 MB, see its CID in the Public tab, then delete it from Pinata.
      Publishing puts the file on the public network, so confirm with the
      user before running it.
