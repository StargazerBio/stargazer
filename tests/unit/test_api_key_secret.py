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


_SECRETS = (
    "from stargazer.config import STARGAZER_SECRETS as s; "
    "print(sorted((x.key, x.as_env_var) for x in s))"
)


def test_pods_call_the_cluster_with_the_named_key():
    """Every pod declares the named secret where flyte's in-cluster client reads it."""
    assert "('UNION_API_KEY', '_UNION_EAGER_API_KEY')" in _fresh(
        _SECRETS, STARGAZER_API_KEY_SECRET="UNION_API_KEY"
    )


def test_no_key_without_a_name():
    """A cluster without a login has no key to give, and a declared secret it lacks stops the pod."""
    assert "_UNION_EAGER_API_KEY" not in _fresh(_SECRETS)


def test_key_name_is_forwarded_into_pods():
    """A pod declares the same key for the tasks it starts."""
    code = (
        "from stargazer.config import STARGAZER_ENV_VARS as e; "
        "print(e.get('STARGAZER_API_KEY_SECRET'))"
    )
    assert _fresh(code, STARGAZER_API_KEY_SECRET="UNION_API_KEY") == "UNION_API_KEY"
