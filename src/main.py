import os
import re
import feedparser
import openai
import pytz
import logging
import xml.etree.ElementTree as ET
import html
import requests
import json
import mutagen
import time
import hashlib
import acoustid
import traceback
from openai import OpenAI
import mutagen.id3  # Importing mutagen's id3 for SynLyrics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pydub import AudioSegment  # Ensure you have ffmpeg installed
from tempfile import NamedTemporaryFile
from random import choice
from ftplib import FTP
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from croniter import croniter
from io import BytesIO

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
    'FIRST': 'NEWS_READER_AUDIO_FIRST',
    'BED': 'NEWS_READER_AUDIO_BED'
}

TIMINGS_ENV = {
    'INTRO': 'NEWS_READER_TIMING_INTRO',
    'OUTRO': 'NEWS_READER_TIMING_OUTRO',
    'BREAK': 'NEWS_READER_TIMING_BREAK',
    'FIRST': 'NEWS_READER_TIMING_FIRST',
    'BED': 'NEWS_READER_TIMING_BED'
}

GAIN_ENV = {
    'VOICE': 'NEWS_READER_GAIN_VOICE',
    'INTRO': 'NEWS_READER_GAIN_INTRO',
    'OUTRO': 'NEWS_READER_GAIN_OUTRO',
    'BREAK': 'NEWS_READER_GAIN_BREAK',
    'FIRST': 'NEWS_READER_GAIN_FIRST',
    'BED': 'NEWS_READER_GAIN_BED'
}

FADEIN_ENV = {
    'INTRO': 'NEWS_READER_FADEIN_INTRO',
    'OUTRO': 'NEWS_READER_FADEIN_OUTRO',
    'BREAK': 'NEWS_READER_FADEIN_BREAK',
    'FIRST': 'NEWS_READER_FADEIN_FIRST',
    'BED': 'NEWS_READER_FADEIN_BED'
}

FADEOUT_ENV = {
    'INTRO': 'NEWS_READER_FADEOUT_INTRO',
    'OUTRO': 'NEWS_READER_FADEOUT_OUTRO',
    'BREAK': 'NEWS_READER_FADEOUT_BREAK',
    'FIRST': 'NEWS_READER_FADEOUT_FIRST',
    'BED': 'NEWS_READER_FADEOUT_BED'
}

# Lexicon data
LEXICON_JSON_PATH = os.getenv('NEWS_READER_LEXICON_JSON', './lexicon.json')

# Weather Data
WEATHER_JSON_PATH = os.getenv('NEWS_READER_WEATHER_JSON', './weather.json')

# BOM data configuration
BOM_PRODUCT_ID = os.getenv('NEWS_READER_BOM_PRODUCT_ID', 'IDN10064')
STATION_CITY = os.getenv('NEWS_READER_STATION_CITY', 'Sydney')
STATION_COUNTRY = os.getenv('NEWS_READER_STATION_COUNTRY', 'Australia')

# OpenWeather Variable configuration
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
OPENWEATHER_LAT = os.getenv('OPENWEATHER_LAT')
OPENWEATHER_LON = os.getenv('OPENWEATHER_LON')
OPENWEATHER_UNITS = os.getenv('OPENWEATHER_UNITS', 'metric')

DEFAULT_CACHE_DIR = os.getenv('NEWS_READER_DEFAULT_CACHE_DIR', '/tmp')
DEFAULT_CACHE_TTL = os.getenv('NEWS_READER_DEFAULT_CACHE_TTL', 3600)

# RSS Feed configuration
FEED_CONFIG = {
    'TITLE': 'title',
    'DESCRIPTION': 'description',
    'CATEGORY': 'category',
    'PUBLISHED': 'pubDate',
    'IGNORE_PATTERNS': [
        r'SBS News in Easy English \d+ \w+ \d{4}',
        r'News Bulletin \d+ \w+ \d{4}'
    ]
}

def validate_cron(cron_expr):
    """Validate the cron expression."""
    try:
        croniter(cron_expr)
        return True
    except:
        return False

def check_and_create_link_path(source, link_path):
    """Attempt to create a symbolic link, fallback to copying if linking fails.

    Args:
        source (str): The source file path.
        link_path (str): The target symbolic link path.
    
    Returns:
        bool: True if either linking or copying succeeds, False otherwise.
    """
    source = Path(source)
    link_path = Path(link_path)
    directory = link_path.parent

    if not directory.exists():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created directory for link path: {directory}")
        except Exception as e:
            logging.error(f"Failed to create directory for link path '{directory}': {e}")
            logging.error(traceback.format_exc())
            return False

    # Attempt to create a symbolic link
    try:
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(source)
        logging.info(f"Created symbolic link '{link_path}' -> '{source}'")
        return True
    except Exception as e:
        logging.warning(f"Failed to create symbolic link '{link_path}' -> '{source}': {e}")

    # Fallback to copying the file
    try:
        if link_path.exists():
            link_path.unlink()
        import shutil
        shutil.copy2(source, link_path)
        logging.info(f"Copied '{source}' to '{link_path}'")
        return True
    except Exception as e:
        logging.error(f"Failed to copy '{source}' to '{link_path}': {e}")
        logging.error(traceback.format_exc())
        return False
    
