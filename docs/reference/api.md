# API Reference

This page will be auto-generated from docstrings using [mkdocstrings](https://mkdocstrings.github.io/).

## Setup

Add to `mkdocs.yml`:

```yaml
plugins:
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
```

Then reference modules with:

```markdown
::: stargazer.types.asset
::: stargazer.types.reference
::: stargazer.tasks.bwa
```
