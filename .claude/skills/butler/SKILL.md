---
name: butler
description: The routine repo sweep, run when the user says "butler". Pulls main and planning, cleans up merged PRs (reads their comments and turns follow-ups into tickets, or an urgent branch), answers review comments on open PRs with commits, rebases open PRs that conflict with main, and reports the board.
---

# Butler

The housekeeping the user would otherwise ask for one piece at a time. Run every step, in order, without stopping to ask, except where a step says to ask. The rules it applies are in `AGENTS.md` (Git Workflow, and Specs, Tickets and Reference Materials). This skill only sequences them.

Never merge a PR, push to `main`, post a PR comment or reply, or open a new PR. Never touch a worktree with uncommitted changes: another session is working there. List it in the report instead.

## 1. Pull

From the main checkout, with `MAIN=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")`:

- `git -C "$MAIN" fetch origin --prune`
- `git -C "$MAIN" pull`, if the checkout is on a clean `main`. If it isn't, say so in the report and don't pull.
- `git -C "$MAIN/planning" pull --rebase`

## 2. Take stock

- `gh pr list --state all --limit 30 --json number,title,state,headRefName,mergedAt,mergeStateStatus,updatedAt`. Leave out #22, the planning branch's standing draft.
- `git worktree list`, plus `git status --short` in each worktree.
- The tickets in `doing` and `review`: `grep -l '^status: \(doing\|review\)' "$MAIN"/planning/*.md`.

## 3. Merged PRs

Handle a merged PR if its branch still exists, locally or on origin, or its ticket isn't `done` yet. Once both are cleaned up, it has been handled and is skipped.

1. **Read everything left on it.**
   - `gh pr view <n> --json comments,reviews`
   - `gh api repos/{owner}/{repo}/pulls/<n>/comments`, for the inline review comments.
   - The comment left at merge is where the user puts follow-ups.
2. **Act on each follow-up.**
   - **Urgent** (a break in `main` or on the tenant, a bug users are hitting): write a ticket in `doing` and cut its worktree and branch from `origin/main`. Fix it after the sweep (step 6).
   - **Anything else:** write a ticket in `backlog`, or in `maybe` when it's floated as an idea rather than asked for. Grep `planning/` for it first, so a sweep run twice doesn't write it twice.
3. **Close the PR's ticket.**
   - Set `status: done` and add an `## Outcome`: what shipped (PR and commit), how it was verified (from the ticket and the PR body), and what's left, naming the new tickets.
   - Take it out of every other ticket's `blocked_by`, dropping the key once the list is empty. Move a ticket it held back to `next` if it's next in line.
4. **Remove its worktree and branch.**
   - `git worktree remove .claude/worktrees/<slug>`
   - `git branch -D <branch>`
   - `git push origin --delete <branch>`
   - If the worktree is dirty, skip this step and report it.

Commit the ticket edits on `planning`, naming only your own files. Push them, then `git -C "$MAIN" pull` again.

If any PR handled here changed the `Dockerfile`, publish the `stargazer` image from `$MAIN` after that pull, once per sweep, both platforms (`AGENTS.md` → Git Workflow).

A PR that was closed without merging keeps its branch and worktree. Report it and ask what to do.

## 4. Open PRs

Do these in each open PR's worktree. If it has none, add one for the existing branch with `git worktree add .claude/worktrees/<slug> <branch>`, and link the local state per `AGENTS.md`. Skip a dirty worktree.

1. **Answer review feedback with commits.**
   - Read the comments, reviews and inline comments.
   - A comment is unanswered if it's newer than the branch's last commit, or no later commit message addresses it.
   - Answer each one with commits, following the Dev Process rules: tests first, ruff, and checking it on its real surface when behavior changes.
   - Push, then rewrite the PR body from the branch's current state (`gh pr edit <n> --body-file`).
   - A question, rather than a change request, gets its answer in the report, not on GitHub.
   - Feedback that redesigns the change: ask before starting it.
2. **Rebase a PR that conflicts.**
   - Only when `mergeStateStatus` is `DIRTY`. `BEHIND` alone merges fine.
   - `git rebase origin/main` and resolve the conflicts. Run the unit tier (`uv run --all-extras pytest`), then `git push --force-with-lease`.
   - If resolving a conflict means choosing between two behaviors, ask.
3. **Check the PR's ticket.** It should be in `review` with `pr: <n>`. Fix it on `planning` if it isn't.

## 5. Report

Keep it short, one line per item, with each claim's evidence:

- **Merged and cleaned up:** each PR, and the tickets its comments became.
- **Published:** the `stargazer` image, if a merged PR changed the `Dockerfile`, with the digest the push printed.
- **Open PRs:**
  - each one's state: feedback answered (with the commits), rebased, or waiting on review;
  - questions from review comments, with their answers;
  - PRs that conflict with each other.
- **Left alone:**
  - dirty worktrees;
  - closed PRs that weren't merged;
  - worktrees with no PR and no commits for days. Ask whether to remove them;
  - a main checkout that wasn't on a clean `main`.
- **The board:** the `next` tickets, highest priority first, skipping blocked ones. Say which you'd take next.

## 6. Urgent follow-ups

If step 3 cut an urgent branch, fix it now with the `bug-fix` skill. When it's verified, stop before the push and the PR. The user says when to open it.
