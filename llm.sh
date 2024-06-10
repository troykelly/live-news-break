#!/usr/bin/env zsh

# Base directories and specific files to include
INCLUDE_DIRS=("src" ".devcontainer" ".github")
INCLUDE_FILES=("Dockerfile" "lexicon.json" "prompt.md" "demo.xml")

# Output markdown file
OUTPUT_FILE="llm.md"

# Create or clear the output file
echo "# Files" > $OUTPUT_FILE

# Function to process each file
process_file() {
    local file_path=$1
    local file_extension="${file_path##*.}"
    echo "\n## ${file_path}\n" >> $OUTPUT_FILE
    echo "\`\`\`${file_extension}" >> $OUTPUT_FILE
    # Add the content of the file and ensure there is a trailing newline
    awk '{print} END {if (NR > 0 && substr($0, length($0), 1) != "\n") print ""}' $file_path >> $OUTPUT_FILE
    echo "\`\`\`\n" >> $OUTPUT_FILE
}

# Process each directory
for dir in "${INCLUDE_DIRS[@]}"; do
    find $dir -type f ! -path "*/__pycache__/*" | while read -r file; do
        process_file "$file"
    done
done

# Process each specific file
for file in "${INCLUDE_FILES[@]}"; do
    if [[ -f $file ]]; then
        process_file "$file"
    fi
done

echo "LLM prompt file has been generated at ${OUTPUT_FILE}"
