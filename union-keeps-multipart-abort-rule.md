---
title: Tell Union to keep the bucket's multipart abort rule
status: backlog
priority: normal
created: 2026-10-21
---

Resumable private uploads (ticket `tus-browser-uploads`) leave an unfinished multipart upload in `union-us-west-2-stargazerbio` when they're abandoned partway, and the pods' role can't abort it. The bucket's `abort_incomplete_multipart_uploads` rule (`AbortIncompleteMultipartUpload`, `DaysAfterInitiation: 1`, whole bucket) cleans them up. The admin added it on 2026-10-21, beside Union's `items_non_current_versions_expiration`.

Union's Terraform owns the bucket's lifecycle (CloudTrail: `union-ai-admin` set it on 2026-09-29), and `put-bucket-lifecycle-configuration` replaces every rule, so a re-apply of their Terraform would drop ours (inferred). Ask Union to add the rule to their configuration for this dataplane. Until then, read the bucket's lifecycle back with the read-only access after Union touches the dataplane (`aws s3api get-bucket-lifecycle-configuration --bucket union-us-west-2-stargazerbio`, `AWS_PROFILE=claude`).
