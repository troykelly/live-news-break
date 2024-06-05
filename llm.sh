#!/usr/bin/env zsh

# Directory containing Python files
SRC_DIR="src"
# Output markdown file
OUTPUT_FILE="llm.md"

# Create or clear the output file
echo "# Files" > $OUTPUT_FILE

# Function to process each Python file
process_file() {
    local file_path=$1
    echo "\n## ${file_path}\n" >> $OUTPUT_FILE
    echo "\`\`\`python" >> $OUTPUT_FILE
    # Add the content of the file and ensure there is a trailing newline
    awk '{print} END {if (NR > 0 && substr($0, length($0), 1) != "\n") print ""}' $file_path >> $OUTPUT_FILE
    echo "\`\`\`\n" >> $OUTPUT_FILE
}

# Find all .py files in the SRC_DIR excluding __pycache__ and other unwanted directories
find $SRC_DIR -type f -name "*.py" ! -path "*/__pycache__/*" | while read -r file; do
    process_file "$file"
done

echo "LLM prompt file has been generated at ${OUTPUT_FILE}"
