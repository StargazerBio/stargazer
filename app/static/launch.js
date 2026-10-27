// Launching notebooks, shared by the dashboard's workspace tiles and the
// asset explorer's notebook cards. A launchable notebook is a `.launch-group`
// holding a `.launch-row` per mode, each with a `form.launch-form` whose
// hidden inputs name its slug, section and mode. Handlers are delegated, so
// a tile or card added after load works with no re-binding.

// Clear a row's extras and hide its Edit/Run button, and the other mode's.
// A notebook runs in exactly one modality at a time, so a running (or
// building) notebook offers no path to a second pod. Stop restores both.
// See docs/architecture/app.md. Don't hide a sibling that's itself already
// launched. Returns the row's mode.
function holdLaunch(row, form) {
    row.querySelectorAll(".launched-extra").forEach((el) => el.remove());
    const mode = form.querySelector('input[name="mode"]').value;
    row.hidden = false;
    form.hidden = true;
    row.closest(".launch-group")
        .querySelectorAll(".launch-row")
        .forEach((r) => {
            if (r !== row && !r.querySelector(".launched-extra"))
                r.hidden = true;
        });
    return mode;
}

// Restore every mode's Edit/Run button (both the hidden sibling row and
// this row's own hidden form), clearing this row's extras.
function releaseLaunch(row) {
    row.querySelectorAll(".launched-extra").forEach((el) => el.remove());
    row.closest(".launch-group")
        .querySelectorAll(".launch-row")
        .forEach((r) => {
            r.hidden = false;
            r.querySelectorAll("form.launch-form").forEach((f) => {
                f.hidden = false;
            });
        });
}

// Show a notebook whose image is building: a link to the build run in
// place of Edit/Run, until /launch/status reports the pod running (then
// Open+Stop) or the build failed (then Edit/Run again, and the reason).
function showBuilding(row, form, buildUrl) {
    holdLaunch(row, form);
    const link = document.createElement("a");
    link.href = buildUrl;
    link.className = "btn btn-muted launched-extra";
    link.innerHTML = '<span class="spinner-inline"></span> Building image';
    link.title =
        "This notebook's image is building. It opens here when it's ready.";
    link.target = "_blank";
    link.rel = "noopener";
    row.appendChild(link);
    watchBuild(row, form);
}

// The build polls running, by `slug:mode`, each holding the row and form
// its outcome goes to.
const buildWatches = new Map();

// Poll /launch/status for a building notebook. Once its build is no longer
// reported, the pod can take a moment to show as running, so keep looking
// for a few minutes before giving the buttons back. One poll runs per
// notebook and mode: a card re-rendered while it builds hands the running
// poll its new row and form rather than starting another.
async function watchBuild(row, form) {
    const slug = form.querySelector('input[name="slug"]').value;
    const mode = form.querySelector('input[name="mode"]').value;
    const key = slug + ":" + mode;
    const polling = buildWatches.has(key);
    buildWatches.set(key, { row, form });
    if (polling) return;
    const mine = (e) => e.slug === slug && e.mode === mode;
    const target = () => buildWatches.get(key);
    try {
        let misses = 0;
        while (misses < 60) {
            await new Promise((r) => setTimeout(r, 5000));
            let data;
            try {
                data = await fetchJSON("/launch/status");
            } catch (_) {
                continue;
            }
            if ((data.building || []).some(mine)) continue;
            const running = (data.running || []).find(mine);
            if (running) {
                showLaunched(target().row, target().form, running.url, true);
                return;
            }
            const failed = (data.failed || []).find(mine);
            if (failed) {
                releaseLaunch(target().row);
                alert("Launch failed: " + failed.error);
                return;
            }
            misses += 1;
        }
        releaseLaunch(target().row);
    } finally {
        buildWatches.delete(key);
    }
}