def load_lexicon(file_path):
    """Load lexicon dictionary from a JSON file.

    Args:
        file_path (str): Path to the JSON file containing the lexicon.

    Returns:
        dict: Dictionary containing the lexicon for translation/conversion.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading lexicon file '{file_path}': {e}")
        logging.error(traceback.format_exc())
        return {}

def generate_hash(text: str) -> str:
    """Generate SHA-256 hash for the given text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def get_cache_dir() -> Path:
    """Get the cache directory path."""
    cache_dir = os.getenv("NEWS_READER_CACHE_DIR", DEFAULT_CACHE_DIR)
    if cache_dir.lower() == "none":
        return None
    return Path(cache_dir)

def is_cache_enabled() -> bool:
    """Check whether caching is enabled."""
    return get_cache_dir() is not None

def cache_audio(hash_value: str, data: bytes, output_format: str) -> Path:
    """Cache the audio data using the hash value as filename."""
    cache_dir = get_cache_dir()
    if cache_dir is None:
        return None
    
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{hash_value}.{output_format}"
    with open(cache_file, "wb") as file:
        file.write(data)
    return cache_file

def get_cached_audio(hash_value: str, output_format: str) -> AudioSegment:
    """Retrieve cached audio if available.

    Args:
        hash_value (str): The hash value used to store the audio.

    Returns:
        AudioSegment: The cached audio segment if available, otherwise None.
    """
    cache_dir = get_cache_dir()
    if cache_dir is None:
        return None
    
    cache_file = cache_dir / f"{hash_value}.{output_format}"
    if cache_file.exists():
        # Update the access time
        cache_file.touch()
        
        # Load the cached audio file into an AudioSegment
        audio = AudioSegment.from_file(cache_file, format=output_format)
        return audio
    return None

def cleanup_cache():
    """Clean up cache by removing files not used within the TTL period."""
    cache_dir = get_cache_dir()
    if cache_dir is None or not cache_dir.exists():
        return
    
    ttl_seconds = int(os.getenv("NEWS_READER_CACHE_TTL", DEFAULT_CACHE_TTL))
    ttl_delta = timedelta(seconds=ttl_seconds)
    now = datetime.now()

    for cache_file in cache_dir.glob("*.audio"):
        last_access_time = datetime.fromtimestamp(cache_file.stat().st_atime)
        if now - last_access_time > ttl_delta:
            cache_file.unlink()
            logging.info(f"Deleted cached file: {cache_file}")

def apply_lexicon(text, lexicon):
    """Apply lexicon translations to the given text.

    Args:
        text (str): The original text to be converted.
        lexicon (dict): Dictionary containing the lexicon for translation/conversion.

    Returns:
        str: The text after applying lexicon conversions.
    """
    import re

    # Sort and apply case-sensitive direct text to translation mappings (prioritize longer matches)
    direct_sensitive = sorted(lexicon.get("direct_sensitive", {}).items(), key=lambda x: -len(x[0]))
    for original, translation in direct_sensitive:
        text = text.replace(original, translation)

    # Sort and apply case-insensitive direct text to translation mappings (prioritize longer matches)
    direct_insensitive = sorted(lexicon.get("direct_insensitive", {}).items(), key=lambda x: -len(x[0]))
    for original, translation in direct_insensitive:
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        text = pattern.sub(lambda m: translation, text)

    # Apply regex patterns with named groups
    for pattern, translation in lexicon.get("regex", {}).items():
        try:
            text = re.sub(pattern, translation, text)
        except re.error as e:
            logging.error(f"Regex error with pattern '{pattern}': {e}")
            logging.error(traceback.format_exc())

    return text

# Example usage within the existing script
def process_text_for_tts(text):
    """Process text using the lexicon before sending to TTS engine.

    Args:
        text (str): The original text to be processed.
    
    Returns:
        str: The processed text.
    """
    lexicon = load_lexicon(LEXICON_JSON_PATH)
    return apply_lexicon(text, lexicon)

