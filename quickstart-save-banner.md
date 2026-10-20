---
title: The stargazer image crashes on start without save_banner.html
status: doing
priority: high
created: 2026-10-20
---

`docker run -p 8080:8080 -it ghcr.io/stargazerbio/stargazer`, the Getting
Started quickstart, exits with code 1 a second after it starts. The proxy
reads `save_banner.html` from its own directory at import, and the image
doesn't have it:

```
File "/usr/local/lib/sg_proxy.py", line 108, in <module>
    _SAVE_BANNER_INJECTION = (Path(__file__).parent / "save_banner.html").read_bytes()
FileNotFoundError: [Errno 2] No such file or directory: '/usr/local/lib/save_banner.html'
```

`d46d3a3` added the banner and baked it into the hosted notebook image
(`notebook_app_img_recipe` in `app/per_notebook.py`), but not into the
`Dockerfile`, which copies only `terminal_overlay.html` beside the proxy.
The published `:latest` (built 2026-10-19) has the new proxy without the file
(measured: the container's log above, reproduced with the published image).

- [ ] Copy `app/save_banner.html` to `/usr/local/lib/` in the `Dockerfile`
- [ ] A unit test that the `Dockerfile` ships every file the proxy reads beside itself
- [ ] Build the image and run the quickstart command against it: the notebook serves on 8080 with the banner spliced in
- [ ] Republish `ghcr.io/stargazerbio/stargazer:latest` (multi-arch, `docs/guides/contributing.md`)
