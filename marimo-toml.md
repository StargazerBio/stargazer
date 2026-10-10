---
title: Cohesive marimo.toml integration
status: backlog
priority: low
created: 2026-06-10
---

A root `marimo.toml` exists with `[ai] rules` carrying stargazer authoring conventions, but it's an ad-hoc artifact — no story for how it's baked into the notebook image, kept in sync with the conventions in AGENTS.md/docs, or extended (completions, future MCP wiring, per-notebook overrides). Design one deliberate marimo-config surface and remove the duplication. Subsumes the marimo-AI angle of the Marimo AI features investigation and In-notebook MCP integration.