def set_synchronized_lyrics_metadata(audio_path, timestamps, lyrics_text):
    """
    Sets the synchronized lyrics metadata for an audio file using the timestamps and lyrics text.

    Args:
        audio_path (str): Path to the audio file.
        timestamps (list): List of timestamps for each segment in format [MM:SS.ss].
        lyrics_text (str): The lyrics text to sync with the timestamps.
    """
    try:
        # Convert PosixPath to string if necessary
        audio_path = str(audio_path)

        if audio_path.endswith('.mp3'):
            # For MP3 files
            audio = ID3(audio_path)
            sync_lyrics = [f"[{timestamp}]{text}" for timestamp, text in zip(timestamps, lyrics_text)]
            audio.add(USLT(encoding=3, desc="SynchronizedLyricsText", text="\n".join(sync_lyrics)))
            audio.add(USLT(encoding=3, desc="SynchronizedLyricsType", text="2"))
            audio.add(USLT(encoding=3, desc="SynchronizedLyricsDescription", text="Script as read by newsreader"))
            audio.save()
        elif audio_path.endswith('.flac'):
            # For FLAC files, we'll use Vorbis comments
            audio = FLAC(audio_path)
            sync_lyrics = [f"[{timestamp}]{text}" for timestamp, text in zip(timestamps, lyrics_text)]
            audio['SynchronizedLyricsText'] = "\n".join(sync_lyrics)
            audio['SynchronizedLyricsType'] = "2"
            audio['SynchronizedLyricsDescription'] = "Script as read by newsreader"
            audio.save()
        else:
            logging.warning(f"Unsupported file format for synchronized lyrics: {audio_path}")

        logging.info(f"Synchronized lyrics metadata successfully updated for {audio_path}")
    except Exception as e:
        logging.error(f"An error occurred while updating synchronized lyrics metadata: {e}")
        logging.error(traceback.format_exc())

def generate_mixed_audio_and_track_timestamps(sfx_file, speech_audio, timing, start_offset):
    """Generate the mixed audio segment based on the provided timing, tracking timestamps."""
    sfx_audio = AudioSegment.from_file(sfx_file)
    
    logging.info(f"Mixing audio with timing: {timing}")

    if timing.lower() != "none":
        timing_offset = int(timing)
        sfx_duration = len(sfx_audio)
        speech_duration = len(speech_audio)
        if timing_offset > sfx_duration:
            # Add silence after SFX for the timing offset
            padding = timing_offset - sfx_duration
            combined_audio = sfx_audio + AudioSegment.silent(duration=padding) + speech_audio
            speech_start_time = start_offset + sfx_duration + padding
        else:
            # Overlay speech onto SFX at the specified timing offset
            combined_audio = sfx_audio.overlay(speech_audio, position=timing_offset)
            speech_start_time = start_offset + timing_offset
            if timing_offset + speech_duration > sfx_duration:
                # Add remaining speech to the end if extends beyond SFX
                combined_audio = combined_audio + speech_audio[sfx_duration - timing_offset:]
    else:
        logging.info("No overlay timing specified, appending speech to SFX")
        combined_audio = sfx_audio + speech_audio
        speech_start_time = start_offset + len(sfx_audio)

    return combined_audio, speech_start_time / 1000  # Convert to seconds for SynLyrics

