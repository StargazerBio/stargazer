---
name: blast-radius
description: Find what a Stargazer change could break beyond its own diff, and prove the one fact it is safe because of by running real code. Use for "blast radius of X", "what could this break", or a small diff touching assets, keyvalues, marshalling, Flyte images, or the app tier that you don't fully trust.
---

# Blast radius

Find what a change breaks somewhere else, before it ships. Listing callers is not the job, grep does that in a second. The job is the breakage grep won't show you.

Adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack)'s blast-radius skill (MIT).

## Don't trust your own writeup

A writeup that sounds right reads as convincing whether or not it's true. Find the one or two facts the change's safety depends on and prove them by running code.

For each fact, get it as far down this ladder as is cheap, and say where it stopped:

1. You said so. Worthless on its own.
2. You pointed at the line. A real `file:line`, or the library's own source.
3. You showed the bad case can't happen. You walked the failure step by step and it doesn't reach.
4. You ran it. A script or test that calls the real code and fails loudly if you're wrong.
5. You reproduced it in the running system (a local Flyte run, the devbox, the notebook, the app).

Step 4 is usually one small script in `scratch/` that imports the real module and calls the exact function you're worried about.

## Steps

1. **Read the change.** The diff, the symbols it adds, changes, and deletes, and what now behaves differently, including what the diff doesn't spell out.
2. **Find the one fact it's safe because of.** Most risky-looking changes are safe because of one fact. Find it. If it holds, most risky cases clear at once. Spend your time here, not on a long list of maybes.
3. **Look where grep stops.** In Stargazer that usually means:
   - **Stored metadata.** `Asset.to_keyvalues()` / `from_keyvalues()` output lives in Pinata and local storage. Renaming or retyping a field leaves old records unreadable or unqueryable. Check `query_files` against existing data, not just new data.
   - **Wire formats.** `marshal.py` shapes what MCP clients and the in-notebook assistant see. The registry in `registry.py` shapes what they can discover.
   - **Flyte images and environments.** A new import or CLI tool must exist in the `flyte.Image` of the env the task runs in (`config.py`). Code bundles ship only `.py` files, and bundled code can shadow image-baked packages (see `devbox_workarounds.md`).
   - **Notebooks.** Notebooks import SDK functions by name, and `@app.function` exports are imported across notebooks. A rename breaks them without any test in `tests/tasks/` noticing.
   - **Third-party behavior.** Read the installed library source in `.venv/`, not your memory of its API.
4. **Rate each risk honestly.** A realistic chance of happening and a real cost if it does. Keep confirmed risks. List checked-and-cleared ones separately. Cite real `file:line`. A search that finds nothing is still an answer. Never invent a caller or an API.
5. **Prove the one fact.** Write the script or test, run it, and paste what happened.

## Reply

- **What it does.** What changed, including the non-obvious part.
- **The one fact it's safe because of.** State it, the ladder step you reached, and the proof. If you couldn't prove it, write unproven.
- **Risks.** Each names how it breaks, the `file:line`, likelihood and cost, and how to check. Paste the proof for the ones that matter.
- **Cleared.** What you checked and why it's fine.
- **Before you merge.** The cheapest test or repro that would catch the real bug, including the script you wrote.
