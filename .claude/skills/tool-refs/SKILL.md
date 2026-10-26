---
name: tool-refs
description: Help text for the GATK and Parabricks commands Stargazer wraps, the source of truth for their parameters and behavior. Use when writing or changing a task that calls gatk or parabricks, or checking a tool flag.
---

# Tool references

One file per command, its `--help` output as markdown: `gatk/<command>.md`, `parabricks/<command>.md`, the command lowercased (`gatk BaseRecalibrator` → `gatk/baserecalibrator.md`). List the directory to find one.

## Adding a tool

`generate_help_docs.sh` runs each command with `--help` and writes the file, HTML tags cleaned into markdown, into a directory named after the command's first word in the current directory. Run it from this skill's directory, in the image that carries the tool (the tools aren't on the dev machine):

```bash
./generate_help_docs.sh "gatk ApplyBQSR" "parabricks fq2bam"
./generate_help_docs.sh commands.txt   # one command per line, # for comments
```

`commands.example.txt` is a sample commands file.
