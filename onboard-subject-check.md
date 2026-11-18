---
title: onboard-subject-check
status: done
priority: high
created: 2026-11-16
---

Onboarding creates a user with `User.create` and keys their project, policy and dashboard on the subject it returns. Unverified: that this is the subject the user's first GitHub sign-in arrives with (`X-User-Subject`). It's the one open check left in ticket [[per-user-dashboard]], and it has to hold before anyone new is onboarded: if the two differ, a new user's sign-in matches no dashboard.

Check it on the tenant with a real second address (not the test account): onboard it, sign in as it for the first time, and compare the dashboard's `X-User-Subject` with what onboarding stored. If it differs, onboarding has to bind the subject at first sign-in instead.

## Verification recipe

The only step that happens once is the first sign-in. Everything it might change can still be read afterwards: the member's subject by email (`User.listall(email=…)`), whether a second member record appeared, and the token `sub` at any later visit. So the run splits the invite from provisioning, and nothing is keyed on a subject until after the first sign-in:

1. Before: `User.listall(email=<address>)` returns nothing. Save the output.
2. Invite only, no project: `User.create(...)`. Save the whole record it returns, subject S0 included.
3. The user accepts Union's invite email and signs in with GitHub. At this point nothing of Stargazer's depends on S0, so a mismatch breaks nothing.
4. After: `User.listall(email=<address>)`. Save every record: subject S1, and how many there are.
5. Run `stargazer-users onboard` for the address. It finds the member by email, so it keys everything on S1 whatever happened. Then the user signs in to the dashboard, which must let them in: its owner check compares S1 with the token's `sub`.

S0 = S1, with one record: onboarding as it is today is safe, and the ticket is done. S0 ≠ S1, or two records: onboarding has to bind the subject at first sign-in, and step 5 has already left this user working.

Check before step 2: the address invited must be the one Union will see from the GitHub account (its primary verified email). Unchecked how Union matches the two.

## Run (2026-11-18, lily@stargazer.bio)

- [x] Step 1, 00:15 UTC: `User.listall(email="lily@stargazer.bio")` returned no records. Control: the same call for `pryce@stargazer.bio` returned its one record (`387300641116005877`), so the filter works.
- [x] Step 2, 00:16 UTC: `User.create(first_name="Lily", last_name="Adastra", email=…)` returned subject S0 = `400077837203186151` (handle `u-db862b4598dbbbc6f278c18dfc0b62f6`). Listed right after: one record, S0.
- [x] Step 3, about 02:49 UTC: Lily accepted Union's invite and signed in with GitHub, in a fresh browser.
- [x] Step 4, 02:50 UTC: one record for the address, subject S1 = `400077837203186151` = S0. The whole org has 5 members and none other is newer than S0, so the sign-in didn't create a second member under another email. **The subject `User.create` returns is the one the first sign-in keeps.**
- [x] Step 5a: `stargazer-users onboard` (run by the user). Read back: project `u-lily` labeled `union-subject=400077837203186151`, policy `stargazer-u-lily` assigned to that subject, and the dashboard `ACTIVE` at `https://u-lily.apps.stargazerbio.us-west-2.unionai.cloud` with `SG_OWNER_SUBJECT=400077837203186151`.
- [x] Step 5b: Lily opened her dashboard and got in (reported by the user, 2026-11-18).

## Outcome

Onboarding as it is is safe for new users: the subject `User.create` returns at invite is the one the user's first GitHub sign-in keeps, and the dashboard onboarding keys on it lets them in. Measured end to end with `lily@stargazer.bio` (subject `400077837203186151`, project `u-lily`), above. No code changed. Users need a public email on their GitHub profile (https://github.com/settings/profile), and it has to be the address invited; Getting Started says so.

Related: [[board]], [[per-user-dashboard]], [[self-serve-onboarding]], [[reonboard-tenant-check]].
