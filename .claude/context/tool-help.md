---
sources:
  - .claude/context/raw/tool-help/generate_help_docs.sh
  - .claude/context/raw/tool-help/commands.example.txt
  - src/stargazer/config.py
---

# Tool help

The help text and manuals of the command-line tools Stargazer's tasks wrap, captured verbatim under `raw/tool-help/`. It's the source of truth for a task's parameters: read the tool's help before writing or changing a task.

## What's captured

- [[gatk]]: GATK tools, with the task that wraps each
- [[parabricks]]: NVIDIA Parabricks, the GPU equivalents, which no task wraps

The aligners and samtools, also in `gatk_env`'s image:

| Tool | Help | Stargazer tasks |
|------|------|-----------------|
| bwa | [[bwa]] | `bwa_index`, `bwa_mem` |
| bwa-mem2 | not captured | `bwa_mem2_index`, `bwa_mem2_mem` |
| samtools faidx | [[samtools-faidx]] | `samtools_faidx` |

Their tasks are in `src/stargazer/tasks/general/`. The bwa and samtools pages are the tools' manuals rather than `--help` output.

## Capturing more

- **`raw/tool-help/generate_help_docs.sh`** runs `<command> --help` for each command it's given, as arguments or a commands file (one per line, `#` comments; `raw/tool-help/commands.example.txt` is one), and saves each as markdown.
- **It names each file `<tool>/<tool>-<subcommand>.md`**, lowercased, so every basename is unique across tools and a `[[wikilink]]` to it resolves. A command with no subcommand is `<tool>/<tool>.md`.
- **It strips HTML** from the help (paragraphs, bold, links, entities) and wraps the result in a code fence.
- **Run it where the tool is.** The tools aren't on the dev machine's path; they're in their task environment's image ([[flyte-images]]), so the script runs inside that image (`docker run --platform linux/amd64 <image> ...`, with the script and an output directory mounted).
- **After capturing**, link the new file from its tool's page and name the task that wraps it.
