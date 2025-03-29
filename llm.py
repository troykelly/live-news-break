#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm.py

This script facilitates interaction with the OpenAI API, managing conversation
state, and updating files in the repository based on LLM responses. It provides
a conversation manager, handles file trees, and applies updates atomically. The
script also logs detailed error output on failures and enforces a default
five-minute timeout on requests to the OpenAI API.

Author: Troy Kelly
Email: troy@aperim.com
Date: Saturday, 19 October 2024

Updates:
- Fixed issue with "double wrapping" in files generated from LLM responses.
- Added function to clean Markdown code blocks from LLM responses before file updates.
- Fixed bug where specifying a directory as an argument didn't include its contents.
- Enhanced error reporting to output details when the model fails or returns an error.
- Introduced a constant TIMEOUT_SECONDS to enforce a default 300-second (5-minute) timeout.
- Resolved looping issue by ensuring the conversation is updated to remove system role
  after a retry, preventing repeated rejections.

Additional Debugging Updates:
- Display total tokens sent to and received from the OpenAI API (via usage.prompt_tokens
  and usage.completion_tokens).
- Provide a --dump argument to save the entire request payload (including any system
  message) to a uniquely named JSON file before sending to the OpenAI API.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openai
from openai import OpenAI

# ------------------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------------------

TIMEOUT_SECONDS: int = 900
"""Default request timeout for OpenAI requests in seconds (5 minutes)."""

# ========================================================================
# System Prompt Template
#
# The system prompt is embedded directly within this script for portability.
# You can edit the prompt below as needed.
# ========================================================================

SYSTEM_PROMPT_TEMPLATE = r"""
## Requirements

### Language

- **Use Australian English** in all responses.

## **Code Revision & Refactoring Instructions**  

When modifying, refactoring, or responding with code, follow these strict guidelines:  

### **1. Make Only Explicitly Requested Changes**  
- Do not modify the code beyond the scope of the user's instructions.  
- If a change is ambiguous, ask for clarification rather than assuming.  

### **2. Preserve Formatting, Naming & Structure**  
- Do not reformat code (e.g., indentation, line breaks, spacing) unless explicitly requested.  
- Do not rename functions, variables, or classes unless necessary to fulfill the user's request.  
- Avoid restructuring functions, refactoring logic, or introducing alternative implementations unless instructed.  

### **3. Preserve Existing Functionality**  
- Do not remove or alter any existing functionality unless explicitly instructed.  
- Maintain existing comments, annotations, and docstrings unless they become incorrect due to modifications.  

### **4. Provide Complete, Operable Files**  
- Always respond with full, functional code files—never partial snippets unless explicitly requested.  
- **Never use placeholders** (e.g., `# Add your code here` or `TODO`). All provided code should be ready to execute.  
- If an existing file is modified, return the entire modified file, not just the changed section.  

### **5. Handling Long Outputs**  
If the output is too long to fit in a single response:  
- Provide as many **complete** files as possible.  
- Indicate that more output is available with: `<<LLM_MORE_OUTPUT_AVAILABLE>>`  
- After all output has been provided, mark completion with: `<<LLM_CONTINUED_OUTPUT_END>>`  

### **6. Apply a Minimal Impact Policy**  
- Make the smallest necessary change to achieve the requested modification.  
- Do not introduce optimizations or performance improvements unless explicitly requested.  

### **7. Error Handling & Safety**  
- If a requested change introduces errors or inconsistencies, highlight them instead of making assumptions.  
- Only fix errors if explicitly instructed to do so.  

### **8. Adherence to Original Language & Conventions**  
- If the code follows a particular style guide (e.g., Google Python Style Guide), do not deviate from it unless instructed.  

### **9. No Unprompted Enhancements**  
- Do not add comments, logging, debugging output, or additional functionality unless requested.  
- If an improvement opportunity is noticed, suggest it separately instead of modifying the code directly.  

**Example**:

```
[Your code output here]

<<LLM_MORE_OUTPUT_AVAILABLE>>
```

### File Demarcation

When providing complete files, **use the following unique markers** to clearly indicate the start and end of each file's content. **Do not double-wrap** with markdown tags; only use these markers:

- **Start of File**: `<<LLM_FILE_START: [filename]>>`
- **End of File**: `<<LLM_FILE_END>>`

**Example**:

```
<<LLM_FILE_START: frontend/src/redux/slices/userSlice.ts>>
[File content goes here]
<<LLM_FILE_END>>
```

*Use these markers exactly as shown, including the double angle brackets and the notation.*

## Technical and Coding Proficiency

When providing code examples and revisions, **adhere strictly to the relevant Google Style Guide** (e.g., for Python, follow the Google Python Style Guide; for Bash, follow the Google Bash Style Guide). Additionally:

1. **Always use best practices**: Always provide responses that adhere to established best practice principles in the field you are responding.
2. **Style Compliance**: All code must comply with the Google Style Guide where one exists, or follow best practices if not.
3. **Full Typing**: Use full typing in languages that support it, including for variables.
4. **Avoid `Any` Type**: Do not use the `Any` type. If it is absolutely necessary, provide detailed code comments explaining why.
5. **Modular Code**: Break code into the smallest logical functional components.
6. **Use of Classes**: Utilize classes where appropriate to enhance functionality.
7. **Exception Handling**: Catch and handle all reasonable errors and exceptions, including performing cleanup when appropriate.
8. **Signal Handling**: Catch and handle all reasonable signals (e.g., `TERM`, `KILL`, `HUP`), including performing cleanup when appropriate.
9. **Inline Documentation**: Generate comprehensive documentation for the provided code. Make sure to include detailed descriptions for every code component (functions, interfaces, classes, etc.), specify the types of parameters and return values, and clearly indicate any optional or nested elements. Provide detailed support for IDE tools like intellisense. Use the appropriate documentation style for the code's language.
10. **Usage Examples**: Provide examples in comments where appropriate.
11. **Do not directly modify any dependency management files** (e.g., those that define project dependencies). Instead, provide the appropriate command or tool-based approach to make changes, as would normally be done using the language's standard package manager or environment. This ensures the changes are applied correctly within the workflow of the specific project.
12. **Do not modify or adjust any linting configuration** to bypass or ignore coding errors. Coding errors should be fixed by correcting the code itself, not by changing or disabling linting rules. If the linting configuration is incorrect or needs adjustment for valid reasons, suggest changes with clear justification. However, coding errors should always be addressed as coding issues, not hidden or ignored through linting configuration changes.
13. **File Headers for New Files**: When creating new files, include a header with:
    - The purpose and description of the file.
    - The author's name and contact information.
    - Code history and changes.
14. **Shebang for Executable Files**: For new executable files, use the `env` shebang method at the top:

    ```python
    #!/usr/bin/env python3
    ```

15. **Imports/Includes**: Ensure all necessary imports/includes are referenced; do not include unused modules.

## Context

### Date

- **Today is {current_date}**

### User Information

- **GITHUB_USERNAME**: `{GITHUB_USERNAME}`
- **GITHUB_FULLNAME**: `{GITHUB_FULLNAME}`
- **GITHUB_EMAIL**: `{GITHUB_EMAIL}`
- **GITHUB_OWNER**: `{GITHUB_OWNER}`
- **GITHUB_REPO**: `{GITHUB_REPO}`

---
"""


