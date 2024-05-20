import os
import re
import feedparser
import openai
import pytz
from openai import OpenAI
from datetime import datetime
from pathlib import Path


# RSS Feed configuration
FEED_CONFIG = {
    'TITLE': 'title',
    'DESCRIPTION': 'description',
    'CATEGORY': 'category',
    'IGNORE_PATTERNS': [
        r'SBS News in Easy English \d+ \w+ \d{4}',
        r'News Bulletin \d+ \w+ \d{4}'
    ]
}

def parse_rss_feed(feed_url, config):
    """Parses the RSS feed, filtering out ignored articles using regex patterns.
    
    Args:
        feed_url: A string representing the URL of the RSS feed.
        config: A dictionary containing field mappings and ignore patterns.
        
    Returns:
        A list of dictionaries, each representing a news item.
    """
    feed = feedparser.parse(feed_url)
    parsed_items = []

    for entry in feed.entries:
        if any(re.search(pattern, entry.title) for pattern in config['IGNORE_PATTERNS']):
            continue

        item = {config_field: entry.get(feed_field, None) for config_field, feed_field in config.items() if config_field != 'IGNORE_PATTERNS'}

        parsed_items.append(item)

    return parsed_items

def generate_news_script(news_items, prompt_instructions, station_name, reader_name, current_time, api_key):
    """Generates a news script using the OpenAI API with given news items and prompt instructions.
    
    Args:
        news_items: A list of dictionaries representing news articles.
        prompt_instructions: A string containing the GPT-4 prompt instructions.
        station_name: The stations name
        reader_name: The news readers name
        current_time: The current time as a string
        api_key: A string representing the OpenAI API key.
    
    Returns:
        A string containing the generated script.
        
    Raises:
        ValueError: If news_items is empty or None.
        openai.error.OpenAIError: If an error occurs within the OpenAI API call.
    """
    if not news_items:
        raise ValueError("The list of news items is empty or None.")
    
    client = OpenAI(api_key=api_key)

    # Set the maximum number of tokens for the OpenAI API
    max_tokens = 4095

    news_content = "\n\n".join([f"{item['TITLE']}\n{item['DESCRIPTION']}" for item in news_items])
    station_ident = f"Station Name is \"{station_name}\"\nNews reader name is \"{reader_name}\""
    
    time_ident = f"Current date and time is \"{current_time}\"\n"

    prompt_length = len(prompt_instructions.split())
    news_length = len(news_content.split())

    # Check if the content is too long for the API
    if prompt_length + news_length > max_tokens:
        raise ValueError(f"The combined length of the prompt instructions and news content exceeds the maximum token limit for the OpenAI API: {max_tokens} tokens.")

    full_prompt = prompt_instructions + "\n\n" + time_ident + station_ident + "\n\n" + news_content  # Concatenate instructions with news items

    try:
        response = client.chat.completions.create(model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt_instructions},
            {"role": "user", "content": full_prompt}
        ],
        max_tokens=max_tokens - prompt_length)  # Reserve space for the prompt)
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        raise openai.OpenAIError(f"An error occurred with the OpenAI API: {e}")

def generate_speech(news_script, api_key, voice, quality, output_file):
    """
    Generates spoken audio from the given text script using OpenAI's TTS API.
    
    Args:
        news_script: A string containing the news script to be converted to audio.
        api_key: A string representing the OpenAI API key.
        voice: A string representing the chosen voice for the TTS.
        quality: A string representing the chosen quality for the TTS (e.g. 'tts-1' or 'tts-1-hd').
        output_file: A string representing the file path where the output audio will be saved.
    """
    client = OpenAI(api_key=api_key)

    try:
        response = client.audio.speech.create(
            model=quality,
            voice=voice,
            input=news_script
        )

        response.stream_to_file(output_file)
    except openai.OpenAIError as e:
        raise openai.OpenAIError(f"An error occurred with the OpenAI TTS API: {e}")

def read_prompt_file(file_path):
    """Reads the contents of a prompt file with error handling.
    
    Args:
        file_path: A string representing the path to the prompt file.
    
    Returns:
        A string containing the contents of the file.
        
    Raises:
        FileNotFoundError: If the prompt file does not exist.
        PermissionError: If the prompt file cannot be opened due to insufficient permissions.
        IOError: If an I/O error occurs when accessing the file.
        Exception: If an unspecified error occurs.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"The prompt file at '{file_path}' was not found.")
    except PermissionError:
        raise PermissionError(f"Permission denied when trying to read the prompt file at '{file_path}'.")
    except IOError as e:
        raise IOError(f"An I/O error occurred while reading the prompt file at '{file_path}': {e}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred while reading the prompt file: {e}")

def main():
    """Main function that fetches, parses, and processes the RSS feed into audio."""
    feed_url = os.getenv('NEWS_READER_RSS', 'https://www.sbs.com.au/news/topic/latest/feed')
    station_name = os.getenv('NEWS_READER_STATION_NAME', 'Live News 24')
    reader_name = os.getenv('NEWS_READER_READER_NAME', 'Burnie Housedown')
    tts_voice = os.getenv('NEWS_READER_TTS_VOICE', 'alloy')
    tts_quality = os.getenv('NEWS_READER_TTS_QUALITY', 'tts-1')

    # Fetch the OpenAI API key from environment variables.
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if openai_api_key is None:
        raise ValueError("The OpenAI API key must be set in the environment variable 'OPENAI_API_KEY'.")

    # Load the prompt file path from the NEWS_READER_PROMPT_FILE environment variable, or use the default
    prompt_file_path = os.getenv('NEWS_READER_PROMPT_FILE', './prompt.md')

    try:
        prompt_instructions = read_prompt_file(prompt_file_path)
    except Exception as e:
        print(f"Error: {e}")
        return

    # Timezone
    timezone_str = os.getenv('NEWS_READER_TIMEZONE', 'UTC')
    try:
        timezone = pytz.timezone(timezone_str)
    except Exception as e:
        print(f"Invalid timezone '{timezone_str}', defaulting to UTC")
        timezone = pytz.UTC
    # Get the current time and date in the specified timezone
    current_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S %Z')

    # Parse the RSS feed using the defined configuration.
    news_items = parse_rss_feed(feed_url, FEED_CONFIG)

    # Generate the news script using the OpenAI API.
    news_script = generate_news_script(news_items, prompt_instructions, station_name, reader_name, current_time, openai_api_key)
    
    # Prepare the output file name with timestamp if template is provided
    output_dir = os.getenv('NEWS_READER_OUTPUT_DIR', '.')
    output_file_template = os.getenv('NEWS_READER_OUTPUT_FILE', 'livenews.%EXT%').replace('%EXT%', 'mp3')
    output_file = output_file_template.replace('%Y%', datetime.now().strftime('%Y')).replace('%m%', datetime.now().strftime('%m')).replace('%d%', datetime.now().strftime('%d')).replace('%H%', datetime.now().strftime('%H')).replace('%M%', datetime.now().strftime('%M')).replace('%S%', datetime.now().strftime('%S'))
    output_file_path = Path(output_dir) / output_file

    # Ensure the output directory exists and is writable
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.access(output_dir, os.W_OK):
        raise PermissionError(f"The output directory '{output_dir}' is not writable.")

    # Generate speech audio from the script
    generate_speech(news_script, openai_api_key, tts_voice, tts_quality, str(output_file_path))

    print(f"News audio generated and saved to {output_file_path}")

if __name__ == '__main__':
    main()