---
title: Delete the keys the injection era left
status: backlog
priority: high
created: 2026-10-24
---

Pods call Union as their project's own key since 2026-10-22 (ticket `org-wide-platform-key`), and the user deleted the org secret `EAGER_API_KEY-union-us-west-2` on 2026-10-24, so no pod can get the org key any more. What the injection era left still works for anyone holding a copy.

- [x] Delete the org key `393067446845621194` (`stargazerbio-EAGER_API_KEY-union-us-west-2`). It holds org-wide `contributor`, and every pod carried it until 2026-10-22, so a copy taken then still acts in every project.
- [x] Delete key `stargazer-flytesnacks` (`395974297992081529`, `contributor` on `flytesnacks`). It was made for image builds, which need no key now.
- [x] Remove the project secrets named `EAGER_API_KEY` in `u-pryce` and `flytesnacks` (three domains each). The `u-pryce` ones hold a deleted key, the `flytesnacks` ones `stargazer-flytesnacks`. Union's control plane hides that name and can't delete it, so they go from AWS Secrets Manager, an admin's step.
- [ ] Stop the org secret coming back. It doesn't stay gone: a job under `union-us-west-2-stargazerbio-adminflyterole` checks for it every four hours (CloudTrail `DescribeSecret` at :48:30 past 02, 06, 10, 14, 18 and 22 PDT). The user deleted it at 13:19 on 2026-10-24, and at 14:48:32 the job wrote it again, holding a newly minted key `396584044785060272` (`stargazerbio-EAGER_API_KEY-union-us-west-2`, org-wide `contributor`). Injection is still off, but a `u-pryce` task that declares the secret gets it (run `u8fsgfdjd4mcgm6srm5v`, checked set/unset only), so any user's code can act as org-wide `contributor` again. Only Union can stop the job. Meanwhile, on 2026-10-25 the user's admin login took `contributor` off key `396584044785060272`, leaving it no policies and the secret in place; a `u-pryce` task using the secret as its key was refused listing and starting runs in `u-pryce` and `flytesnacks` (run `up9cxnvcglq24nqmmfjt`). Check the key still holds nothing after the job's next pass.

Both keys were deleted on 2026-10-24 with `ApiKey.delete` under the user's admin login; the console listed neither. The org's keys are now Union's three (`uss-us-west-2-cli`, `uss-us-west-2-browser`, `stargazerbio-union-us-west-2-operator`), `stargazer-upgrade`, and `stargazer-u-pryce`. After the deletions a `u-pryce` task holding its project key still launched its child (run `uf424d77g8nrhl9sfnwb`). The `stargazer-flytesnacks` policy is left, assigned to nothing. The user is clearing the Secrets Manager secrets.
