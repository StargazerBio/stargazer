"""The public tier from a task pod, with the org's Pinata key mounted as a file.

A pod declaring `STARGAZER_SECRETS` has no `PINATA_JWT` in its environment,
yet its storage client has the public tier: it publishes a stored file to
Pinata and finds it there by a public query. The file is unpublished after.
"""

import json
import uuid

from . import pod_tasks


def test_a_pod_publishes_with_the_key_mounted_as_a_file(devbox_run):
    """The key reaches the SDK from the mounted file, and publishing works."""
    tag = uuid.uuid4().hex[:8]
    report = json.loads(devbox_run(pod_tasks.publish_round_trip, tag=tag).outputs()[0])

    assert report["key_in_env"] is False
    assert report["public_tier"] is True
    assert report["published"] == [report["stored"]]
    assert report["found"] == [report["stored"]]
