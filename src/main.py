import os
import re
import feedparser
import openai
import pytz
import logging
from openai import OpenAI
from datetime import datetime
from pathlib import Path
from pydub import AudioSegment  # Ensure you have pydub and ffmpeg installed
from tempfile import NamedTemporaryFile
from random import choice, randint


logging.basicConfig(level=logging.DEBUG)

# Constants for placeholders
INTRO_PLACEHOLDER = "[SFX: NEWS INTRO]"
ARTICLE_START_PLACEHOLDER = "[SFX: ARTICLE START]"
ARTICLE_BREAK_PLACEHOLDER = "[SFX: ARTICLE BREAK]"
OUTRO_PLACEHOLDER = "[SFX: NEWS OUTRO]"


# Environment Variable configuration
AUDIO_FILES_ENV = {
    'INTRO': 'NEWS_READER_AUDIO_INTRO',
    'OUTRO': 'NEWS_READER_AUDIO_OUTRO',
    'BREAK': 'NEWS_READER_AUDIO_BREAK',
    'FIRST': 'NEWS_READER_AUDIO_FIRST'
}

TIMINGS_ENV = {
    'INTRO': 'NEWS_READER_TIMING_INTRO',
    'OUTRO': 'NEWS_READER_TIMING_OUTRO',
    'BREAK': 'NEWS_READER_TIMING_BREAK',
    'FIRST': 'NEWS_READER_TIMING_FIRST'
}

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
    """Generates a news script using the OpenAI API with the given news items and prompt instructions.
    
    Args:
        news_items (list): A list of dictionaries representing news articles.
        prompt_instructions (str): A string containing the GPT-4 prompt instructions.
        station_name (str): The station's name.
        reader_name (str): The news reader's name.
        current_time (str): The current time as a string.
        api_key (str): A string representing the OpenAI API key.
    
    Returns:
        str: A string containing the generated script.
    
    Raises:
        ValueError: If news_items is empty or None.
        openai.error.OpenAIError: If an error occurs within the OpenAI API call.
    """
    if not news_items:
        raise ValueError("The list of news items is empty or None.")

    client = OpenAI(api_key=api_key)

    # OpenAI GPT-4 token limit
    max_tokens = 4095

    news_content = "\n\n".join(
        [f"{item['TITLE']}\n{item['DESCRIPTION']}" for item in news_items]
    )
    station_ident = f'Station Name is "{station_name}"\nNews reader name is "{reader_name}"'
    time_ident = f'Current date and time is "{current_time}"\n'

    prompt_length = len(prompt_instructions.split())
    news_length = len(news_content.split())

    # Check if the content is too long for the API
    if prompt_length + news_length > max_tokens:
        raise ValueError(
            f"The combined length of the prompt instructions and news content "
            f"exceeds the maximum token limit for the OpenAI API: {max_tokens} tokens."
        )

    user_prompt = (
        time_ident
        + station_ident
        + "\n\n"
        + news_content
    )  # Concatenate instructions with news items

    try:
        response = client.chat.completions.create(model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt_instructions},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=max_tokens - prompt_length)  # Reserve space for the prompt)
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        raise openai.OpenAIError(f"An error occurred with the OpenAI API: {e}")
    
