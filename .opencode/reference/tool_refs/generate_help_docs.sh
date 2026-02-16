#!/bin/bash

# Script to generate help documentation for multiple commands
# Usage: ./generate_help_docs.sh commands.txt
#   OR:  ./generate_help_docs.sh "command1 subcommand1" "command2 subcommand2" ...

set -e

# Function to convert command to filename
# e.g., "gatk BaseRecalibrator" -> "gatk/base_recalibrator.md"
command_to_filename() {
    local cmd="$1"
    local first_word=$(echo "$cmd" | awk '{print $1}')
    local rest=$(echo "$cmd" | cut -d' ' -f2- | tr '[:upper:]' '[:lower:]' | tr ' ' '_')

    # Create directory if it doesn't exist
    mkdir -p "$first_word"

    # Return the full path
    echo "${first_word}/${rest}.md"
}

# Function to format output as markdown and clean HTML tags
format_as_markdown() {
    local input_file="$1"
    local cmd_name="$2"
    local temp_file="${input_file}.tmp"

    # Add markdown header
    echo "# ${cmd_name}" > "$temp_file"
    echo "" >> "$temp_file"
    echo '```' >> "$temp_file"

    # Process the file to clean HTML tags and format
    cat "$input_file" | \
        # Remove HTML tags but preserve content
        sed 's/<p>/\n/g' | \
        sed 's/<\/p>//g' | \
        sed 's/<br>/\n/g' | \
        sed 's/<\/br>//g' | \
        sed 's/<b>\(.*\)<\/b>/**\1**/g' | \
        sed 's/<i>\(.*\)<\/i>/*\1*/g' | \
        sed 's/<code>\(.*\)<\/code>/`\1`/g' | \
        sed 's/<pre>/\n```\n/g' | \
        sed 's/<\/pre>/\n```\n/g' | \
        sed 's/<ul>/\n/g' | \
        sed 's/<\/ul>/\n/g' | \
        sed 's/<li>/* /g' | \
        sed 's/<\/li>//g' | \
        sed 's/<h[0-9]>/\n## /g' | \
        sed 's/<\/h[0-9]>/\n/g' | \
        sed 's/<a href="\([^"]*\)"[^>]*>\([^<]*\)<\/a>/[\2](\1)/g' | \
        sed 's/&lt;/</g' | \
        sed 's/&gt;/>/g' | \
        sed 's/&amp;/\&/g' | \
        sed 's/&quot;/"/g' | \
        sed 's/&apos;/'\''/g' | \
        # Remove any remaining HTML tags
        sed 's/<[^>]*>//g' | \
        # Remove excessive blank lines (more than 2 consecutive)
        cat -s >> "$temp_file"

    echo '```' >> "$temp_file"

    # Replace original file with formatted version
    mv "$temp_file" "$input_file"
}

# Function to run command with --help and save output
generate_help() {
    local cmd="$1"
    local output_file=$(command_to_filename "$cmd")
    local temp_raw="${output_file}.raw"

    echo "Generating help for: $cmd"
    echo "  -> $output_file"

    # Run the command with --help and save to temp file first
    # Using eval to properly handle the command string
    if eval "$cmd --help" > "$temp_raw" 2>&1; then
        echo "  ✓ Help generated"
    else
        # Some commands return non-zero exit codes even for --help
        # So we still consider it success if output was generated
        if [ -s "$temp_raw" ]; then
            echo "  ✓ Help generated (non-zero exit, but output generated)"
        else
            echo "  ✗ Failed (no output generated)"
            rm -f "$temp_raw"
            return 1
        fi
    fi

    # Format as markdown and clean HTML
    mv "$temp_raw" "$output_file"
    format_as_markdown "$output_file" "$cmd"
    echo "  ✓ Formatted as markdown"
    echo ""
}

# Main script logic
main() {
    if [ $# -eq 0 ]; then
        echo "Usage: $0 <commands_file>"
        echo "   OR: $0 \"command1 subcommand1\" \"command2 subcommand2\" ..."
        echo ""
        echo "Examples:"
        echo "  $0 commands.txt"
        echo "  $0 \"gatk BaseRecalibrator\" \"gatk HaplotypeCaller\""
        echo ""
        echo "commands_file format (one command per line):"
        echo "  gatk BaseRecalibrator"
        echo "  gatk HaplotypeCaller"
        echo "  parabricks fq2bam"
        exit 1
    fi

    # Check if first argument is a file
    if [ -f "$1" ]; then
        echo "Reading commands from file: $1"
        echo "================================"
        echo ""

        # Read commands from file (one per line, ignore empty lines and comments)
        while IFS= read -r line || [ -n "$line" ]; do
            # Skip empty lines and comments
            [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
            generate_help "$line"
        done < "$1"
    else
        # Treat all arguments as individual commands
        echo "Processing commands from arguments"
        echo "=================================="
        echo ""

        for cmd in "$@"; do
            generate_help "$cmd"
        done
    fi

    echo "All done!"
}

main "$@"