class EnvironmentConfig:
    """
    A class to load and store environment variables.
    """

    def __init__(self) -> None:
        """
        Initialise the EnvironmentConfig class, loading environment variables
        required for OpenAI and GitHub integration.
        """
        self.env_vars: Dict[str, str] = self.load_environment_variables()

    @staticmethod
    def load_environment_variables() -> Dict[str, str]:
        """
        Load necessary environment variables from the environment.

        Returns:
            A dictionary containing the relevant environment variables.
        """
        env_vars: Dict[str, str] = {
            "OPENAI_KEY": os.getenv("LLM_SH_OPENAI_KEY", ""),
            "OPENAI_PROJECT": os.getenv("LLM_SH_OPENAI_PROJECT", ""),
            "OPENAI_ORGANIZATION": os.getenv("LLM_SH_OPENAI_ORGANIZATION", ""),
            "OPENAI_MODEL": os.getenv("LLM_SH_OPENAI_MODEL", "gpt-4"),
            "OPENAI_REASONING": os.getenv("LLM_SH_OPENAI_REASONING", None),
            "OPENAI_MAX_TOKENS": os.getenv("LLM_SH_OPENAI_MAX_TOKENS", "4096"),
            "GITHUB_USERNAME": os.getenv("GITHUB_USERNAME", "troykelly"),
            "GITHUB_FULLNAME": os.getenv("GITHUB_FULLNAME", "Troy Kelly"),
            "GITHUB_EMAIL": os.getenv("GITHUB_EMAIL", "troy@aperim.com"),
            "GITHUB_OWNER": os.getenv("GITHUB_OWNER", ""),
            "GITHUB_REPO": os.getenv("GITHUB_REPO", ""),
        }
        return env_vars


