"""Tests for where the SDK finds the Pinata key (`stargazer.config.pinata_jwt`)."""

from stargazer.config import pinata_jwt


def test_the_mounted_file_wins_over_the_env_var(tmp_path, monkeypatch):
    """A pod's mounted secret is the key, whatever the environment holds."""
    (tmp_path / "PINATA_JWT").write_text("from-file\n")
    monkeypatch.setenv("FLYTE_SECRETS_DEFAULT_DIR", str(tmp_path))
    monkeypatch.setenv("PINATA_JWT", "from-env")

    assert pinata_jwt() == "from-file"


def test_the_env_var_is_the_key_without_a_file(tmp_path, monkeypatch):
    """Locally the key comes from the environment (.env), with no mounted file."""
    monkeypatch.setenv("FLYTE_SECRETS_DEFAULT_DIR", str(tmp_path))
    monkeypatch.setenv("PINATA_JWT", "from-env")

    assert pinata_jwt() == "from-env"


def test_no_key_anywhere_is_none(tmp_path, monkeypatch):
    """Neither a file nor a value (an empty one included) means no public tier."""
    (tmp_path / "PINATA_JWT").write_text("")
    monkeypatch.setenv("FLYTE_SECRETS_DEFAULT_DIR", str(tmp_path))
    monkeypatch.setenv("PINATA_JWT", "")

    assert pinata_jwt() is None
