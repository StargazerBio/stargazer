"""The dashboard deploys on the devbox and serves the stand-in user."""

import httpx


def test_dashboard_serves_the_stand_in_user(dashboard):
    """The deployed dashboard answers and shows `devbox-user` as signed in."""
    page = httpx.get(f"{dashboard}/", timeout=30)
    assert page.status_code == 200
    assert "devbox-user" in page.text
