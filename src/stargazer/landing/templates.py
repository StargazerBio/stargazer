"""
### HTML templates for the landing page.

Plain Python functions returning HTML strings. No Jinja dependency —
the landing page is simple enough that f-strings suffice.

spec: [docs/architecture/landing.md](../../docs/architecture/landing.md)
"""


def _base(title: str, body: str) -> str:
    """Wrap body content in the base HTML shell."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title} — Stargazer</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         Helvetica, Arial, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 2.5rem;
            max-width: 420px;
            width: 100%;
            text-align: center;
        }}
        h1 {{ color: #f0f6fc; margin-bottom: 0.5rem; font-size: 1.6rem; }}
        p {{ margin-bottom: 1.5rem; line-height: 1.5; font-size: 0.95rem; }}
        .btn {{
            display: inline-block;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
            transition: opacity 0.15s;
        }}
        .btn:hover {{ opacity: 0.85; }}
        .btn-github {{
            background: #238636;
            color: #fff;
        }}
        .btn-notebook {{
            background: #1f6feb;
            color: #fff;
        }}
        .btn-console {{
            background: #30363d;
            color: #c9d1d9;
            margin-left: 0.5rem;
        }}
        .user-info {{
            margin-bottom: 1.5rem;
            font-size: 0.9rem;
            color: #8b949e;
        }}
        .actions {{ display: flex; gap: 0.75rem; justify-content: center; flex-wrap: wrap; }}
        .spinner {{
            display: inline-block;
            width: 24px; height: 24px;
            border: 3px solid #30363d;
            border-top-color: #58a6ff;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 1rem;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .logout {{ color: #8b949e; font-size: 0.8rem; margin-top: 1rem; }}
        .logout a {{ color: #8b949e; }}
    </style>
</head>
<body>
    <div class="card">
        {body}
    </div>
</body>
</html>"""


def login_html() -> str:
    """Landing page with GitHub sign-in button."""
    return _base(
        "Sign In",
        """\
        <h1>Stargazer</h1>
        <p>Interactive bioinformatics workflows powered by Flyte.</p>
        <a href="/auth/login" class="btn btn-github">Sign in with GitHub</a>""",
    )


def dashboard_html(
    github_username: str, notebook_url: str, console_url: str | None = None
) -> str:
    """Post-login dashboard with links to notebook and console."""
    console_link = ""
    if console_url:
        console_link = (
            f'<a href="{console_url}" class="btn btn-console">Union Console</a>'
        )

    return _base(
        "Dashboard",
        f"""\
        <h1>Stargazer</h1>
        <div class="user-info">Signed in as <strong>{github_username}</strong></div>
        <div class="actions">
            <a href="{notebook_url}" class="btn btn-notebook">Open Notebook</a>
            {console_link}
        </div>
        <div class="logout"><a href="/auth/logout">Sign out</a></div>""",
    )


def provisioning_html(github_username: str) -> str:
    """Displayed while the user's workspace is being set up."""
    return _base(
        "Setting Up",
        f"""\
        <div class="spinner"></div>
        <h1>Setting up your workspace</h1>
        <p>Creating project for <strong>{github_username}</strong>...<br>
        This usually takes a minute or two on first login.</p>
        <script>
            setTimeout(function() {{ window.location.reload(); }}, 5000);
        </script>""",
    )
