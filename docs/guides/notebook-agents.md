# Agents in the Notebook

The notebook editor carries two coding agents, **Claude Code** and **OpenCode**, hosted and in the local image alike.

## Signing In

Press ++ctrl+grave++ in the notebook to open its terminal and sign in once: run `claude` for Claude Code, or `opencode auth login` for OpenCode. A hosted notebook keeps your sign-in for your next session; the local image keeps it until the container stops.

## Starting a Session

Open the AI panel from the sidebar, switch to **Agents** and start a new Claude or OpenCode session. The terminal and the agent are part of the editor, so a notebook opened to run has neither.

## What the Agent Can Do

- **Work in the notebook's folder**, with the Stargazer SDK installed at `/stargazer`.
- **Edit the open notebook.** The changed cells show up in the editor, ready to run.
- **Add tools to the notebook's header**, the command-line tools a notebook needs ([Where Your Code Runs](where-your-code-runs.md#your-notebooks-header)).
- **Use Stargazer's own tools**, which list the tasks and workflows, run them, and find, upload and tag your files. They're the MCP server's tools; [Using the MCP Server](mcp-server.md) describes each one.