def split_script(news_script, max_length=4094):
    """
    Splits the news script into manageable chunks, ensuring we split at paragraph boundaries.
    
    Args:
        news_script: A string containing the entire news script to be converted.
        max_length: The maximum character length for each chunk.
    
    Returns:
        A list of strings, each representing a chunk of the news script.
    """
    paragraphs = news_script.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 > max_length:  # +2 accounts for the '\n\n'
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            current_chunk += ("\n\n" if current_chunk else "") + paragraph
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def generate_speech(news_script_chunk, api_key, voice, quality, output_format):
    """
    Generates spoken audio from the given text script chunk using OpenAI's TTS API.
    
    Args:
        news_script_chunk: A string containing the news script chunk to be converted to audio.
        api_key: A string representing the OpenAI API key.
        voice: A string representing the chosen voice for the TTS.
        quality: A string representing the chosen quality for the TTS (e.g. 'tts-1' or 'tts-1-hd').
        output_format: A string representing the desired output audio format.
    
    Returns:
        A temporary file containing the generated audio.
    """
    client = OpenAI(api_key=api_key)

    try:
        response = client.audio.speech.create(
            model=quality,
            voice=voice,
            input=news_script_chunk,
            response_format=output_format
        )

        with NamedTemporaryFile(delete=False, suffix=f".{output_format}") as temp_audio_file:
            temp_audio_file.write(response.content)  # Directly write the response content to the file
        return temp_audio_file.name
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

def concatenate_audio_files(audio_files, output_path, output_format):
    """
    Concatenates a list of audio files into a single audio file.
    
    Args:
        audio_files: A list of file paths representing the audio files to concatenate.
        output_path: The file path where the concatenated audio will be saved.
        output_format: The format of the output audio file (e.g., 'flac').
    """
    final_audio = AudioSegment.empty()
    for audio_file in audio_files:
        segment = AudioSegment.from_file(audio_file, format=output_format)
        final_audio += segment
    
    final_audio.export(output_path, format=output_format)

def get_random_file(file_path):
    """Return the base file path or a random numbered file if exists."""
    base_path = Path(file_path)
    if not base_path.exists():
        # Check for numbered files
        numbered_files = list(base_path.parent.glob(f"{base_path.stem}_*.{base_path.suffix}"))
        if not numbered_files:
            logging.warning(f"Audio file {base_path} not found and no numbered alternatives exist.")
            return None
        return str(choice(numbered_files))
    return str(base_path)

def check_audio_files():
    """Check the existence of necessary audio files in the environment."""
    checked_files = {}
    for key, env_var in AUDIO_FILES_ENV.items():
        file_path = os.getenv(env_var, None)
        if file_path:
            random_file = get_random_file(file_path)
            if random_file:
                checked_files[key] = random_file
    return checked_files

def split_and_strip_script(news_script):
    """Split the script by placeholders and return sections with placeholders."""
    sections = re.split(f"({INTRO_PLACEHOLDER}|{ARTICLE_START_PLACEHOLDER}|{ARTICLE_BREAK_PLACEHOLDER}|{OUTRO_PLACEHOLDER})", news_script)
    stripped_sections = [section.strip() for section in sections if section.strip()]
    return stripped_sections

def generate_mixed_audio(sfx_file, speech_file, timing):
    """Generate the mixed audio segment based on provided timing."""
    sfx_audio = AudioSegment.from_file(sfx_file)
    speech_audio = AudioSegment.from_file(speech_file)
    
    if timing:
        timing_offset = int(timing)
        sfx_duration = len(sfx_audio)
        if timing_offset > sfx_duration:
            padding = timing_offset - sfx_duration
            combined_audio = sfx_audio + AudioSegment.silent(duration=padding) + speech_audio
        else:
            combined_audio = sfx_audio.overlay(speech_audio, position=timing_offset)
    else:
        combined_audio = sfx_audio + speech_audio
    
    return combined_audio

