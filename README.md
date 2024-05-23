# AI Live News Reader for Radio Stations

The `live-news-break` repository contains a news generation script that fetches, processes, and converts news articles into an audio news broadcast. This guide will help you understand how to set up, configure, and run the news generation process using the script provided.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running the Script](#running-the-script)
- [Script Overview](#script-overview)
- [Contributing](#contributing)
- [License](#license)

## Demo

Listen to the demo here: [https://audio.com/troy-8/audio/troykelly-live-news-break-demo-reel-1](https://audio.com/troy-8/audio/troykelly-live-news-break-demo-reel-1)

## Test

To test with docker, see the example command below.

This will create a completely dry read, as we can't distribute the audio files with the package - you will have to create or find your own.

```bash
docker run --rm -e OPENAI_API_KEY=SETKEYHERE -e NEWS_READER_OUTPUT_DIR=/mnt/audio -v "${PWD}:/mnt/audio" ghcr.io/troykelly/live-news-break:edge
```
*Make sure to set your correct OPENAI_API_KEY*

## Prerequisites

Ensure you have the following software installed on your system:

- Python 3.8+
- `ffmpeg` (required for `pydub` to process audio)
- Required Python packages (see `requirements.txt`)

## Setup

Clone the repository:

```bash
git clone https://github.com/troykelly/live-news-break.git
cd live-news-break
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## Configuration

You will need to set several environment variables for the script to work correctly. You can set these variables in a `.env` file at the root of the repository for convenience.

Here's an example configuration, see the docker compose file for an exhaustive list.

```dotenv
OPENAI_API_KEY=sk-proj-KEYKEYKEY
ELEVENLABS_API_KEY=KEYKEYKEY
NEWS_READER_STATION_NAME=News Update Radio
NEWS_READER_READER_NAME=OpenAI Shimmer
NEWS_READER_STATION_CITY=Sydney
NEWS_READER_STATION_COUNTRY=Australia
NEWS_READER_TTS_VOICE=shimmer
NEWS_READER_TTS_MODEL=tts-1-hd
NEWS_READER_TTS_PROVIDER=elevenlabs
NEWS_READER_AUDIO_INTRO=audio/intro.wav
NEWS_READER_AUDIO_OUTRO=audio/outro.wav
NEWS_READER_AUDIO_FIRST=audio/first.wav
NEWS_READER_AUDIO_BREAK=audio/break.wav
NEWS_READER_AUDIO_BED=audio/bed.wav
NEWS_READER_TIMEZONE=Australia/Sydney
NEWS_READER_TIMING_INTRO=16500
NEWS_READER_TIMING_OUTRO=8500
NEWS_READER_TIMING_BREAK=1600
NEWS_READER_TIMING_FIRST=3300
NEWS_READER_TIMING_BED=-500
NEWS_READER_GAIN_BED=-15
NEWS_READER_FADEIN_BED=0
NEWS_READER_FADEOUT_BED=500
NEWS_READER_BOM_PRODUCT_ID=IDN10064
OPENWEATHER_API_KEY=KEYKEYKEY
OPENWEATHER_LAT=-33.8688
OPENWEATHER_LON=151.2093
```

Ensure to replace placeholder values, especially the `OPENAI_API_KEY` and `ELEVENLABS_API_KEY` with your actual API keys.

## Environment Variables Explainer

This section provides an overview and explanation of the environment variables used in the News Reader application.

### General Configuration

- **`OPENAI_API_KEY`**: API key for OpenAI, used for generating news scripts via the GPT model.
  - **Example:** `sk-abc123`
  
- **`ELEVENLABS_API_KEY`**: API key for ElevenLabs, used for TTS voice generation.
  - **Example:** `abc123`

- **`NEWS_READER_CRON`**: Cron expression to schedule the news generation. If not set, the script runs once.
  - **Example:** `13,28,43,58 * * * *`

- **`NEWS_READER_RSS`**: URL of the RSS feed to parse.
  - **Default:** `https://raw.githubusercontent.com/troykelly/live-news-break/main/demo.xml`
  - **Example:** `https://example.com/rss-feed`

- **`NEWS_READER_OUTPUT_DIR`**: Directory where the generated audio files are saved.
  - **Default:** `.`
  - **Example:** `/output`

- **`NEWS_READER_OUTPUT_FILE`**: File name template for the output audio file. Supports placeholders: `%Y%`, `%m%`, `%d%`, `%H%`, `%M%`, `%S%`, `%EXT%`.
  - **Default:** `livenews.%EXT%`
  - **Example:** `news_%Y%_%m%_%d%_%H%_%M%_%S%.mp3`

- **`NEWS_READER_OUTPUT_LINK`**: Path to create a symbolic link pointing to the latest output file. If not set, no symbolic link is created.
  - **Example:** `/path/to/latest_news.mp3`

### Station Configuration

- **`NEWS_READER_STATION_NAME`**: Name of the radio station.
  - **Default:** `Live News 24`
  - **Example:** `News Update Radio`

- **`NEWS_READER_READER_NAME`**: Name of the news reader.
  - **Default:** `Burnie Housedown`
  - **Example:** `OpenAI Shimmer`

- **`NEWS_READER_STATION_CITY`**: City where the station is located.
  - **Default:** `Sydney`
  - **Example:** `Melbourne`

- **`NEWS_READER_STATION_COUNTRY`**: Country where the station is located.
  - **Default:** `Australia`
  - **Example:** `United States`

### Audio Configuration

- **`NEWS_READER_TTS_VOICE`**: Voice to be used by the text-to-speech service.
  - **Default:** `alloy`
  - **Example:** `shimmer`

- **`NEWS_READER_TTS_MODEL`**: Model settings for the TTS.
  - **Default:** `tts-1`
  - **Example:** `tts-1-hd`

- **`NEWS_READER_TTS_PROVIDER`**: TTS provider to use.
  - **Default:** `openai`
  - **Example:** `elevenlabs`

- **`NEWS_READER_OUTPUT_FORMAT`**: Format for the output audio file.
  - **Default:** `flac`
  - **Example:** `mp3`

### Audio Files

- **`NEWS_READER_AUDIO_INTRO`**: Path to the introduction audio file.
  - **Example:** `audio/intro.wav`
- **`NEWS_READER_AUDIO_OUTRO`**: Path to the outro audio file.
  - **Example:** `audio/outro.wav`
- **`NEWS_READER_AUDIO_FIRST`**: Path to the first news article audio file.
  - **Example:** `audio/first.wav`
- **`NEWS_READER_AUDIO_BREAK`**: Path to the break between articles audio file.
  - **Example:** `audio/break.wav`
- **`NEWS_READER_AUDIO_BED`**: Path to the bed music file.
  - **Example:** `audio/bed.wav`

### Timing Configuration

- **`NEWS_READER_TIMING_INTRO`**: Timing offset for introduction.
  - **Example:** `16500`
- **`NEWS_READER_TIMING_OUTRO`**: Timing offset for outro.
  - **Example:** `8500`
- **`NEWS_READER_TIMING_BREAK`**: Timing offset for break.
  - **Example:** `1600`
- **`NEWS_READER_TIMING_FIRST`**: Timing offset for the first article.
  - **Example:** `3300`
- **`NEWS_READER_TIMING_BED`**: Timing offset for bed music.
  - **Example:** `-500`

### Gain Configuration

- **`NEWS_READER_GAIN_VOICE`**: Gain for voice audio.
  - **Example:** `-3`
- **`NEWS_READER_GAIN_INTRO`**: Gain for introduction audio.
  - **Example:** `-6`
- **`NEWS_READER_GAIN_OUTRO`**: Gain for outro audio.
  - **Example:** `-6`
- **`NEWS_READER_GAIN_BREAK`**: Gain for break audio.
  - **Example:** `-6`
- **`NEWS_READER_GAIN_FIRST`**: Gain for the first article audio.
  - **Example:** `-6`
- **`NEWS_READER_GAIN_BED`**: Gain for bed music audio.
  - **Example:** `-15`

### Fade Configuration

- **`NEWS_READER_FADEIN_INTRO`**: Fade-in duration for introduction.
  - **Example:** `1000`
- **`NEWS_READER_FADEIN_OUTRO`**: Fade-in duration for outro.
  - **Example:** `1000`
- **`NEWS_READER_FADEIN_BREAK`**: Fade-in duration for break.
  - **Example:** `1000`
- **`NEWS_READER_FADEIN_FIRST`**: Fade-in duration for the first article.
  - **Example:** `1000`
- **`NEWS_READER_FADEIN_BED`**: Fade-in duration for bed music.
  - **Example:** `0`
- **`NEWS_READER_FADEOUT_INTRO`**: Fade-out duration for introduction.
  - **Example:** `1000`
- **`NEWS_READER_FADEOUT_OUTRO`**: Fade-out duration for outro.
  - **Example:** `1000`
- **`NEWS_READER_FADEOUT_BREAK`**: Fade-out duration for break.
  - **Example:** `1000`
- **`NEWS_READER_FADEOUT_FIRST`**: Fade-out duration for the first article.
  - **Example:** `1000`
- **`NEWS_READER_FADEOUT_BED`**: Fade-out duration for bed music.
  - **Example:** `500`

### Lexicon Configuration

- **`NEWS_READER_LEXICON_JSON`**: Path to the lexicon JSON file for text conversion.
  - **Default:** `./lexicon.json`
  - **Example:** `/path/to/lexicon.json`

### Weather Data Configuration

- **`NEWS_READER_WEATHER_JSON`**: Path to the weather data JSON file.
  - **Default:** `./weather.json`
  - **Example:** `/path/to/weather.json`

### Bureau of Meteorology (BOM) Configuration

- **`NEWS_READER_BOM_PRODUCT_ID`**: BOM product ID for weather data.
  - **Default:** `IDN10064`
  - **Example:** `IDN10064`

### OpenWeather Configuration

- **`OPENWEATHER_API_KEY`**: API key for OpenWeatherMap.
  - **Example:** `abc123`
- **`OPENWEATHER_LAT`**: Latitude for the weather location.
  - **Example:** `-33.8688`
- **`OPENWEATHER_LON`**: Longitude for the weather location.
  - **Example:** `151.2093`
- **`OPENWEATHER_UNITS`**: Units for weather data (standard, metric, imperial).
  - **Default:** `metric`
  - **Example:** `metric`

### Example Environment Configuration

Here's an example environment configuration you can use in your Docker Compose file or `.env` file:

```dotenv
OPENAI_API_KEY=sk-abc123
ELEVENLABS_API_KEY=elevenlabs-abc123
NEWS_READER_CRON=13,28,43,58 * * * *
NEWS_READER_RSS=https://example.com/rss-feed
NEWS_READER_OUTPUT_DIR=/output
NEWS_READER_OUTPUT_FILE=news_%Y%_%m%_%d%_%H%_%M%_%S%.mp3
NEWS_READER_OUTPUT_LINK=/path/to/latest_news.mp3
NEWS_READER_STATION_NAME=News Update Radio
NEWS_READER_READER_NAME=OpenAI Shimmer
NEWS_READER_STATION_CITY=Sydney
NEWS_READER_STATION_COUNTRY=Australia
NEWS_READER_TTS_VOICE=Stuart - Energetic and enthusiastic
NEWS_READER_TTS_MODEL=eleven_turbo_v2
NEWS_READER_TTS_PROVIDER=elevenlabs
NEWS_READER_OUTPUT_FORMAT=mp3
NEWS_READER_AUDIO_INTRO=audio/intro.wav
NEWS_READER_AUDIO_OUTRO=audio/outro.wav
NEWS_READER_AUDIO_FIRST=audio/first.wav
NEWS_READER_AUDIO_BREAK=audio/break.wav
NEWS_READER_AUDIO_BED=audio/bed.wav
NEWS_READER_TIMING_INTRO=16500
NEWS_READER_TIMING_OUTRO=8500
NEWS_READER_TIMING_BREAK=1600
NEWS_READER_TIMING_FIRST=3300
NEWS_READER_TIMING_BED=-500
NEWS_READER_GAIN_VOICE=-3
NEWS_READER_GAIN_INTRO=-6
NEWS_READER_GAIN_OUTRO=-6
NEWS_READER_GAIN_BREAK=-6
NEWS_READER_GAIN_FIRST=-6
NEWS_READER_GAIN_BED=-15
NEWS_READER_FADEIN_INTRO=1000
NEWS_READER_FADEOUT_INTRO=1000
NEWS_READER_FADEIN_OUTRO=1000
NEWS_READER_FADEOUT_OUTRO=1000
NEWS_READER_FADEIN_BREAK=1000
NEWS_READER_FADEOUT_BREAK=1000
NEWS_READER_FADEIN_FIRST=1000
NEWS_READER_FADEOUT_FIRST=1000
NEWS_READER_FADEIN_BED=0
NEWS_READER_FADEOUT_BED=500
NEWS_READER_LEXICON_JSON=/path/to/lexicon.json
NEWS_READER_WEATHER_JSON=/path/to/weather.json
NEWS_READER_BOM_PRODUCT_ID=IDN10064
OPENWEATHER_API_KEY=abc123
OPENWEATHER_LAT=-33.8688
OPENWEATHER_LON=151.2093
OPENWEATHER_UNITS=metric
NEWS_READER_TIMEZONE=Australia/Sydney
```

## Running the Script

After configuring your environment variables, you can run the script using:

```bash
python src/main.py
```

The script will fetch news articles, generate a news script, convert the script into audio, and save the output audio file based on your configuration.

## Script Overview

### Main Functions

- **parse_rss_feed**: Fetches and processes RSS feed data.
- **fetch_bom_data**: Retrieves weather data from the Bureau of Meteorology.
- **fetch_openweather_data**: Retrieves weather data from the OpenWeatherMap API.
- **generate_news_script**: Uses the OpenAI API to generate a news script from fetched news items.
- **generate_speech**: Converts script text into speech using the OpenAI TTS API.
- **concatenate_audio_files**: Combines multiple audio files into one final output.
- **check_audio_files**: Ensures all necessary audio files are available.
- **generate_mixed_audio**: Mixes SFX audio with speech audio based on timing settings.

### Environment Variables

The script uses various environment variables for configuration. These include API keys, file paths for audio clips, text-to-speech settings, and more. Refer to the example environment configuration above.

### Logging

The script includes logging statements to help you monitor the process and diagnose issues. Logs will be output to the console.

## Contributing

Contributions to this project are welcome. If you identify any bugs or have suggestions for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.