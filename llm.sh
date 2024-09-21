#!/usr/bin/env bash

# LLM Prompt Generator Script
# Author: Your Name
# Contact Information: Your Contact Info
# Description:
#   This script generates an LLM prompt by aggregating specified files and directories.
#   It inserts a '# Prompt' section at the top of the llm.md file for the user to input instructions.
#   If the script is being run inside a VSCode devcontainer and the required environment variables are set,
#   it will send the entire updated llm.md to the OpenAI API.
#   The model's response is then inserted into llm.md after the user's prompt and before the '# Files' section.

# Code History:
#   - [Date]: Initial script creation.
#   - [Date]: Added functionality to interact with OpenAI API when environment variables are set.
#   - [Date]: Updated script to generate content before prompting the user for instructions.
#   - [Date]: Ensured script operates without environment variables, generating output as before.
#   - [Date]: Fixed 'Argument list too long' error by using --rawfile instead of --arg with jq.
#   - [Date]: Fixed 'Argument list too long' error with curl by writing request data to a temporary file.
#   - [Date]: Fixed unclosed quote error in reduce_yaml_file function.

# Default values for JSON processing
JSON_MAX_SIZE=${JSON_MAX_SIZE:-20480}  # Defaults to 20 KiB
JSON_MAX_DEPTH=${JSON_MAX_DEPTH:-10}   # Defaults to depth of 10
JSON_DONT_MODIFY=(${JSON_DONT_MODIFY[@]})  # Files not to modify (defaults to empty list)

# Directories and files to include
INCLUDE_DIRS=("src" ".devcontainer" ".github")
INCLUDE_FILES=("Dockerfile" "lexicon.json" "prompt.md" "demo.xml" "README.md")

# Extensions to ignore
IGNORE_EXTENSIONS=("svg" "jpg" "png" "gif" "pdf" "zip" "tar" "gz")

# Output markdown file
OUTPUT_FILE="llm.md"
TEMP_FILE="${OUTPUT_FILE}.tmp"

# Create or clear the output file
echo "" > "$OUTPUT_FILE"

# Append the additional text to the output file
{
  echo "# Requirements:"
  echo ""
  echo "## Language"
  echo ""
  echo "Always write in Australian English"
  echo ""
  echo "## Responses"
  echo ""
  echo "When refactoring or making changes to code, respond with complete, operable, files. Do not use placeholders to represent existing code that the user will need to replace."
  echo ""
  echo "## Technical and Coding Proficiency:"
  echo "When providing code examples and revisions, adhere strictly to the relevant Google Style Guide ie For Python, follow the Google Python Style Guide; for Bash, follow the Google Bash Style Guide, etc. Furthermore:"
  echo "1. **All code must be Google Style Guide compliant where one exists, best practice if not**."
  echo "2. **All code must be fully typed in languages that support typing**, including variables."
  echo "3. **When typing, the \`Any\` type must be avoided**. If it is required, detailed comments explaining why must be provided."
  echo "4. **All code must be broken into the smallest logical functional components**."
  echo "5. **Classes should be used where appropriate for functionality**."
  echo "6. **All reasonable exceptions must be caught and handled**, including cleanup where appropriate."
  echo "7. **All reasonable signals (including TERM, KILL, HUP, etc.) must be caught and handled appropriately**, including cleanup where appropriate."
  echo "8. **All code must be very well documented inline**."
  echo "9. **Examples should be included in comments where appropriate**."
  echo "10. **When creating new files**, an appropriate **file header should be included**:"
  echo "    - The purpose and description of the file."
  echo "    - The author's name and contact information."
  echo "    - Code history and changes."
  echo "11. **When creating a new file that is intended to be executed**, it should use the \`env\` shebang method:"
  echo "    \`\`\`python"
  echo "    #!/usr/bin/env python3"
  echo "    \`\`\`"
  echo "12. Ensure all imports/includes are referenced in the code; do not import/include if not needed."
  echo ""
  echo "# Context"
  echo ""
  echo "## Date"
  echo ""
  echo "Today is $(date '+%A, %d %B %Y')"
  echo ""
} >> "$OUTPUT_FILE"