def main():
    """Main function that fetches, parses, and processes the RSS feed into audio."""
    feed_url = os.getenv('NEWS_READER_RSS', 'https://www.sbs.com.au/news/topic/latest/feed')
    station_name = os.getenv('NEWS_READER_STATION_NAME', 'Live News 24')
    reader_name = os.getenv('NEWS_READER_READER_NAME', 'Burnie Housedown')
    tts_voice = os.getenv('NEWS_READER_TTS_VOICE', 'alloy')
    tts_quality = os.getenv('NEWS_READER_TTS_QUALITY', 'tts-1')
    output_format = os.getenv('NEWS_READER_OUTPUT_FORMAT', 'flac')

    # Fetch the OpenAI API key from environment variables.
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if openai_api_key is None:
        raise ValueError("The OpenAI API key must be set in the environment variable 'OPENAI_API_KEY'.")

    # Load the prompt file path from the NEWS_READER_PROMPT_FILE environment variable, or use the default.
    prompt_file_path = os.getenv('NEWS_READER_PROMPT_FILE', './prompt.md')

    try:
        prompt_instructions = read_prompt_file(prompt_file_path)
    except Exception as e:
        logging.error(f"Error reading prompt file: {e}")
        return

    # Timezone
    timezone_str = os.getenv('NEWS_READER_TIMEZONE', 'UTC')
    try:
        timezone = pytz.timezone(timezone_str)
    except Exception as e:
        logging.error(f"Invalid timezone '{timezone_str}', defaulting to UTC")
        timezone = pytz.UTC
    # Get the current time and date in the specified timezone.
    current_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S %Z')

    # Parse the RSS feed using the defined configuration.
    news_items = parse_rss_feed(feed_url, FEED_CONFIG)

    # Generate the news script using the OpenAI API.
    news_script = generate_news_script(news_items, prompt_instructions, station_name, reader_name, current_time, openai_api_key)
   
    logging.debug(f"# News Script\n\n{news_script}")

    # Check audio files
    audio_files = check_audio_files()

    # Split the script into sections
    script_sections = split_and_strip_script(news_script)

    output_dir = os.getenv('NEWS_READER_OUTPUT_DIR', '.')
    output_file_template = os.getenv('NEWS_READER_OUTPUT_FILE', 'livenews.%EXT%').replace('%EXT%', output_format)
    output_file = output_file_template.replace('%Y%', datetime.now().strftime('%Y')).replace('%m%', datetime.now().strftime('%m')).replace('%d%', datetime.now().strftime('%d')).replace('%H%', datetime.now().strftime('%H')).replace('%M%', datetime.now().strftime('%M')).replace('%S%', datetime.now().strftime('%S'))
    output_file_path = Path(output_dir) / output_file

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.access(output_dir, os.W_OK):
        raise PermissionError(f"The output directory '{output_dir}' is not writable.")

    final_audio = AudioSegment.empty()
    speech_audio_files = []
    current_index = 0

    while current_index < len(script_sections):
        section = script_sections[current_index]
        if section in [INTRO_PLACEHOLDER, ARTICLE_START_PLACEHOLDER, ARTICLE_BREAK_PLACEHOLDER, OUTRO_PLACEHOLDER]:
            sfx_key = section.split(":")[1].strip().replace(" ", "_")
            sfx_file = audio_files.get(sfx_key.upper(), None)
            timing_key = TIMINGS_ENV.get(sfx_key.upper(), None)
            timing_value = os.getenv(timing_key, "None") if timing_key else "None"

            if sfx_file:
                if current_index + 1 < len(script_sections):
                    speech_text = script_sections[current_index + 1]
                    speech_audio_file = generate_speech(speech_text, openai_api_key, tts_voice, tts_quality, output_format)
                    mixed_audio = generate_mixed_audio(sfx_file, speech_audio_file, timing_value)
                    final_audio += mixed_audio
                    speech_audio_files.append(speech_audio_file)
                    current_index += 2
                else:
                    raise ValueError("SFX placeholder found at the end without subsequent text.")
            else:
                current_index += 1
        else:
            # Handle normal speech section without SFX
            speech_audio_file = generate_speech(section, openai_api_key, tts_voice, tts_quality, output_format)
            final_audio += AudioSegment.from_file(speech_audio_file)
            speech_audio_files.append(speech_audio_file)
            current_index += 1

    final_audio.export(output_file_path, format=output_format)
    logging.info(f"News audio generated and saved to {output_file_path}")

if __name__ == '__main__':
    main()