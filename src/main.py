import os
import re
import feedparser
import openai
import pytz
import logging
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI
from datetime import datetime
from pathlib import Path
from pydub import AudioSegment  # Ensure you have ffmpeg installed
from tempfile import NamedTemporaryFile
from random import choice
from ftplib import FTP

logging.basicConfig(level=logging.INFO)

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

# BOM data configuration
BOM_PRODUCT_ID = os.getenv('NEWS_READER_BOM_PRODUCT_ID', 'IDN10064')
STATION_CITY = os.getenv('NEWS_READER_STATION_CITY', 'Sydney')
STATION_COUNTRY = os.getenv('NEWS_READER_STATION_COUNTRY', 'Australia')

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
        feed_url (str): URL of the RSS feed.
        config (dict): Configuration dictionary for field mappings and ignore patterns.

    Returns:
        list: List of dictionaries, each representing a news item.
    """
    feed = feedparser.parse(feed_url)
    parsed_items = []

    for entry in feed.entries:
        if any(re.search(pattern, entry.title) for pattern in config['IGNORE_PATTERNS']):
            continue

        item = {config_field: entry.get(feed_field, None)
                for config_field, feed_field in config.items()
                if config_field != 'IGNORE_PATTERNS'}

        parsed_items.append(item)

    return parsed_items

def fetch_bom_data(product_id):
    """Fetches the BOM data from the FTP server for the provided product ID.

    Args:
        product_id (str): The BOM product ID.

    Returns:
        str or None: Weather information as a string if successful, None otherwise.
    """
    ftp_url = 'ftp.bom.gov.au'
    ftp_path = f'anon/gen/fwo/{product_id}.xml'

    try:
        # Connect to the FTP server and retrieve the file
        ftp = FTP(ftp_url)
        ftp.login()
        weather_data = []

        ftp.retrbinary('RETR ' + ftp_path, weather_data.append)
        ftp.quit()

        # Join the retrieved binary data and parse as XML
        weather_data = b''.join(weather_data)
        root = ET.fromstring(weather_data)

        # Find the first area that has forecast data
        for area in root.findall(".//area"):
            forecast_period_now = area.find("forecast-period[@index='0']")
            
            if forecast_period_now is not None:
                forecast_icon_code = forecast_period_now.find("element[@type='forecast_icon_code']")
                
                if forecast_icon_code is not None:
                    description = area.get("description")
                    forecast_now_precis = forecast_period_now.find("text[@type='precis']").text if forecast_period_now.find("text[@type='precis']") is not None else "No description"
                    forecast_now_pop = forecast_period_now.find("text[@type='probability_of_precipitation']").text if forecast_period_now.find("text[@type='probability_of_precipitation']") is not None else "No data"

                    # Get forecast period for the immediate future
                    forecast_period_future = area.find("forecast-period[@index='1']")
                    if forecast_period_future is not None:
                        future_min_temp = forecast_period_future.find("element[@type='air_temperature_minimum']").text if forecast_period_future.find("element[@type='air_temperature_minimum']") is not None else "No data"
                        future_max_temp = forecast_period_future.find("element[@type='air_temperature_maximum']").text if forecast_period_future.find("element[@type='air_temperature_maximum']") is not None else "No data"
                        forecast_future_precis = forecast_period_future.find("text[@type='precis']").text if forecast_period_future.find("text[@type='precis']") is not None else "No description"
                        forecast_future_pop = forecast_period_future.find("text[@type='probability_of_precipitation']").text if forecast_period_future.find("text[@type='probability_of_precipitation']") is not None else "No data"

                        return (
                            f"Weather in {description}, {STATION_COUNTRY}: {forecast_now_precis} "
                            f"with a {forecast_now_pop} chance of precipitation. For tomorrow, "
                            f"expect a low of {future_min_temp}°C and a high of {future_max_temp}°C with {forecast_future_precis} "
                            f"and a {forecast_future_pop} chance of precipitation."
                        )

        # If no forecast data is found
        return None

    except Exception as e:
        logging.error(f"Failed to fetch BOM data: {e}")
        return None

def get_timing_value(env_key, default="None"):
    """Retrieve the timing value from the environment.

    Args:
        env_key (str): The environment variable key.
        default (str): The default value if the variable is not set.

    Returns:
        str: The timing value as a string.
    """
    return os.getenv(env_key, default)

def generate_news_script(news_items, prompt_instructions, station_name, reader_name, current_time, api_key):
    """Generates a news script using the OpenAI API.

    Args:
        news_items (list): List of dictionaries representing news articles.
        prompt_instructions (str): Prompt instructions for GPT-4.
        station_name (str): Name of the station.
        reader_name (str): Name of the news reader.
        current_time (str): Current time.
        api_key (str): OpenAI API key.

    Returns:
        str: Generated script.

    Raises:
        ValueError: If news_items is empty.
        openai.error.OpenAIError: If an error occurs within the OpenAI API call.
    """
    if not news_items:
        raise ValueError("The list of news items is empty or None.")

    client = OpenAI(api_key=api_key)

    max_tokens = 4095
    news_content = "\n\n".join(
        [f"{index + 1}. **Headline:** {item['TITLE']}\n   **Category:** {item.get('CATEGORY', 'General')}\n   **Description:** {item['DESCRIPTION']}"
        for index, item in enumerate(news_items)]
    )
    station_ident = f'Station Name is "{station_name}"\nStation city is "{STATION_CITY}"\nStation country is "{STATION_COUNTRY}"\nNews reader name is "{reader_name}"'
    time_ident = f'Current date and time is "{current_time}"\n'

    prompt_length = len(prompt_instructions.split())
    news_length = len(news_content.split())

    if prompt_length + news_length > max_tokens:
        raise ValueError(
            f"The combined length of the prompt instructions and news content "
            f"exceeds the maximum token limit for the OpenAI API: {max_tokens} tokens."
        )

    user_prompt = (
        time_ident + station_ident + "\n\n" + news_content
    )
    
    logging.info(f"User prompt: {user_prompt}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_instructions},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens - prompt_length
        )
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        raise openai.OpenAIError(f"An error occurred with the OpenAI API: {e}")

def clean_script(script):
    """Cleans the script by removing lines with formatting markers."""
    cleaned_lines = []
    for line in script.splitlines():
        if line.strip() not in ["```plaintext", "```"]:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)    

def generate_speech(news_script_chunk, api_key, voice, quality, output_format):
    """Generates spoken audio from the given text script chunk using OpenAI's TTS API.
    
    Args:
        news_script_chunk (str): News script chunk to be converted to audio.
        api_key (str): OpenAI API key.
        voice (str): Chosen voice for the TTS.
        quality (str): Chosen quality for the TTS (e.g. 'tts-1' or 'tts-1-hd').
        output_format (str): Desired output audio format.

    Returns:
        str: Path to the temporary file containing the generated audio.
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
            temp_audio_file.write(response.content)
            temp_audio_file_path = temp_audio_file.name

        # Normalize the audio
        audio = AudioSegment.from_file(temp_audio_file_path)
        normalized_audio = audio.apply_gain(-audio.max_dBFS)  # Normalize to 0 dBFS

        normalized_audio.export(temp_audio_file_path, format=output_format)
        
        return temp_audio_file_path
    except openai.OpenAIError as e:
        raise openai.OpenAIError(f"An error occurred with the OpenAI TTS API: {e}")

