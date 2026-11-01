"""Tests for the project key secret (`STARGAZER_API_KEY_SECRET`).

Checked in a fresh interpreter, since `stargazer.config` resolves the
environment once at import.
"""

import os
import subprocess
import sys


def _fresh(code: str, **env: str) -> str:
    """Run `code` in a clean interpreter with `env` overlaid; return stdout."""
    base = {k: v for k, v in os.environ.items() if not k.startswith("STARGAZER_")}
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**base, **env},
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


_SECRETS_AND_ENV = (
    "from stargazer.config import STARGAZER_ENV_VARS as e, STARGAZER_SECRETS as s; "
    "print(sorted((x.key, x.as_env_var) for x in s)); "
    "print(e.get('STARGAZER_API_KEY_SECRET'))"
)


def test_a_named_key_is_declared_in_pods_and_forwarded_to_their_tasks():
    """Every pod declares the named secret where flyte's in-cluster client reads
    it, and passes the name on, so the tasks it starts declare it too."""
    secrets, forwarded = _fresh(
        _SECRETS_AND_ENV, STARGAZER_API_KEY_SECRET="UNION_API_KEY"
    ).splitlines()

    assert "('UNION_API_KEY', '_UNION_EAGER_API_KEY')" in secrets
    assert forwarded == "UNION_API_KEY"


def test_no_key_without_a_name():
    """A cluster without a login has no key to give, and a declared secret it lacks stops the pod."""
    secrets, forwarded = _fresh(_SECRETS_AND_ENV).splitlines()

    assert "_UNION_EAGER_API_KEY" not in secrets
    assert forwarded == "None"