def format_timestamp(seconds):
    """Convert float seconds to a timestamp in [MM:SS.ss] format."""
    minutes = int(seconds // 60)
    remainder_seconds = seconds % 60
    return f"{minutes:02d}:{remainder_seconds:05.2f}"

def parse_rss_feed(feed_url, config):
    """Parses the RSS feed, filtering out ignored articles using regex patterns 
    and sorts the articles from most recent to oldest.

    Args:
        feed_url (str): URL of the RSS feed.
        config (dict): Configuration dictionary for field mappings and ignore patterns.

    Returns:
        list: List of dictionaries, each representing a news item, sorted by most recent.
    """
    feed = feedparser.parse(feed_url, agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
    parsed_items = []

    for entry in feed.entries:
        logging.info(f"Processing entry: {entry.title}")
        if any(re.search(pattern, entry.title) for pattern in config['IGNORE_PATTERNS']):
            continue

        categories = [clean_text(cat['term']) for cat in entry.get('tags', [])]
        item = {config_field: clean_text(entry.get(feed_field, ''))
                for config_field, feed_field in config.items()
                if config_field not in ['IGNORE_PATTERNS', 'CATEGORY']}
        item['CATEGORY'] = ', '.join(categories) if categories else 'General'

        # Ensure we correctly parse the published date
        if hasattr(entry, 'published_parsed'):
            published_date = datetime(*entry.published_parsed[:6])
            item['PUBLISHED'] = published_date
        elif 'published' in entry:
            try:
                published_date = datetime.strptime(entry.published, '%a, %d %b %Y %H:%M:%S %Z')
                item['PUBLISHED'] = published_date
            except ValueError:
                item['PUBLISHED'] = None
        else:
            item['PUBLISHED'] = None

        parsed_items.append(item)

    # Sort the parsed items by the published date in descending order
    parsed_items.sort(key=lambda x: x['PUBLISHED'] or datetime.min, reverse=True)

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
        logging.error(traceback.format_exc())
        return None

def fetch_openweather_data(api_key, lat, lon, units, weather_json_path):
    """Fetches weather data from OpenWeatherMap API and caches the result in a JSON file.

    Args:
        api_key (str): The OpenWeatherMap API key.
        lat (str): The latitude of the location for which to fetch weather data.
        lon (str): The longitude of the location for which to fetch weather data.
        units (str): Units of measurement ("standard", "metric", or "imperial").
        weather_json_path (str): Path to the JSON file for storing fetched weather data.

    Returns:
        dict: Weather information as a dictionary if successful, None otherwise.
    """
    if not api_key or not lat or not lon:
        logging.error("OpenWeather API key, latitude, or longitude not set.")
        logging.error(traceback.format_exc())
        return None

    weather_file = Path(weather_json_path)
    current_time = datetime.now(timezone.utc)
    
    if weather_file.exists():
        try:
            with open(weather_json_path, 'r', encoding='utf-8') as file:
                weather_data = json.load(file)
                fetched_time = datetime.strptime(weather_data['dt'], '%Y-%m-%dT%H:%M:%SZ')
                fetched_time = fetched_time.replace(tzinfo=timezone.utc)
                if current_time - fetched_time < timedelta(minutes=15):
                    return weather_data['data']
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.warning(f"Error reading or parsing weather JSON file: {e}. Fetching new data.")
    
    # Fetch new data from OpenWeatherMap API due to stale data or parsing error
    weather_api_url = (
        f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}&units={units}&appid={api_key}"
    )

    try:
        response = requests.get(weather_api_url)
        response.raise_for_status()
        weather_data = response.json()
        
        # Store the current time and weather data to JSON file
        data_to_save = {
            'dt': current_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'data': weather_data
        }
        with open(weather_json_path, 'w', encoding='utf-8') as file:
            json.dump(data_to_save, file)
        
        return weather_data

    except requests.RequestException as e:
        logging.error(f"Failed to fetch weather data from OpenWeatherMap: {e}")
        logging.error(traceback.format_exc())
        return None

def convert_wind_speed(speed, units):
    """Convert wind speed to the appropriate unit."""
    if units == 'metric':
        # Convert m/s to km/h
        return speed * 3.6
    return speed

def wind_direction(deg):
    """Convert wind direction in degrees to compass direction."""
    directions = [
        "North", "North North East", "North East", "East North East", "East", 
        "East South East", "South East", "South South East", "South", 
        "South South West", "South West", "West South West", "West", 
        "West North West", "North West", "North North West"
    ]
    idx = int((deg + 11.25) / 22.5) % 16
    return directions[idx]

def set_audio_metadata(file_path, metadata):
    """
    Sets metadata for an audio file.
    
    Args:
        file_path (str): Path to the audio file.
        metadata (dict): A dictionary of metadata to set.
    """
    try:
        file_path = str(file_path)  # Convert PosixPath to string
        
        if file_path.endswith('.mp3'):
            audio = EasyID3(file_path)
        elif file_path.endswith('.flac'):
            audio = FLAC(file_path)
        elif file_path.endswith('.ogg'):
            audio = mutagen.File(file_path, easy=True)
        else:
            logging.warning(f"File format not supported for metadata: {file_path}")
            return
        
        # Set metadata
        for key, value in metadata.items():
            try:
                audio[key] = value
            except mutagen.MutagenError as e:
                logging.warning(f"Error setting metadata key '{key}': {e}")
        
        # Save changes
        audio.save()
        logging.info(f"Metadata successfully updated for {file_path}")
    except mutagen.MutagenError as e:
        logging.error(f"Error opening file '{file_path}' for metadata update: {e}")
        logging.error(traceback.format_exc())

def format_datetime(dt):
    """Format datetime to a full and human-readable format."""
    # Suffixes for day of the month
    day_suffix = lambda d: 'th' if 10 <= d % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')
    day = dt.day
    suffix = day_suffix(day)
    formatted_datetime = dt.strftime(f'%A the {day}{{suffix}} of %B %Y at %H:%M (%Z)')
    return formatted_datetime.replace("{suffix}", suffix)

def generate_openweather_weather_report(data, units='metric'):
    """Generate a weather report from JSON data."""

    timezone_offset = data['timezone_offset']
    current_weather = data['current']
    minutely_weather = data['minutely']
    daily_weather = data['daily'][0]
    next_day_weather = data['daily'][1]

    # Convert timestamps to readable formats with timezone
    current_time = datetime.fromtimestamp(current_weather['dt'], timezone(timedelta(seconds=timezone_offset)))
    sunrise = datetime.fromtimestamp(current_weather['sunrise'], timezone(timedelta(seconds=timezone_offset)))
    sunset = datetime.fromtimestamp(current_weather['sunset'], timezone(timedelta(seconds=timezone_offset)))

    # Unit labels
    temp_unit = '°C' if units == 'metric' else '°F'
    wind_speed_unit = 'km/h' if units == 'metric' else 'mph'
    
    # Convert wind speed if necessary
    wind_speed = convert_wind_speed(current_weather['wind_speed'], units)
    wind_bearing = wind_direction(current_weather['wind_deg'])
    
    # Current weather report
    current_report = (
        f"Current Weather Update as of {format_datetime(current_time)}:\n"
        f"Temperature: {current_weather['temp']}{temp_unit} (Feels like: {current_weather['feels_like']}{temp_unit})\n"
        f"Humidity: {current_weather['humidity']}%\n"
        f"Condition: {current_weather['weather'][0]['description'].capitalize()}\n"
        f"Wind: {wind_speed:.2f} {wind_speed_unit} from the {wind_bearing}\n"
        f"UV Index: {current_weather['uvi']}\n"
        f"Sunrise at: {format_datetime(sunrise)}, Sunset at: {format_datetime(sunset)}\n"
    )

    # Immediate future weather
    future_rain = [minute['precipitation'] for minute in minutely_weather[:60]]  # Next hour
    future_total_rain = sum(future_rain)
    if future_total_rain > 0:
        immediate_future_report = (
            f"In the immediate future, expect light rain with a total precipitation of "
            f"{future_total_rain:.1f} mm over the next hour."
        )
    else:
        immediate_future_report = "No significant precipitation expected in the immediate future."

    # Convert next day wind speed
    next_day_wind_speed = convert_wind_speed(next_day_weather['wind_speed'], units)
    next_day_wind_bearing = wind_direction(next_day_weather['wind_deg'])

    # Next day weather report
    next_day_report = (
        f"Weather Forecast for Tomorrow ({format_datetime(datetime.fromtimestamp(next_day_weather['dt'], timezone(timedelta(seconds=timezone_offset))))}):\n"
        f"Day Temperature: {next_day_weather['temp']['day']}{temp_unit} (Feels like: {next_day_weather['feels_like']['day']}{temp_unit})\n"
        f"Night Temperature: {next_day_weather['temp']['night']}{temp_unit} (Feels like: {next_day_weather['feels_like']['night']}{temp_unit})\n"
        f"Condition: {next_day_weather['summary']}\n"
        f"Humidity: {next_day_weather['humidity']}%\n"
        f"Wind: {next_day_wind_speed:.2f} {wind_speed_unit} from the {next_day_wind_bearing}\n"
        f"Chance of Rain: {next_day_weather['pop']*100}%"
    )

    # Combine all reports
    full_report = f"{current_report}\n{immediate_future_report}\n\n{next_day_report}"
    
    return full_report

def clean_text(input_string):
    """Remove HTML tags, non-human-readable content, and excess whitespace from the text."""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', html.unescape(input_string))
    cleaned_whitespace = re.sub(r'\s+', ' ', cleantext)
    return cleaned_whitespace.strip()

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

    max_tokens = 8192
    max_completion_tokens = 4095
    prompt_length = len(prompt_instructions.split())
    station_ident = f'Station Name is "{station_name}"\nStation city is "{STATION_CITY}"\nStation country is "{STATION_COUNTRY}"\nNews reader name is "{reader_name}"'
    time_ident = f'Current date and time is "{current_time}"\n'

    combined_prompt = time_ident + station_ident + "\n\n"
    news_content = ""
    news_length = 0
    seen_titles = set()

    for index, item in enumerate(news_items):
        title = item['TITLE']
        # Skip the item if the title has already been seen
        if title in seen_titles:
            continue

        # Include published date if available
        published_date = item.get('PUBLISHED', None)
        if published_date and published_date != 'Unknown':
            published_date = published_date.strftime('%A, %B %d, %Y at %I:%M %p %Z')
            date_line = f"   **Published on:** {published_date}\n"
        else:
            date_line = ""

        new_entry = (
            f"{index + 1}. **Headline:** {title}\n"
            f"   **Category:** {item.get('CATEGORY', 'General')}\n"
            f"{date_line}"
            f"   **Description:** {item['DESCRIPTION']}\n\n"
        )
        new_entry_length = len(new_entry.split())

        if prompt_length + news_length + new_entry_length > max_tokens:
            break

        news_content += new_entry
        news_length += new_entry_length
        seen_titles.add(title)  # Mark the title as seen

    if not news_content:
        logging.info(f"News Content: {news_content}")
        logging.info(f"Prompt length: {prompt_length}, News length: {news_length}")
        raise ValueError(
            f"The combined length of the prompt instructions and news content "
            f"exceeds the maximum token limit for the OpenAI API: {max_tokens} tokens."
        )

    user_prompt = combined_prompt + news_content

    logging.info(f"User prompt: {user_prompt}")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt_instructions},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_completion_tokens
        )
        return response.choices[0].message.content
    except openai.OpenAIError as e:
        raise openai.OpenAIError(f"An error occurred with the OpenAI API: {e}")

