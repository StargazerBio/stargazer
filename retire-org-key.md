---
title: Delete the keys the injection era left
status: backlog
priority: high
created: 2026-10-24
---

Pods call Union as their project's own key since 2026-10-22 (ticket `org-wide-platform-key`), and the user deleted the org secret `EAGER_API_KEY-union-us-west-2` on 2026-10-24, so no pod can get the org key any more. What the injection era left still works for anyone holding a copy.

- [ ] Delete the org key `393067446845621194` (`stargazerbio-EAGER_API_KEY-union-us-west-2`). It holds org-wide `contributor`, and every pod carried it until 2026-10-22, so a copy taken then still acts in every project.
- [ ] Delete key `stargazer-flytesnacks` (`395974297992081529`, `contributor` on `flytesnacks`). It was made for image builds, which need no key now.
- [ ] Remove the project secrets named `EAGER_API_KEY` in `u-pryce` and `flytesnacks` (three domains each). The `u-pryce` ones hold a deleted key, the `flytesnacks` ones `stargazer-flytesnacks`. Union's control plane hides that name and can't delete it, so they go from AWS Secrets Manager, an admin's step.
- [ ] Check the org secret stays gone. After its 2026-10-20 delete it came back the same day through the control plane, which doesn't record who asked. While it's gone, a task declaring it is refused at admission (probe run `u2wqkphhwpqw6x9nz44c`, 2026-10-24).

The admin console lists neither key; `ApiKey.delete(client_id)` under an admin login deletes them.
