"""Tests for the task environment factories: what every environment shares."""

from pathlib import Path

import flyte

from stargazer import config

GATK_ENV = Path(config.__file__).parent / "tasks" / "gatk" / "env.py"
TEMPLATE = Path(config.__file__).parent / "notebooks" / "templates" / "basic.py"


def _secret_keys(env: flyte.TaskEnvironment) -> list[str]:
    """The keys of the secrets `env` declares."""
    return [s.key for s in env.secrets]


def test_a_domains_environment_is_named_after_its_directory():
    """A domain's environment is named for its directory and built on its task image."""
    env = config.task_environment(GATK_ENV, resources=flyte.Resources(memory="1Gi"))

    assert env.name == "gatk"
    assert env.image.name == "stargazer-gatk"
    assert env.image.uri == config.task_image(GATK_ENV).uri
    assert env.resources.memory == "1Gi"


def test_a_domains_environment_carries_the_shared_env_vars_and_secrets():
    """A domain's environment forwards the shared variables and declares the shared secrets."""
    env = config.task_environment(GATK_ENV)

    assert env.env_vars["PINATA_GATEWAY"] == config.STARGAZER_ENV_VARS["PINATA_GATEWAY"]
    assert "PINATA_JWT" in _secret_keys(env)


def test_a_callers_env_vars_and_secrets_are_added_to_the_shared_ones():
    """A caller's variables and secrets join the shared ones; the shared value wins."""
    env = config.task_environment(
        GATK_ENV,
        env_vars={"EXTRA": "1", "PINATA_GATEWAY": "https://elsewhere.example"},
        secrets=[flyte.Secret(key="MY_KEY", as_env_var="MY_KEY")],
    )

    assert env.env_vars["EXTRA"] == "1"
    # The shared value wins: a pod must resolve it like the submitter.
    assert env.env_vars["PINATA_GATEWAY"] == config.STARGAZER_ENV_VARS["PINATA_GATEWAY"]
    assert _secret_keys(env)[-1] == "MY_KEY"
    assert "PINATA_JWT" in _secret_keys(env)


def test_a_notebooks_environment_builds_from_its_header():
    """A notebook's environment is named for it and built from its header."""
    env = config.notebook_task_environment(TEMPLATE, "template")

    assert env.name == "template"
    assert env.image.name == "stargazer-template"
    assert env.image.uri == config.notebook_image(TEMPLATE, "stargazer-template").uri
    assert "PINATA_JWT" in _secret_keys(env)
    assert env.env_vars["PINATA_GATEWAY"] == config.STARGAZER_ENV_VARS["PINATA_GATEWAY"]
