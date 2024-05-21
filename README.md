# live-news-break

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

To test with docker:

```bash
docker run --rm -e OPENAI_API_KEY=SETKEYHERE -e NEWS_READER_OUTPUT_DIR=/mnt/audio -v "${PWD}:/mnt/audio" ghcr.io/troykelly/live-news-break:edge
```

Make sure to set your correct OPENAI_API_KEY

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

Here's an example configuration:

```dotenv
OPENAI_API_KEY=sk-proj-KEYKEYKEY
OPENWEATHER_API_KEY=KEYKEYKEY
NEWS_READER_STATION_NAME='News Update Radio'
NEWS_READER_READER_NAME='OpenAI Shimmer'
NEWS_READER_STATION_CITY=Sydney
NEWS_READER_STATION_COUNTRY=Australia
NEWS_READER_TTS_VOICE=shimmer
NEWS_READER_TTS_QUALITY=tts-1-hd
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
OPENWEATHER_LAT=-33.8688
OPENWEATHER_LON=151.2093
```

Ensure to replace placeholder values, especially the `OPENAI_API_KEY` and `OPENWEATHER_API_KEY`, with your actual API keys.

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