// Append an "Open" link + "Stop" button beside a launched notebook's
// Edit/Run button. The original button stays so the notebook can be
// re-launched; the extras are tagged `.launched-extra` so a re-launch or
// a Stop can clear them without disturbing the form.
function showLaunched(row, form, url, fresh) {
    const mode = holdLaunch(row, form);

    const open = document.createElement("a");
    open.href = url;
    open.className = "btn btn-ready launched-extra";
    open.textContent =
        mode === "run" ? "Open: Run Mode" : "Open: Edit Mode";
    open.target = "_blank";
    open.rel = "noopener";
    // A hydrated URL (from /launch/status on load) can point at a pod
    // that's scaled to zero or was served before a redeploy. Re-serve
    // through /launch on click to reconcile it to the current spec (a
    // no-op for a warm, current pod), then navigate. The tab is opened
    // synchronously in the click handler so the await can't cost us the
    // user-gesture and trip the popup blocker.
    if (!fresh) {
        open.addEventListener("click", (e) => {
            e.preventDefault();
            const win = window.open("", "_blank");
            if (win) win.opener = null;
            reopenHydrated(open, form, win);
        });
    }

    const stop = document.createElement("button");
    stop.type = "button";
    stop.className = "btn btn-stop launched-extra";
    stop.textContent = "Stop";
    stop.addEventListener("click", () => stopNotebook(stop, row, form));

    row.appendChild(open);
    row.appendChild(stop);
}

// Re-open a hydrated notebook: re-serve it through /launch, then point
// the pre-opened tab at it. The notebook shows its own starting page
// until it's ready, so there's nothing to wait for here.
async function reopenHydrated(openBtn, form, win) {
    const label = openBtn.textContent;
    openBtn.style.pointerEvents = "none";
    openBtn.textContent = "Starting…";
    try {
        const payload = await requestLaunch(new FormData(form));
        if (payload.building) {
            if (win) win.close();
            showBuilding(
                openBtn.closest(".launch-row"),
                form,
                payload.building,
            );
            return;
        }
        if (win) win.location = payload.url;
        else window.open(payload.url, "_blank", "noopener");
    } catch (err) {
        if (win) win.close();
        alert("Open failed: " + err.message);
    } finally {
        openBtn.textContent = label;
        openBtn.style.pointerEvents = "";
    }
}

// Deactivate a running per-notebook pod. Reuses the launch form's hidden
// slug/section/mode inputs so /stop targets the same (slug, mode) env.
async function stopNotebook(stopBtn, row, form) {
    stopBtn.disabled = true;
    stopBtn.innerHTML = '<span class="spinner-inline"></span>';
    try {
        const resp = await fetch("/stop", {
            method: "POST",
            body: new FormData(form),
            headers: { Accept: "application/json" },
        });
        if (!resp.ok) {
            const txt = await resp.text();
            throw new Error(
                "stop HTTP " + resp.status + ": " + txt.slice(0, 200),
            );
        }
        releaseLaunch(row);
    } catch (err) {
        stopBtn.disabled = false;
        stopBtn.textContent = "Stop";
        alert("Stop failed: " + err.message);
    }
}

// Fetch `url` as JSON and return the payload; throw the server's error
// message (or the HTTP status) on a non-2xx. `options` are fetch's:
// `method` and `body`.
async function fetchJSON(url, options = {}) {
    const resp = await fetch(url, {
        ...options,
        headers: { Accept: "application/json" },
    });
    const payload = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(payload.error || "HTTP " + resp.status);
    return payload;
}

