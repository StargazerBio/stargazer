"""
### Marimo notebooks for interactive Stargazer workflows.

Researchers use these notebooks to explore data, run tasks, and visualize
results in a familiar Python-native environment. The hosted launch path
goes through the admin app's `/launch` handler, which spawns a
per-notebook AppEnvironment whose image is built programmatically by
`app.per_notebook.notebook_app_img`.

Navigation between notebooks lives on the dashboard; notebooks themselves
carry no nav chrome. The dashboard tile registry is `app/notebooks.py`.

spec: [docs/architecture/notebook.md](../../architecture/notebook.md)
"""