def clean_script(script):
    """Cleans the script by removing lines with formatting markers."""
    cleaned_lines = []
    for line in script.splitlines():
        if line.strip() not in ["```plaintext", "```markdown", "```"]:
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
        AudioSegment: The generated audio segment.
    """
    text_hash = generate_hash(news_script_chunk)
    cached_audio = get_cached_audio(text_hash, output_format)
    
    if cached_audio:
        logging.info(f"Using cached audio for hash: {text_hash}")
        return cached_audio
    
    client = OpenAI(api_key=api_key)
    
    processed_text = process_text_for_tts(news_script_chunk)
    logging.info(f"Processed text for TTS: {processed_text}")

    try:
        response = client.audio.speech.create(
            model=quality,
            voice=voice,
            input=processed_text,
            response_format=output_format
        )
        
        # Create a new AudioSegment object from the returned Audio
        audio = AudioSegment.from_file(BytesIO(response.content), format=output_format)

        normalized_audio = audio.apply_gain(-audio.max_dBFS)  # Normalize to 0 dBFS
        cache_audio(text_hash, normalized_audio.export(format=output_format).read(), output_format)
        
        return normalized_audio
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

def generate_audio_fingerprint_from_object(output_file_path):
    """Generate an audio fingerprint from an audio object using Chromaprint and AcoustID.
    
    Args:
        output_file_path (str): The path to the audio file.
    
    Returns:
        tuple: (duration, fingerprint string, bitrate, file_format)
        
    Raises:
        RuntimeError: If the fingerprinting process fails.
    """
    try:        
        # Generate fingerprint and duration
        duration, fingerprint = acoustid.fingerprint_file(output_file_path)
        
        # Use mutagen to extract metadata (bitrate)
        audio_file = mutagen.File(output_file_path)
        if audio_file is None:
            raise RuntimeError('Unsupported file format')

        bitrate = getattr(audio_file.info, 'bitrate', None) // 1000 if getattr(audio_file.info, 'bitrate', None) else None

        return duration, fingerprint, bitrate
    except Exception as e:
        raise RuntimeError(f"Failed to generate fingerprint: {e}")

def submit_to_musicbrainz(output_file_path, output_format, metadata, user_key, application_key):
    """Submit the audio fingerprint along with metadata to MusicBrainz.
    
    Args:
        output_file_path (str): The audio file path.
        output_format (str): The format of the audio file.
        metadata (dict): Metadata dictionary including artist, title, etc.
        user_key (str): Your AcoustID user API key.
        application_key (str): Your AcoustID application API key
    
    Returns:
        dict: JSON response from MusicBrainz.
        
    Raises:
        RuntimeError: If the submission process fails.
    """
    # Generate fingerprint and retrieve accurate bitrate and file format
    try:
        duration, fingerprint, bitrate = generate_audio_fingerprint_from_object(output_file_path)
    except Exception as e:
        raise RuntimeError(f"Failed to generate fingerprint: {e}")
    
    logging.info(f"Duration: {duration}, Bitrate: {bitrate} kbps")

    # Mapping existing metadata to AcoustID valid metadata
    data = {
        'client': application_key,  # Your application API key
        'user': user_key,
        'duration.0': int(duration),  # Ensure duration is an integer
        'fingerprint.0': fingerprint.decode('utf-8') if isinstance(fingerprint, bytes) else fingerprint,
        'track.0': metadata.get('title'),
        'artist.0': metadata.get('artist'),
        'album.0': metadata.get('album'),
        'albumartist.0': metadata.get('artist'),  # Assuming the artist as the album artist
        'year.0': metadata.get('year'),
        'trackno.0': metadata.get('tracknumber'),
        'discno.0': metadata.get('discnumber'),
        'bitrate.0': str(bitrate),
        'fileformat.0': output_format,
        'format': 'json'
    }

    # Remove None values from data
    data = {k: v for k, v in data.items() if v is not None}

    try:
        response = requests.get('https://api.acoustid.org/v2/submit', params=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        # Pretty print the submission payload for debugging
        logging.error(f"Failed to submit to MusicBrainz: {e}")
        logging.error(f"Response: {response.text}")
        logging.error(f"data: {data}")
        # If response has a json encoded error message, raise that
        try:
            error_message = response.json().get('error', {}).get('message')
            if error_message:
                raise RuntimeError(error_message)
        except ValueError:
            raise RuntimeError(response.text)

def generate_news_audio():
    """Function to handle the news generation and audio output."""
    feed_url = os.getenv('NEWS_READER_RSS', 'https://raw.githubusercontent.com/troykelly/live-news-break/main/demo.xml')
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
        logging.error(traceback.format_exc())
        return

    timezone_str = os.getenv('NEWS_READER_TIMEZONE', 'UTC')
    try:
        timezone = pytz.timezone(timezone_str)
    except Exception as e:
        logging.error(f"Invalid timezone '{timezone_str}', defaulting to UTC")
        logging.error(traceback.format_exc())
        timezone = pytz.UTC

    # Handle timeshift
    timeshift_millis = int(os.getenv('NEWS_READER_TIMESHIFT', '0'))
    timeshift_delta = timedelta(milliseconds=timeshift_millis)

    current_time = datetime.now(timezone) + timeshift_delta

    news_items = parse_rss_feed(feed_url, FEED_CONFIG)

    if not news_items:
        logging.warning("No news items found in the feed.")
        return

    weather_info = None

    openweather_api_key = os.getenv('OPENWEATHER_API_KEY')
    openweather_lat = os.getenv('OPENWEATHER_LAT')
    openweather_lon = os.getenv('OPENWEATHER_LON')
    openweather_units = os.getenv('OPENWEATHER_UNITS', 'metric')  # default to metric if not set

    if openweather_api_key and openweather_lat and openweather_lon:
        weather_data = fetch_openweather_data(openweather_api_key, openweather_lat, openweather_lon, openweather_units, WEATHER_JSON_PATH)
        if weather_data:
            weather_info = generate_openweather_weather_report(weather_data, openweather_units)
    else:
        bom_product_id = os.getenv('BOM_PRODUCT_ID')
        if bom_product_id:
            weather_info = fetch_bom_data(bom_product_id)

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
    # speech_audio_files = []
    current_index = 0
    placeholder_to_key = {
        INTRO_PLACEHOLDER: "INTRO",
        ARTICLE_START_PLACEHOLDER: "FIRST",
        ARTICLE_BREAK_PLACEHOLDER: "BREAK",
        OUTRO_PLACEHOLDER: "OUTRO"
    }

    total_elapsed_time = 0  # Track cumulative time for timestamps
    timestamps = []
    lyrics_text = []

    article_start_time = None
    article_end_time = None

    while current_index < len(script_sections):
        section = script_sections[current_index]
        if section in placeholder_to_key:
            sfx_key = placeholder_to_key[section]
            sfx_file = audio_files.get(sfx_key, None)
            timing_value = get_timing_value(TIMINGS_ENV.get(sfx_key, "None"))

            if sfx_file:
                if current_index + 1 < len(script_sections):
                    speech_text = script_sections[current_index + 1]
                    speech_audio = generate_speech(speech_text, openai_api_key, tts_voice, tts_quality, output_format)
                    mixed_audio, speech_start_time = generate_mixed_audio_and_track_timestamps(sfx_file, speech_audio, timing_value, total_elapsed_time * 1000)
                                        
                    final_audio += mixed_audio
                    current_index += 2
                    
                    if sfx_key == "OUTRO" and article_end_time is None:
                        article_end_time = total_elapsed_time * 1000
                        logging.info(f"Music bed to end at {article_end_time}.")
                        
                    if sfx_key == "FIRST" and article_start_time is None:
                        timing_offset = 0
                        if timing_value.lower() != "none":
                            timing_offset = int(timing_value)
                        article_start_time = (total_elapsed_time * 1000) + timing_offset
                        logging.info(f"Music bed to start at {article_start_time}.")

                    timestamps.append(format_timestamp(speech_start_time))
                    lyrics_text.append(speech_text)
                    total_elapsed_time += len(mixed_audio) / 1000  # Update elapsed time (in seconds)
                else:
                    raise ValueError("SFX placeholder found at the end without subsequent text.")
            else:
                logging.warning(f"No SFX file for {section}")
                current_index += 1                
        else:
            speech_audio = generate_speech(section, openai_api_key, tts_voice, tts_quality, output_format)
                        
            final_audio += speech_audio
            current_index += 1
            
            if article_start_time is None:
                article_start_time = total_elapsed_time * 1000

            total_elapsed_time += len(speech_audio) / 1000  # Update elapsed time (in seconds)
            timestamps.append(format_timestamp(total_elapsed_time))
            lyrics_text.append(section)
            
    # Post-process to add music bed
    bed_file = audio_files.get("BED", None)
    if bed_file and article_start_time is not None and article_end_time is not None:
        bed_audio = AudioSegment.from_file(bed_file)
        # Ensure fade values are converted to integers and have default fallback values if not set
        bed_gain = float(os.getenv(GAIN_ENV["BED"], -15))
        bed_fadein = int(os.getenv(FADEIN_ENV["BED"], 0) or 0)
        bed_fadeout = int(os.getenv(FADEOUT_ENV["BED"], 500) or 500)
        bed_offset = int(os.getenv(TIMINGS_ENV["BED"], 0) or 0)

        # Adjust the start time of the bed audio in case of a negative offset
        adjusted_article_start_time = max(0, article_start_time + bed_offset)
        if article_start_time is not None and article_end_time is not None:
            bed_duration = article_end_time - article_start_time
            looped_bed_audio = AudioSegment.empty()

            while len(looped_bed_audio) < bed_duration:
                looped_bed_audio += bed_audio

            looped_bed_audio = looped_bed_audio[:bed_duration]
            looped_bed_audio = looped_bed_audio.apply_gain(bed_gain)

            if bed_fadein > 0:
                looped_bed_audio = looped_bed_audio.fade_in(bed_fadein)
            if bed_fadeout > 0:
                looped_bed_audio = looped_bed_audio.fade_out(bed_fadeout)
            # Overlay the bed audio starting from the adjusted article start time
            combined_audio = final_audio.overlay(looped_bed_audio, position=adjusted_article_start_time)
            final_audio = combined_audio            

    final_audio.export(output_file_path, format=output_format)

    # Human readable date for metadata
    metadata_human_date = current_time.strftime('%A, %B %d, %Y at %I:%M %p %Z')
    
    # The release time of the news read (time plus time shift if it's set) as YYYY-MM-DDThh:mm:ssZ
    metadata_release_time = (current_time + timeshift_delta).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Set metadata for the generated audio file
    metadata = {
        'title': f"{station_name} News Broadcast for {metadata_human_date}",
        'subtitle': f"Read by {reader_name}",
        'artist': f"{reader_name}",
        'album': 'News Bulletin',
        'date': datetime.now().strftime('%Y-%m-%d'),
        'releasetime': metadata_release_time,
        'genre': 'News',
        'comment': news_script,
        'discnumber': '1',
        'tracknumber': '1',
        'language': 'en',
        'publisher': f"{station_name} News",
        'year': datetime.now().strftime('%Y'),
        'encodedby': 'https://github.com/troykelly/live-news-break',
        'source': f"RSS: {feed_url}",
        'copyright': f"Copyright © {station_name} {datetime.now().strftime('%Y')}",
        'publisherurl': 'https://github.com/troykelly/live-news-break',
    }
    set_audio_metadata(output_file_path, metadata)
    set_synchronized_lyrics_metadata(output_file_path, timestamps, lyrics_text)  # Set SynLyrics metadata
    logging.info(f"News audio generated and saved to {output_file_path}")

    # Handle the NEWS_READER_OUTPUT_LINK environment variable
    output_link = os.getenv('NEWS_READER_OUTPUT_LINK', '').strip()

    if output_link:
        if check_and_create_link_path(output_file_path, output_link):
            logging.info(f"Successfully created link or copied file to '{output_link}'")
        else:
            logging.error(f"Failed to create link or copy file to '{output_link}'")
            logging.error(traceback.format_exc())

    # Check for AcoustID user and application keys
    acoustid_user_key = os.getenv('ACOUSTID_USER_KEY', '').strip()
    acoustid_application_key = os.getenv('ACOUSTID_APPLICATION_KEY', '').strip()

    if acoustid_user_key and acoustid_application_key:
        try:
            # Call the submit_to_musicbrainz function
            response = submit_to_musicbrainz(output_file_path, output_format, metadata, acoustid_user_key, acoustid_application_key)
            logging.info(f"Successfully submitted to MusicBrainz: {response}")
        except Exception as e:
            logging.error(f"Failed to submit to MusicBrainz: {e}")
            logging.error(traceback.format_exc())
    else:
        logging.warning("AcoustID user key or application key is not defined. Skipping submission.")

def main():
    """Main function that fetches, parses, and processes the RSS feed into audio."""
    cron_exp = os.getenv('NEWS_READER_CRON', '').strip()

    if cron_exp:
        if not validate_cron(cron_exp):
            logging.error(f"Invalid cron expression '{cron_exp}' in 'NEWS_READER_CRON' environment variable.")
            logging.error(traceback.format_exc())
            return

        while True:
            try:
                iterator = croniter(cron_exp, datetime.now())
                next_run = iterator.get_next(datetime)
                current_time = datetime.now()
                sleep_duration = (next_run - current_time).total_seconds()

                logging.info(f"Scheduled next run at: {next_run} (sleeping for {sleep_duration} seconds)")
                time.sleep(sleep_duration)

                generate_news_audio()
            except Exception as e:
                logging.error(f"An error occurred during scheduled news generation: {e}")
                logging.error(traceback.format_exc())

    else:
        try:
            generate_news_audio()
        except Exception as e:
            logging.error(f"An error occurred during news generation: {e}")
            logging.error(traceback.format_exc())

if __name__ == '__main__':
    main()