def read_prompt_file(file_path):
    """Reads the contents of a prompt file with error handling.

    Args:
        file_path (str): Path to the prompt file.

    Returns:
        str: Contents of the prompt file.

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
    """Concatenates a list of audio files into a single audio file.

    Args:
        audio_files (list): List of file paths representing the audio files to concatenate.
        output_path (str): File path where the concatenated audio will be saved.
        output_format (str): Format of the output audio file.
    """
    final_audio = AudioSegment.empty()
    for audio_file in audio_files:
        segment = AudioSegment.from_file(audio_file, format=output_format)
        final_audio += segment

    final_audio.export(output_path, format=output_format)

def get_random_file(file_path):
    """Returns the base file path or a random numbered file if exists.
    
    Args:
        file_path (str): Path to the audio file.

    Returns:
        str: Path to the base file or a random numbered file, or None if not found.
    """
    base_path = Path(file_path)
    if base_path.exists():
        return str(base_path)

    # Construct patterns to search for numbered files
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent
    numbered_files = list(parent.glob(f"{stem}_*{suffix}"))
    
    if numbered_files:
        selected_file = str(choice(numbered_files))
        logging.info(f"Using random audio file: {selected_file}")
        return selected_file

    logging.warning(f"Audio file {base_path} not found and no numbered alternatives exist.")
    return None

def check_audio_files():
    """Checks the existence of necessary audio files in the environment.

    Returns:
        dict: Dictionary of audio file paths for each key.
    """
    checked_files = {}
    for key, env_var in AUDIO_FILES_ENV.items():
        file_path = os.getenv(env_var, None)
        if file_path:
            random_file = get_random_file(file_path)
            if random_file:
                checked_files[key] = random_file
                logging.info(f"Audio file found for {key}: {random_file}")
            else:
                logging.warning(f"Audio file for {key} specified as {file_path} was not found and no alternatives exist.")
        else:
            logging.warning(f"Environment variable {env_var} for {key} not set.")
    return checked_files

def generate_mixed_audio(sfx_file, speech_file, timing):
    """Generate the mixed audio segment based on the provided timing."""
    sfx_audio = AudioSegment.from_file(sfx_file)
    speech_audio = AudioSegment.from_file(speech_file)
    
    logging.info(f"Mixing audio with timing: {timing}")

    if timing.lower() != "none":
        timing_offset = int(timing)
        sfx_duration = len(sfx_audio)
        speech_duration = len(speech_audio)
        total_duration = timing_offset + speech_duration
        logging.info(f"Overlaying speech at offset {timing_offset}ms of SFX duration {sfx_duration}ms for total duration of {total_duration}ms")

        if timing_offset > sfx_duration:
            # Add silence after SFX for the timing offset
            padding = timing_offset - sfx_duration
            combined_audio = sfx_audio + AudioSegment.silent(duration=padding) + speech_audio
        else:
            # Overlay speech onto SFX at the specified timing offset
            combined_audio = sfx_audio.overlay(speech_audio, position=timing_offset)
            if timing_offset + speech_duration > sfx_duration:
                # Add remaining speech to the end if extends beyond SFX
                combined_audio = combined_audio + speech_audio[sfx_duration-timing_offset:]
    else:
        logging.info("No overlay timing specified, appending speech to SFX")
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

    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        raise ValueError("The OpenAI API key must be set in the environment variable 'OPENAI_API_KEY'.")

    prompt_file_path = os.getenv('NEWS_READER_PROMPT_FILE', './prompt.md')

    try:
        prompt_instructions = read_prompt_file(prompt_file_path)
    except Exception as e:
        logging.error(f"Error reading prompt file: {e}")
        return

    timezone_str = os.getenv('NEWS_READER_TIMEZONE', 'UTC')
    try:
        timezone = pytz.timezone(timezone_str)
    except Exception as e:
        logging.error(f"Invalid timezone '{timezone_str}', defaulting to UTC")
        timezone = pytz.UTC

    current_time = datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S %Z')

    news_items = parse_rss_feed(feed_url, FEED_CONFIG)

    if not news_items:
        logging.warning("No news items found in the feed.")
        return

    # Fetch BOM weather data
    weather_info = fetch_bom_data(BOM_PRODUCT_ID)
    
    # Append weather info as the first item in the news items if available and valid
    if weather_info and "No data" not in weather_info and "No description" not in weather_info:
        news_items.insert(0, {'TITLE': 'Weather Report', 'DESCRIPTION': weather_info, 'CATEGORY': 'weather'})
    else:
        logging.warning("Valid weather data not available. Skipping weather report.")

    news_script = generate_news_script(
        news_items, prompt_instructions, station_name, reader_name, current_time, openai_api_key
    )

    if not news_script:
        logging.warning("Generated news script is empty.")
        return

    # Clean the news script to remove formatting markers
    news_script = clean_script(news_script)

    logging.info(f"# News Script\n\n{news_script}")

    audio_files = check_audio_files()
    logging.info(f"Checked audio files: {audio_files}")

    # Correctly split the script by placeholders
    pattern = re.compile(
        f"({re.escape(INTRO_PLACEHOLDER)}|{re.escape(ARTICLE_START_PLACEHOLDER)}|"
        f"{re.escape(ARTICLE_BREAK_PLACEHOLDER)}|{re.escape(OUTRO_PLACEHOLDER)})"
    )
    script_sections = pattern.split(news_script)
    script_sections = [section.strip() for section in script_sections if section.strip()]

    output_dir = os.getenv('NEWS_READER_OUTPUT_DIR', '.')
    output_file_template = os.getenv('NEWS_READER_OUTPUT_FILE', 'livenews.%EXT%').replace('%EXT%', output_format)
    output_file = output_file_template.replace('%Y%', datetime.now().strftime('%Y')).replace(
        '%m%', datetime.now().strftime('%m')).replace('%d%', datetime.now().strftime('%d')).replace(
        '%H%', datetime.now().strftime('%H')).replace('%M%', datetime.now().strftime('%M')).replace(
        '%S%', datetime.now().strftime('%S'))
    output_file_path = Path(output_dir) / output_file

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    if not os.access(output_dir, os.W_OK):
        raise PermissionError(f"The output directory '{output_dir}' is not writable.")

    final_audio = AudioSegment.empty()
    speech_audio_files = []
    current_index = 0
    placeholder_to_key = {
        INTRO_PLACEHOLDER: "INTRO",
        ARTICLE_START_PLACEHOLDER: "FIRST",
        ARTICLE_BREAK_PLACEHOLDER: "BREAK",
        OUTRO_PLACEHOLDER: "OUTRO"
    }

    while current_index < len(script_sections):
        section = script_sections[current_index]
        if section in placeholder_to_key:
            sfx_key = placeholder_to_key[section]
            sfx_file = audio_files.get(sfx_key, None)
            timing_value = get_timing_value(TIMINGS_ENV.get(sfx_key, "None"))

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
                logging.warning(f"No SFX file for {section}")
                current_index += 1
        else:
            speech_audio_file = generate_speech(section, openai_api_key, tts_voice, tts_quality, output_format)
            final_audio += AudioSegment.from_file(speech_audio_file)
            speech_audio_files.append(speech_audio_file)
            current_index += 1

    final_audio.export(output_file_path, format=output_format)
    logging.info(f"News audio generated and saved to {output_file_path}")

if __name__ == '__main__':
    main()