# Append the "# Files" section
echo "# Files" >> "$OUTPUT_FILE"

# Function to process each file
process_file() {
  local file_path="$1"
  local file_extension="${file_path##*.}"
  local file_name
  file_name="$(basename "$file_path")"
  local file_size
  local dont_modify=false

  # Check if the file is in JSON_DONT_MODIFY
  for dont_modify_file in "${JSON_DONT_MODIFY[@]}"; do
    if [[ "$file_name" == "$dont_modify_file" ]]; then
      dont_modify=true
      break
    fi
  done

  # Append headings to the output file
  {
    echo ""
    echo "## ${file_path}"
    echo ""
    echo "\`\`\`${file_extension}"
  } >> "$OUTPUT_FILE"

  # Process JSON and YAML files for size reduction
  if [[ "$file_extension" == "json" || "$file_extension" == "yaml" || "$file_extension" == "yml" ]]; then
    file_size=$(stat -c%s "$file_path")
    if (( file_size > JSON_MAX_SIZE )) && [[ "$dont_modify" == false ]]; then
      # Reduce the size of the file content
      if [[ "$file_extension" == "json" ]]; then
        reduce_json_file "$file_path" >> "$OUTPUT_FILE"
      else
        reduce_yaml_file "$file_path" >> "$OUTPUT_FILE"
      fi
    else
      cat "$file_path" >> "$OUTPUT_FILE"
    fi
  else
    cat "$file_path" >> "$OUTPUT_FILE"
  fi

  # Close the code block
  {
    echo ""
    echo "\`\`\`"
    echo ""
  } >> "$OUTPUT_FILE"
}

# Function to reduce JSON file size by truncating arrays
reduce_json_file() {
  local file_path="$1"
  local depth="$JSON_MAX_DEPTH"
  jq --argjson depth "$depth" '
    def truncate($d):
      if $d == 0 then
        .
      elif type == "array" then
        if length > 2 then
          [.[0], .[1], "... truncated ..."]
        else
          map(. | truncate($d - 1))
        end
      elif type == "object" then
        with_entries(.value |= truncate($d - 1))
      else
        .
      end;
    truncate($depth)
  ' "$file_path"
}

# Function to reduce YAML file size by truncating arrays
reduce_yaml_file() {
  local file_path="$1"
  local depth="$JSON_MAX_DEPTH"
  yq eval '
    def truncate(d):
      if d == 0 then
        .
      elif tag == "!!seq" then
        if length > 2 then
          [.[0], .[1], "... truncated ..."]
        else
          map(truncate(d - 1))
        end
      elif tag == "!!map" then
        with(.[]; . = truncate(d - 1))
      else
        .
      end;
    truncate('"'"$depth"'"')
  ' "$file_path"
}

# Function to check if a file should be ignored based on extension
is_ignored() {
  local file_path="$1"
  local file_extension="${file_path##*.}"

  # Check against ignored extensions
  for ext in "${IGNORE_EXTENSIONS[@]}"; do
    if [[ "$file_extension" == "$ext" ]]; then
      # Check if the file is explicitly included
      for include_file in "${INCLUDE_FILES[@]}"; do
        if [[ "$file_path" == "$include_file" ]]; then
          return 1 # Not ignored
        fi
      done
      return 0 # Ignored
    fi
  done

  return 1 # Not ignored
}

# Function to check if a file is binary
is_binary() {
  local file_path="$1"
  # Use grep to check for binary data in the file
  if grep -qI "." "$file_path"; then
    return 1 # Not binary
  else
    return 0 # Binary
  fi
}

# Process each directory
for dir in "${INCLUDE_DIRS[@]}"; do
  if [[ -d "$dir" ]]; then
    find "$dir" -type f ! -path "*/__pycache__/*" | while IFS= read -r file; do
      if ! is_ignored "$file" && ! is_binary "$file"; then
        process_file "$file"
      fi
    done
  fi
done

# Process each specific file
for file in "${INCLUDE_FILES[@]}"; do
  if [[ -f "$file" ]] && ! is_ignored "$file" && ! is_binary "$file"; then
    process_file "$file"
  fi
