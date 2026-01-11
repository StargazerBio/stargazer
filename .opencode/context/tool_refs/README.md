# Tool Reference Documentation Generator

This script automatically generates help documentation for command-line tools by running `--help` and saving the output to organized markdown files with HTML tags cleaned up.

## Features

- **Markdown formatted output** - All help text is saved as `.md` files with proper formatting
- **HTML tag cleaning** - Automatically strips and converts HTML tags (`<p>`, `<br>`, etc.) to markdown
- **Organized structure** - Creates directories based on tool names
- **Batch processing** - Process multiple commands at once

## Usage

### Method 1: Using a commands file

```bash
./generate_help_docs.sh commands.txt
```

### Method 2: Passing commands directly

```bash
./generate_help_docs.sh "gatk BaseRecalibrator" "gatk HaplotypeCaller" "parabricks fq2bam"
```

## Commands File Format

Create a text file with one command per line:

```
# Comments start with #
gatk BaseRecalibrator
gatk HaplotypeCaller
parabricks fq2bam
parabricks germline
```

## Output Structure

The script automatically:
- Creates directories based on the first word of the command
- Converts subcommands to lowercase with underscores
- Saves output as markdown `.md` files
- Strips HTML tags and formats as clean markdown

**Examples:**
- `gatk BaseRecalibrator` → `gatk/base_recalibrator.md`
- `parabricks fq2bam` → `parabricks/fq2bam.md`
- `samtools view` → `samtools/view.md`

## HTML Tag Handling

The script automatically cleans up HTML tags commonly found in help output:
- `<p>`, `<br>` → Newlines
- `<b>text</b>` → `**text**` (bold)
- `<i>text</i>` → `*text*` (italic)
- `<code>text</code>` → `` `text` `` (inline code)
- `<a href="...">text</a>` → `[text](url)` (links)
- HTML entities (`&lt;`, `&gt;`, `&amp;`, etc.) → Proper characters

## Example

```bash
# Create a commands file
cat > my_commands.txt << EOF
gatk BaseRecalibrator
gatk ApplyBQSR
parabricks fq2bam
EOF

# Generate all help docs
./generate_help_docs.sh my_commands.txt
```

This will create:
- `gatk/base_recalibrator.md`
- `gatk/apply_bqsr.md`
- `parabricks/fq2bam.md`

All files will be formatted as markdown with HTML tags cleaned up for easy reading.