class OpenAIInteraction:
    """
    A class to handle interactions with the OpenAI API.
    """

    def __init__(self, env_vars: Dict[str, str], dump_mode: bool = False) -> None:
        """
        Initialise the OpenAIInteraction class, preparing necessary configuration
        for ChatCompletion requests.

        Args:
            env_vars: A dictionary of environment variables.
            dump_mode: Flag indicating whether to dump the entire payload to disk.
        """
        self.env_vars: Dict[str, str] = env_vars
        self.api_key: str = env_vars["OPENAI_KEY"]
        self.organization: str = env_vars.get("OPENAI_ORGANIZATION", "")
        self.model: str = env_vars["OPENAI_MODEL"]
        self.max_tokens: int = int(env_vars.get("OPENAI_MAX_TOKENS", "4096"))
        self.reasoning: str = env_vars.get("OPENAI_REASONING", None)
        self.client: OpenAI = OpenAI(
            api_key=self.api_key, organization=self.organization)
        self.last_error: str = ""
        """Stores details of the most recent error encountered during requests."""
        self.dump_mode: bool = dump_mode
        """Flag that indicates whether to write the request payload to a unique JSON file."""

    def send(self, conversation: List[Dict[str, str]]) -> Optional[str]:
        """
        Send the conversation to the OpenAI API and get the assistant's response.

        This method also logs the token usage and optionally dumps the entire
        request payload to a uniquely named JSON file if dump_mode is enabled.

        Args:
            conversation: List of messages in the conversation.

        Returns:
            The assistant's response content, or None if an error occurred.
        """
        # Build payload for possible dumping
        payload: Dict[str, object] = {
            "model": self.model,
            "messages": self._format_messages(conversation),
            "max_completion_tokens": self.max_tokens,
            "temperature": 1,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "timeout": TIMEOUT_SECONDS,
            "reasoning": self.reasoning
        }

        if self.dump_mode:
            dump_filename: str = f"payload_dump_{
                datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
            try:
                with open(dump_filename, "w", encoding="utf-8") as dump_file:
                    json.dump(payload, dump_file, indent=2)
                logging.info("Wrote request payload to %s", dump_filename)
            except Exception as dump_exc:
                logging.error("Failed to dump request payload: %s", dump_exc)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._format_messages(conversation),
                max_completion_tokens=self.max_tokens,
                temperature=1,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                timeout=TIMEOUT_SECONDS,
                reasoning_effort=self.reasoning
            )

            # Log token usage if available
            usage: Optional[Dict[str, int]] = getattr(response, "usage", None)
            # if usage:
            #     prompt_tokens: int = usage.get("prompt_tokens", 0)
            #     completion_tokens: int = usage.get("completion_tokens", 0)
            #     total_tokens: int = usage.get("total_tokens", 0)
            #     logging.info("Total tokens sent (prompt): %d", prompt_tokens)
            #     logging.info(
            #         "Total tokens received (completion): %d", completion_tokens)
            #     logging.info("Overall tokens used: %d", total_tokens)

            return response.choices[0].message.content
        except openai.BadRequestError as exc:
            self.last_error = str(exc)
            error_message = str(exc)
            if "'system'" in error_message:
                logging.warning(
                    "Model doesn't support 'system' role in messages. Retrying without 'system' role."
                )
                # If the model rejects the 'system' role, try removing it once
                return self._retry_without_system_role(conversation)
            else:
                logging.error("OpenAI API Error: %s", exc)
                return None
        except openai.OpenAIError as exc:
            self.last_error = str(exc)
            logging.error("OpenAI API Error: %s", exc)
            return None
        except Exception as exc:
            self.last_error = str(exc)
            logging.error("An unexpected error occurred: %s", exc)
            return None

    def _retry_without_system_role(
        self, conversation: List[Dict[str, str]]
    ) -> Optional[str]:
        """
        Retry the chat completion request without the 'system' role.

        This method extracts any system prompt, prepends it to the first user
        message (or inserts a new user message), and updates the original
        conversation so that subsequent calls do not repeatedly re-inject
        the 'system' role.

        Args:
            conversation: Original conversation including 'system' role.

        Returns:
            The assistant's response content, or None if an error occurred.
        """
        messages_without_system: List[Dict[str, str]] = [
            msg for msg in conversation if msg["role"] != "system"
        ]

        system_prompt: str = next(
            (msg["content"]
             for msg in conversation if msg["role"] == "system"), ""
        )

        if messages_without_system and messages_without_system[0]["role"] == "user":
            messages_without_system[0]["content"] = (
                f"{system_prompt}\n\n{messages_without_system[0]['content']}"
            )
        else:
            messages_without_system.insert(
                0, {"role": "user", "content": system_prompt}
            )

        # Build payload for possible dumping
        payload: Dict[str, object] = {
            "model": self.model,
            "messages": self._format_messages(messages_without_system),
            "timeout": TIMEOUT_SECONDS,
        }

        if self.dump_mode:
            dump_filename: str = f"payload_dump_{
                datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_retry.json"
            try:
                with open(dump_filename, "w", encoding="utf-8") as dump_file:
                    json.dump(payload, dump_file, indent=2)
                logging.info(
                    "Wrote retry request payload to %s", dump_filename)
            except Exception as dump_exc:
                logging.error(
                    "Failed to dump retry request payload: %s", dump_exc)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self._format_messages(messages_without_system),
                timeout=TIMEOUT_SECONDS,
                reasoning_effort=self.reasoning
            )
            # If we successfully get a response, update the original
            # conversation to remove system role and use the new messages.
            conversation.clear()
            conversation.extend(messages_without_system)

            usage: Optional[Dict[str, int]] = getattr(response, "usage", None)
            # if usage:
            #     prompt_tokens: int = usage.get("prompt_tokens", 0)
            #     completion_tokens: int = usage.get("completion_tokens", 0)
            #     total_tokens: int = usage.get("total_tokens", 0)
            #     logging.info(
            #         "Total tokens sent (prompt, retry): %d", prompt_tokens)
            #     logging.info(
            #         "Total tokens received (completion, retry): %d", completion_tokens)
            #     logging.info("Overall tokens used (retry): %d", total_tokens)

            return response.choices[0].message.content
        except openai.OpenAIError as exc:
            self.last_error = str(exc)
            logging.error("Error after removing 'system' role: %s", exc)
            return None
        except Exception as exc:
            self.last_error = str(exc)
            logging.error(
                "Unexpected error after removing 'system' role: %s", exc)
            return None

    @staticmethod
    def _format_messages(conversation: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Format the conversation into the expected message format for the OpenAI API.

        Args:
            conversation: List of messages in the conversation.

        Returns:
            Formatted list of messages.
        """
        return [{"role": msg["role"], "content": msg["content"]} for msg in conversation]


class ConversationManager:
    """
    A class to manage the conversation state and storage.
    """

    def __init__(self, conversation_file: str) -> None:
        """
        Initialise the ConversationManager class.

        Args:
            conversation_file: Path to the JSON file used for storing conversation data.
        """
        self.conversation_file: str = conversation_file
        self.conversation: List[Dict[str, str]] = []
        self.load_conversation()

    def load_conversation(self) -> None:
        """
        Load the conversation from the designated JSON file.
        """
        if os.path.exists(self.conversation_file):
            try:
                with open(self.conversation_file, "r", encoding="utf-8") as file:
                    self.conversation = json.load(file)
                    logging.info("Loaded existing conversation.")
            except json.JSONDecodeError:
                logging.warning(
                    "Invalid conversation file. Starting a new conversation."
                )
                self.conversation = []
        else:
            logging.info(
                "No previous conversation found. Starting a new conversation.")

    def save_conversation(self) -> None:
        """
        Save the current conversation to the designated JSON file.
        """
        with open(self.conversation_file, "w", encoding="utf-8") as file:
            json.dump(self.conversation, file, indent=2)
        logging.info("Conversation saved.")

    def append_message(self, role: str, content: str) -> None:
        """
        Append a new message to the conversation.

        Args:
            role: The role of the message ('user', 'assistant', or 'system').
            content: The content of the message.
        """
        self.conversation.append({"role": role, "content": content})

    def get_conversation(self) -> List[Dict[str, str]]:
        """
        Retrieve the entire conversation.

        Returns:
            The list of conversation messages.
        """
        return self.conversation


def main() -> None:
    """
    Main function to orchestrate the script operations:
      1. Parse arguments and configure logging.
      2. Load environment variables and verify the OpenAI key is available.
      3. Manage and possibly reset conversation state.
      4. Build file tree and prepare content for context.
      5. Interact with OpenAI's API, capturing and applying any file updates.
      6. Optionally continue the conversation in a loop until terminated.
    """
    parser = argparse.ArgumentParser(
        description="Run the LLM assistant script."
    )
    parser.add_argument("paths", nargs="*",
                        help="Specific files or folders to include.")
    parser.add_argument(
        "--include-large",
        action="store_true",
        help="Include content of large files (over 1 MB).",
    )
    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        default=0,
        help="Set verbosity level. Use -v, -vv, or -vvv.",
    )
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Dump the entire request payload to a uniquely named JSON file."
    )
    args = parser.parse_args()

    # Set up logging based on verbosity level
    verbosity: int = args.verbosity
    if verbosity == 0:
        logging_level: int = logging.WARNING
    elif verbosity == 1:
        logging_level = logging.INFO
    elif verbosity >= 2:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.WARNING
    logging.basicConfig(level=logging_level,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    # Load environment variables
    env_config: EnvironmentConfig = EnvironmentConfig()
    env_vars: Dict[str, str] = env_config.env_vars

    if not env_vars["OPENAI_KEY"]:
        logging.error(
            "OpenAI API key not found in environment variables (LLM_SH_OPENAI_KEY). Exiting."
        )
        sys.exit(1)

    # Initialise conversation manager
    conversation_manager: ConversationManager = ConversationManager(
        ".llm.json")

    # Check if we need to start a new conversation
    if conversation_manager.conversation:
        while True:
            choice: str = input(
                "A previous conversation is in progress. Do you wish to continue it? (yes/no): "
            ).strip().lower()
            if choice == "yes":
                break
            if choice == "no":
                # Delete llm.md and .llm.json to start a new conversation
                if os.path.exists("llm.md"):
                    os.remove("llm.md")
                if os.path.exists(".llm.json"):
                    os.remove(".llm.json")
                conversation_manager.conversation = []
                conversation_manager.save_conversation()
                break
            print("Please enter 'yes' or 'no'.")

    # Initialise OpenAI handler with optional dump mode
    openai_handler: OpenAIInteraction = OpenAIInteraction(
        env_vars, dump_mode=args.dump
    )

    # Build file tree and contents
    root_dir: str = "."
    include_files: Optional[List[str]] = args.paths if args.paths else None
    file_tree, files_contents = build_file_tree(
        root_dir, include_files, args.include_large
    )

    # Write and read prompt
    user_prompt: str = write_prompt_file()

    # Prepare system prompt
    system_prompt: str = prepare_system_prompt(
        env_vars, file_tree, files_contents)

    # Append messages to conversation
    conversation_manager.append_message("system", system_prompt)
    conversation_manager.append_message("user", user_prompt)

    # Send conversation to OpenAI
    print("Sending conversation to OpenAI API.")
    response_content: Optional[str] = openai_handler.send(
        conversation_manager.get_conversation()
    )

    if not response_content:
        logging.error(
            "No response from OpenAI API. Error details: %s",
            openai_handler.last_error,
        )
        sys.exit(1)

    # Append assistant's response
    conversation_manager.append_message("assistant", response_content)
    conversation_manager.save_conversation()

    # Update llm.md with assistant's response
    with open("llm.md", "a", encoding="utf-8") as response_file:
        response_file.write("\n## Assistant's Response\n\n")
        response_file.write(response_content)

    # Process any file updates
    files_to_update: Dict[str, str] = update_files_from_response(
        response_content)
    if files_to_update:
        process_file_updates(files_to_update)

    # Handle further interaction loop
    handle_interaction_loop(conversation_manager, openai_handler)


def build_file_tree(
    root_dir: str, include_files: Optional[List[str]], include_large: bool
) -> Tuple[List[str], Dict[str, str]]:
    """
    Build a file tree representation and collect file contents.

    Args:
        root_dir: The root directory to scan.
        include_files: Specific files or directories to include, if any.
        include_large: Flag indicating whether to include large files.

    Returns:
        A tuple: (list of relative file paths, dict mapping file paths to contents).
    """
    file_tree: List[str] = []
    files_contents: Dict[str, str] = {}
    ignored_paths: List[str] = get_ignored_paths()

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Exclude ignored directories
        original_dirnames: List[str] = dirnames.copy()
        dirnames[:] = [
            d
            for d in dirnames
            if not should_ignore(os.path.relpath(os.path.join(dirpath, d), root_dir), ignored_paths)
        ]
        if logging.getLogger().getEffectiveLevel() <= logging.DEBUG:
            for directory in original_dirnames:
                rel_path: str = os.path.relpath(
                    os.path.join(dirpath, directory), root_dir)
                if directory not in dirnames:
                    logging.debug("Ignoring directory: %s", rel_path)
                else:
                    logging.debug("Including directory: %s", rel_path)

        for filename in filenames:
            filepath: str = os.path.join(dirpath, filename)
            relative_path: str = os.path.relpath(filepath, root_dir)
            if should_ignore(relative_path, ignored_paths):
                logging.debug("Ignoring file: %s", relative_path)
                continue
            if include_files and not any(
                relative_path == inc or relative_path.startswith(f"{inc}{
                                                                 os.sep}")
                for inc in include_files
            ):
                logging.debug(
                    "File not included by paths filter: %s", relative_path)
                continue
            file_tree.append(relative_path)
            logging.debug("Including file: %s", relative_path)
            process_file_content(filepath, relative_path,
                                 files_contents, include_large)
    return file_tree, files_contents


def process_file_content(
    filepath: str,
    relative_path: str,
    files_contents: Dict[str, str],
    include_large: bool,
) -> None:
    """
    Process and store the content of a file.

    Args:
        filepath: Full path to the file on the filesystem.
        relative_path: Relative path for display or indexing.
        files_contents: Dictionary to store file contents by relative path.
        include_large: Flag indicating whether to include content of large files.
    """
    try:
        file_size: int = os.path.getsize(filepath)
    except OSError:
        file_size = 0
    if any(
        filepath.endswith(ext)
        for ext in [".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".exe", ".dll", ".bin"]
    ):
        files_contents[relative_path] = "[Binary file content omitted]"
        logging.debug("Binary file content omitted: %s", relative_path)
    elif file_size > 1e6 and not include_large:
        if filepath.endswith((".json", ".yaml", ".yml")):
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
                    content: str = file.read()
                    skeleton: str = skeletonize_json_yaml(content)
                    files_contents[relative_path] = skeleton
                    logging.debug(
                        "Included skeletonised content for large file: %s", relative_path
                    )
            except Exception as exc:
                files_contents[relative_path] = (
                    f"[Could not read file for skeletonisation: {exc}]"
                )
                logging.error(
                    "Error reading file for skeletonisation: %s", relative_path
                )
        else:
            files_contents[relative_path] = "[File content omitted due to size]"
            logging.debug(
                "File content omitted due to size: %s", relative_path)
    else:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
                content: str = file.read()
                files_contents[relative_path] = content
                logging.debug("File content read: %s", relative_path)
        except Exception as exc:
            files_contents[relative_path] = f"[Could not read file: {exc}]"
            logging.error("Could not read file: %s, Error: %s",
                          relative_path, exc)


def get_ignored_paths() -> List[str]:
    """
    Get a list of paths to ignore from .gitignore and .llmignore files,
    supplemented by known internal paths.

    Returns:
        A list of paths/patterns that should be ignored during file scanning.
    """
    ignored_paths: List[str] = []
    for ignore_file in [".gitignore", ".llmignore"]:
        if os.path.exists(ignore_file):
            with open(ignore_file, "r", encoding="utf-8") as file:
                lines: List[str] = file.readlines()
            for line in lines:
                stripped_line: str = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    ignored_paths.append(stripped_line)
                    logging.debug(
                        "Added ignore pattern from %s: %s", ignore_file, stripped_line
                    )
    # Always ignore specific workspace and script-related files
    ignored_paths.extend([".git", ".llm.json", "llm.md", "llm.py"])
    logging.debug("Ignored paths: %s", ignored_paths)
    return ignored_paths


def should_ignore(path: str, ignored_paths: List[str]) -> bool:
    """
    Determine if a path should be ignored based on ignore patterns.

    Args:
        path: The path to check.
        ignored_paths: List of patterns indicating ignored paths.

    Returns:
        True if the path should be ignored, otherwise False.
    """
    for pattern in ignored_paths:
        if Path(path).match(pattern) or Path(path).match(f"**/{pattern}"):
            logging.debug("Path %s matches ignore pattern %s", path, pattern)
            return True
    return False


def skeletonize_json_yaml(content: str) -> str:
    """
    Create a skeleton representation of JSON or YAML content for large files.

    Args:
        content: The file content to skeletonise.

    Returns:
        The skeletonised representation as a string.
    """
    try:
        import json
        import yaml  # PyYAML must be installed for parsing YAML

        try:
            data = json.loads(content)
            skeleton = json.dumps(skeletonize_data(data), indent=2)
        except json.JSONDecodeError:
            data = yaml.safe_load(content)
            skeleton = yaml.dump(skeletonize_data(data), indent=2)
        return skeleton
    except Exception as exc:
        logging.error("Error skeletonising content: %s", exc)
        return f"[Error skeletonising file: {exc}]"


def skeletonize_data(data: object) -> object:
    """
    Recursively create a skeleton of data structures for JSON or YAML content.

    NOTE: We use 'object' instead of more specific types here to avoid forcing
    multiple union types. This approach handles a broad range of JSON/YAML values.

    Args:
        data: The data to skeletonise (JSON/YAML).

    Returns:
        The skeletonised version of the data, where complex structures are
        trimmed to a single element or replaced with a type placeholder.
    """
    if isinstance(data, dict):
        return {k: skeletonize_data(v) for k, v in data.items()}
    if isinstance(data, list):
        if data:
            return [skeletonize_data(data[0])]
        return []
    return f"<{type(data).__name__}>"


def write_prompt_file() -> str:
    """
    Create or open llm.md, prompting the user to enter instructions under "## Prompt".

    Returns:
        The user prompt as a string once the user updates llm.md.
    """
    if not os.path.exists("llm.md"):
        with open("llm.md", "w", encoding="utf-8") as file:
            file.write(
                '# llm.md\n\nPlease provide your instructions under the "Prompt" section below.\n\n## Prompt\n\n'
            )
    # Attempt to open llm.md in VSCode if the environment is Codespaces or Dev Containers
    if os.getenv("CODESPACES") == "true" or os.getenv("REMOTE_CONTAINERS") == "true":
        subprocess.run(["code", "llm.md"])
    else:
        print("Please open llm.md and provide your prompt under the 'Prompt' section.")

    print("Waiting for you to write your prompt in llm.md...")
    try:
        initial_mtime: float = os.path.getmtime("llm.md")
    except FileNotFoundError:
        logging.error("llm.md not found. Exiting.")
        sys.exit(1)

    while True:
        time.sleep(1)
        try:
            current_mtime: float = os.path.getmtime("llm.md")
            if current_mtime != initial_mtime:
                break
        except FileNotFoundError:
            logging.error("llm.md has been deleted. Exiting.")
            sys.exit(1)

    with open("llm.md", "r", encoding="utf-8") as file:
        content: str = file.read()
    if "## Prompt" in content:
        prompt: str = content.split("## Prompt", 1)[1].strip()
        if prompt:
            return prompt
    logging.error("No prompt detected in llm.md. Exiting.")
    sys.exit(1)


def prepare_system_prompt(
    env_vars: Dict[str, str], file_tree: List[str], files_contents: Dict[str, str]
) -> str:
    """
    Prepare the system prompt including context, requirements, file tree, and file contents.

    Args:
        env_vars: Dictionary of environment variables used for context.
        file_tree: List of paths for all included files.
        files_contents: Dictionary mapping file paths to their text content.

    Returns:
        The fully populated system prompt string.
    """
    system_prompt_template: str = SYSTEM_PROMPT_TEMPLATE
    current_date: str = datetime.now().strftime("%A, %d %B %Y")
    formatted_system_prompt: str = system_prompt_template.format(
        current_date=current_date,
        GITHUB_USERNAME=env_vars["GITHUB_USERNAME"],
        GITHUB_FULLNAME=env_vars["GITHUB_FULLNAME"],
        GITHUB_EMAIL=env_vars["GITHUB_EMAIL"],
        GITHUB_OWNER=env_vars["GITHUB_OWNER"],
        GITHUB_REPO=env_vars["GITHUB_REPO"],
    )

    # Append file tree and contents
    formatted_system_prompt += "\n\n## Workspace File Tree\n\n"
    for path in file_tree:
        formatted_system_prompt += f"- {path}\n"

    formatted_system_prompt += "\n\n## File Contents\n\n"
    for path in file_tree:
        content: str = files_contents.get(path, "")
        formatted_system_prompt += f"### {path}\n\n"
        formatted_system_prompt += f"```\n{content}\n```\n\n"
    logging.debug("Prepared system prompt.")
    return formatted_system_prompt


def remove_markdown_code_blocks(content_lines: List[str]) -> List[str]:
    """
    Remove Markdown code block markers (```).

    Args:
        content_lines: List of lines between file demarcation markers.

    Returns:
        A list of lines without code block markers.
    """
    cleaned_lines: List[str] = []
    in_code_block: bool = False
    for line in content_lines:
        stripped_line: str = line.strip()
        # Check for the start or end of a code block
        if stripped_line.startswith("```"):
            in_code_block = not in_code_block
            continue
        cleaned_lines.append(line)
    return cleaned_lines


def update_files_from_response(response_text: str) -> Dict[str, str]:
    """
    Extract file updates from the assistant's response, looking for special markers.

    Args:
        response_text: The assistant's entire response text.

    Returns:
        A dictionary mapping filenames to updated content extracted from the response.
    """
    files_to_update: Dict[str, str] = {}
    lines: List[str] = response_text.splitlines()
    i: int = 0
    while i < len(lines):
        line: str = lines[i]
        if line.startswith("<<LLM_FILE_START:"):
            filename: str = line[len("<<LLM_FILE_START:"):].rstrip(">>").strip()
            content_lines: List[str] = []
            i += 1
            while i < len(lines):
                if lines[i].startswith("<<LLM_FILE_END>>"):
                    break
                content_lines.append(lines[i])
                i += 1
            # Clean the content lines by removing markdown code blocks
            content_lines = remove_markdown_code_blocks(content_lines)
            file_content: str = "\n".join(content_lines).strip()
            files_to_update[filename] = file_content
            logging.debug("Found file update for: %s", filename)
        else:
            i += 1
    return files_to_update


def process_file_updates(files_to_update: Dict[str, str]) -> None:
    """
    Prompt the user and process file updates if confirmed.

    Args:
        files_to_update: Mapping of filenames to their updated contents.
    """
    print("The assistant has provided updates to the following files:")
    for filename in files_to_update.keys():
        print(f"- {filename}")
    while True:
        choice: str = input(
            "Do you wish to automatically update them? (yes/no): "
        ).strip().lower()
        if choice == "yes":
            if not git_is_clean():
                print("Git repository is not clean. Committing current changes.")
                git_commit_all()
            atomically_write_files(files_to_update)
            print("Files have been updated.")
            break
        if choice == "no":
            print("Files were not updated.")
            break
        print("Please enter 'yes' or 'no'.")


def atomically_write_files(files_dict: Dict[str, str]) -> None:
    """
    Atomically write updated files to the file system to avoid partial writes.

    Args:
        files_dict: A dictionary mapping filenames to their desired new content.
    """
    for filename, content in files_dict.items():
        dirname: str = os.path.dirname(filename)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
            logging.debug("Created directory: %s", dirname)
        temp_filename: str = f"{filename}.tmp"
        with open(temp_filename, "w", encoding="utf-8") as file:
            file.write(content)
        shutil.move(temp_filename, filename)
        logging.debug("Updated file: %s", filename)


def git_is_clean() -> bool:
    """
    Check if the Git repository is clean (no uncommitted changes).

    Returns:
        True if the Git repository is clean, otherwise False.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )
    is_clean: bool = not result.stdout.strip()
    logging.debug("Git repository is clean: %s", is_clean)
    return is_clean


def git_commit_all() -> None:
    """
    Commit all changes in the current Git repository with a standard commit message.
    """
    subprocess.run(["git", "add", "."])
    commit_message: str = f"LLM Auto Commit {
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    subprocess.run(["git", "commit", "-m", commit_message])
    logging.info("Committed current changes to Git.")


def handle_interaction_loop(
    conversation_manager: ConversationManager, openai_handler: OpenAIInteraction
) -> None:
    """
    Handle a loop allowing the user to continue responding to the assistant.

    Args:
        conversation_manager: Manages and persists the conversation state.
        openai_handler: Interacts with the OpenAI API to get responses.
    """
    while True:
        cont: str = input(
            "Do you wish to respond to the assistant? (yes/no): "
        ).strip().lower()
        if cont == "yes":
            # Append new section to llm.md
            with open("llm.md", "a", encoding="utf-8") as file:
                file.write("\n## Your Response\n\n")
            print("Please provide your response in llm.md under 'Your Response' section.")

            # Wait for user to update the file
            print("Waiting for you to write your response in llm.md...")
            try:
                initial_mtime: float = os.path.getmtime("llm.md")
            except FileNotFoundError:
                logging.error("llm.md not found. Exiting.")
                sys.exit(1)

            while True:
                time.sleep(1)
                try:
                    current_mtime: float = os.path.getmtime("llm.md")
                    if current_mtime != initial_mtime:
                        break
                except FileNotFoundError:
                    logging.error("llm.md has been deleted. Exiting.")
                    sys.exit(1)

            # Read user's response
            with open("llm.md", "r", encoding="utf-8") as file:
                content: str = file.read()

            if "## Your Response" in content:
                user_response: str = content.split(
                    "## Your Response", 1)[1].strip()
                if user_response:
                    conversation_manager.append_message("user", user_response)
                    response_content: Optional[str] = openai_handler.send(
                        conversation_manager.get_conversation()
                    )

                    if not response_content:
                        logging.error(
                            "No response from OpenAI API. Error details: %s",
                            openai_handler.last_error,
                        )
                        sys.exit(1)

                    # Append assistant's response to conversation
                    conversation_manager.append_message(
                        "assistant", response_content)
                    conversation_manager.save_conversation()

                    # Update llm.md with assistant's response
                    with open("llm.md", "a", encoding="utf-8") as resp_file:
                        resp_file.write("\n## Assistant's Response\n\n")
                        resp_file.write(response_content)

                    # Process any file updates
                    files_to_update: Dict[str, str] = update_files_from_response(
                        response_content
                    )
                    if files_to_update:
                        process_file_updates(files_to_update)
                else:
                    print(
                        "No user response detected in llm.md. Exiting the conversation.")
                    break
            else:
                print(
                    "No 'Your Response' section found in llm.md. Exiting the conversation.")
                break
        elif cont == "no":
            print("Conversation ended.")
            break
        else:
            print("Please enter 'yes' or 'no'.")


if __name__ == "__main__":
    main()