done

# Insert the "# Prompt" section at the top of the file
{
  echo "# Prompt"
  echo ""
  echo "[Write your instructions here. For example: \"Add functionality to my app that checks the stock market every five minutes.\"]"
  echo ""
} > "$TEMP_FILE"

cat "$OUTPUT_FILE" >> "$TEMP_FILE"

# Replace the OUTPUT_FILE with TEMP_FILE
mv "$TEMP_FILE" "$OUTPUT_FILE"

# Open the llm.md file in VSCode
if command -v code >/dev/null 2>&1; then
  code "$OUTPUT_FILE"
else
  echo "Error: VSCode command 'code' not found."
  exit 1
fi

# Check if the script is being run inside a VSCode devcontainer and required environment variables are set
if [[ (-n "$REMOTE_CONTAINERS" || -n "$CODESPACES") && -n "$LLM_SH_OPENAI_KEY" && -n "$LLM_SH_OPENAI_MODEL" ]]; then
  # Wait for the user to edit and save the llm.md file
  initial_mod_time=$(stat -c %Y "$OUTPUT_FILE")
  echo "Waiting for you to edit and save llm.md..."
  
  while true; do
    sleep 1
    new_mod_time=$(stat -c %Y "$OUTPUT_FILE")
    if [[ "$new_mod_time" != "$initial_mod_time" ]]; then
      echo "llm.md has been modified."
      break
    fi
  done

  # Determine if the model does not support system prompts or max tokens
  MODEL="$LLM_SH_OPENAI_MODEL"
  if [[ "$MODEL" == "o1-preview-2024-09-12" ]]; then
    NO_SYSTEM_PROMPT=true
  else
    NO_SYSTEM_PROMPT=false
  fi

  # Prepare the request payload and write it to a temporary file
  REQUEST_FILE=$(mktemp)
  
  if [[ "$NO_SYSTEM_PROMPT" == "true" ]]; then
    jq -n \
      --arg model "$MODEL" \
      --rawfile content "$OUTPUT_FILE" \
      '{
        "model": $model,
        "messages": [
          {
            "role": "user",
            "content": $content
          }
        ]
      }' > "$REQUEST_FILE"
  else
    # You can set a system prompt here if needed
    SYSTEM_PROMPT="You are an assistant that helps with code and technical tasks."
    jq -n \
      --arg model "$MODEL" \
      --arg system_prompt "$SYSTEM_PROMPT" \
      --rawfile content "$OUTPUT_FILE" \
      '{
        "model": $model,
        "messages": [
          {
            "role": "system",
            "content": $system_prompt
          },
          {
            "role": "user",
            "content": $content
          }
        ]
      }' > "$REQUEST_FILE"
  fi

  # Send the content to the OpenAI API using the temporary file
  echo "Sending your prompt to the OpenAI API..."
  RESPONSE=$(curl -s https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LLM_SH_OPENAI_KEY" \
  --data-binary @"$REQUEST_FILE")

  # Remove the temporary request file
  rm "$REQUEST_FILE"

  # Extract the assistant's response
  assistant_content=$(echo "$RESPONSE" | jq -r '.choices[0].message.content')

  if [[ "$assistant_content" == "null" ]]; then
    echo "Error: Failed to get a valid response from the OpenAI API."
    echo "Response from API:"
    echo "$RESPONSE"
    exit 1
  fi

  # Insert the assistant's response into llm.md after the user's prompt and before the '# Files' section
  {
    # Extract the content before '# Files'
    sed '/# Files/,$d' "$OUTPUT_FILE"
    echo ""
    echo "# Assistant's Response"
    echo ""
    echo "$assistant_content"
    echo ""
    # Include the '# Files' section and everything after
    sed -n '/# Files/,$p' "$OUTPUT_FILE"
  } > "$TEMP_FILE"

  # Replace the OUTPUT_FILE with TEMP_FILE
  mv "$TEMP_FILE" "$OUTPUT_FILE"

  echo "Assistant's response has been added to $OUTPUT_FILE."
else
  echo "LLM prompt file has been generated at ${OUTPUT_FILE}"
fi