// POST /launch with the given FormData and return its payload: `url`, the
// per-notebook URL, or `building`, the image build run's URL while the
// image builds. Throws with a useful message on any non-JSON / error
// response.
// Shared by `handleLaunch` (the Edit/Run buttons) and `reopenHydrated`.
async function requestLaunch(formData) {
    const resp = await fetch("/launch", {
        method: "POST",
        body: formData,
        headers: { Accept: "application/json" },
    });
    // Read once as text so we can surface the body even when the server
    // returned HTML (e.g. an error page, or a 302 fetch silently followed).
    const rawBody = await resp.text();
    const ctype = resp.headers.get("content-type") || "";
    if (!ctype.includes("application/json")) {
        const snippet = rawBody.slice(0, 200).replace(/\s+/g, " ");
        throw new Error(
            "launch HTTP " + resp.status + " (non-JSON): " + snippet,
        );
    }
    let payload;
    try {
        payload = JSON.parse(rawBody);
    } catch (_) {
        throw new Error(
            "launch JSON parse failed: " + rawBody.slice(0, 200),
        );
    }
    if (!resp.ok) {
        throw new Error(
            "launch HTTP " +
                resp.status +
                ": " +
                (payload.error || rawBody),
        );
    }
    return payload;
}

// Run the launch flow for one Edit/Run button: spinner → /launch → Open+Stop.
// The notebook shows its own starting page while it warms up.
async function handleLaunch(form) {
    const button = form.querySelector('button[type="submit"]');
    const row = form.closest(".launch-row");
    const originalLabel = button.textContent;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-inline"></span>';
    try {
        const payload = await requestLaunch(new FormData(form));
        button.disabled = false;
        button.textContent = originalLabel;
        if (payload.building) showBuilding(row, form, payload.building);
        else showLaunched(row, form, payload.url, true);
    } catch (err) {
        button.textContent = originalLabel;
        button.disabled = false;
        alert("Launch failed: " + err.message);
    }
}

document.addEventListener("submit", (e) => {
    const form = e.target.closest("form.launch-form");
    if (!form) return;
    e.preventDefault();
    handleLaunch(form);
});

// Copy a built-in workflow or a public notebook into the editable Workspace.
// POST, then drop the returned workspace tile in before the New-notebook tile.
async function copyToWorkspace(btn) {
    const slug = btn.dataset.copySlug;
    const section = btn.dataset.copySection;
    const restore = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-inline"></span>';
    try {
        const payload = await fetchJSON("/workspace/copy", {
            method: "POST",
            body: new URLSearchParams({ slug, section }),
        });
        const createTile = document.getElementById("create-tile");
        if (createTile && payload.tile_html)
            createTile.insertAdjacentHTML("beforebegin", payload.tile_html);
        btn.innerHTML = "✓ Copied";
        setTimeout(() => {
            btn.innerHTML = restore;
            btn.disabled = false;
        }, 1500);
    } catch (err) {
        btn.innerHTML = restore;
        btn.disabled = false;
        alert("Copy failed: " + err.message);
    }
}

document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-copy-slug]");
    if (!btn) return;
    e.preventDefault();
    copyToWorkspace(btn);
});

// Find the launch form under `root` for slug + mode (both are hidden inputs).
function findLaunchForm(root, slug, mode) {
    return Array.from(root.querySelectorAll("form.launch-form")).find(
        (f) =>
            f.querySelector('input[name="slug"]').value === slug &&
            f.querySelector('input[name="mode"]').value === mode,
    );
}

// Ask which notebooks are already running and flip their launch forms under
// `root` straight to Open+Stop — no re-launch, no spin. Authoritative +
// survives dashboard restarts (the server queries Flyte, not in-memory
// state). The page runs it on load, and the explorer for each notebook card.
async function hydrateLaunches(root) {
    let data;
    try {
        const resp = await fetch("/launch/status", {
            headers: { Accept: "application/json" },
        });
        if (!resp.ok) return;
        data = await resp.json();
    } catch (_) {
        return;
    }
    for (const { slug, mode, url } of data.running || []) {
        const form = findLaunchForm(root, slug, mode);
        if (form)
            showLaunched(form.closest(".launch-row"), form, url, false);
    }
    for (const { slug, mode, url } of data.building || []) {
        const form = findLaunchForm(root, slug, mode);
        if (form) showBuilding(form.closest(".launch-row"), form, url);
    }
}

