---
title: reonboard-tenant-check
status: done
priority: normal
created: 2026-10-28
pr: 11
---

Ticket `reonboard-unarchive` made onboarding unarchive a returning user's project, and it was checked against infra's fakes only. On the tenant, with a second address (offboarding the test account takes down its dashboard): onboard, upload an asset, offboard, onboard, and the dashboard lists the asset.

The open question is DSQL. Offboarding deletes the index's IAM role, and onboarding recreates it under the same ARN. `_ensure_iam_mapping` then finds the old `sys.iam_pg_role_mappings` row with that ARN and skips `AWS IAM GRANT`. If DSQL matches the mapping by ARN, the pods log in. If it ties the mapping to the role's unique id, as IAM trust policies do, they're refused, and offboarding should `AWS IAM REVOKE` the mapping along with deleting the role.

## Findings (2026-10-28, infra StargazerBio/infra#11; `pr: 11` is infra's)

Run with the test account itself, not a second address.

- [x] DSQL keeps a mapping for the role it was granted to, not for its ARN
      (measured): with the role recreated under the same ARN and the old
      mapping kept, the dashboard's index login is refused (`access
      denied`), still failing at 3 minutes. Onboarding now revokes and grants again
      when it creates the role.
- [x] The test account was labeled on two projects, `u-pryce` and an
      older `u-387300641116005877`, and re-onboarding unarchived the wrong
      one (empty index). Onboarding and offboarding now refuse a user
      labeled on more than one. `u-387300641116005877`'s labels were
      replaced with `retired-stargazer-subject: 387300641116005877`.
- [x] From the branch: offboard then onboard brought back the same 80
      assets (same CIDs), and a keyvalue edit was stored and read back.

## Verification recipe

Needs the admin's AWS profile for `stargazer-users`; the rest runs as the
test account.

1. Deploy the test account's dashboard (`verify-dashboard` skill,
   `union_dashboard.py deploy`), and from its page record
   `fetch("/assets/list?source=mine")`: the count and a few CIDs.
2. The admin runs, from the branch's checkout,
   `stargazer-users offboard --email pryce@stargazer.bio`, then
   `stargazer-users onboard --email pryce@stargazer.bio --first-name Pryce --last-name Turner`.
3. Reload the dashboard: the same list comes back (not `[]`, not a 500).
   A 500 is the index login refused; the dashboard's logs (console, app,
   Logs tab) show `access denied`.
4. Edit one row's keyvalues with `POST /assets/update` (`network:
   "private"`) and read it back from the list.
5. `union_dashboard.py teardown`: no active app, no live run.

## Outcome

Shipped in StargazerBio/infra#11 (merge `13f3074`): a user labeled on more
than one project is refused instead of given the first, and a role that
onboarding creates gets its DSQL mapping revoked and granted again. Verified
on the tenant with the test account: offboard then onboard from the branch
brought back the same 80 assets and stored a keyvalue edit; 332 tests pass.
Left: nothing. `u-387300641116005877` stays archived with only a
`retired-stargazer-subject` label.
