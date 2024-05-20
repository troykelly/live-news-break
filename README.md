
# Live News Break Generator

## Overview

The Live News Break Generator is a tool designed to fetch news articles from an RSS feed, integrate weather data from the Bureau of Meteorology (BOM), generate a news script, and produce audio news segments using text-to-speech (TTS) technology. This tool can be used by radio stations, podcasts, or any service requiring automated news updates.

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [License](#license)

## Features

- Fetch news articles from any specified RSS feed.
- Integrate live weather data from the BOM.
- Generate coherent and engaging news scripts formatted for radio broadcasting.
- Convert news scripts into audio files with TTS.
- Concatenate custom sound effects (intros, breaks, outros) with the generated speech.

## Prerequisites

Before you begin, ensure you have met the following requirements:

- Python 3.8 or higher installed on your machine.
- `ffmpeg` installed on your machine for audio processing.
- Access to the OpenAI API for GPT-4 and TTS services.
- An FTP client installed for fetching weather data from the BOM.

## Installation

1. Clone the repository from GitHub.

    ```bash
    git clone https://github.com/yourusername/live-news-break.git
    cd live-news-break
    ```

2. Install the required Python packages.

    ```bash
    pip install -r requirements.txt
    ```

3. Ensure `ffmpeg` is installed and accessible in your system's PATH.

## Configuration

The script uses environmental variables for its configuration. Create a `.env` file in the root of your project with the following variables:

```env
# OpenAI API Key
OPENAI_API_KEY=your_openai_api_key

# RSS Feed URL
NEWS_READER_RSS=https://www.sbs.com.au/news/topic/latest/feed

# Station Information
NEWS_READER_STATION_NAME=Live News 24
NEWS_READER_READER_NAME=Burnie Housedown
NEWS_READER_STATION_CITY=Sydney
NEWS_READER_STATION_COUNTRY=Australia

# TTS Configuration
NEWS_READER_TTS_VOICE=alloy
NEWS_READER_TTS_QUALITY=tts-1
NEWS_READER_OUTPUT_FORMAT=flac

# BOM Product ID
NEWS_READER_BOM_PRODUCT_ID=IDN10064

# Timing Configuration
NEWS_READER_TIMING_INTRO=0
NEWS_READER_TIMING_OUTRO=0
NEWS_READER_TIMING_BREAK=0
NEWS_READER_TIMING_FIRST=0

# Sound Effects Files
NEWS_READER_AUDIO_INTRO=path/to/intro_sound.mp3
NEWS_READER_AUDIO_OUTRO=path/to/outro_sound.mp3
NEWS_READER_AUDIO_BREAK=path/to/break_sound.mp3
NEWS_READER_AUDIO_FIRST=path/to/first_sound.mp3

# Prompt file
NEWS_READER_PROMPT_FILE=./prompt.md

# Output directory for the final audio file
NEWS_READER_OUTPUT_DIR=./output
```

## Usage

The main script `main.py` fetches news, generates a script, and produces an audio file. Run the following command to execute the script:

```bash
python src/main.py
```

This script will:

1. Fetch news articles from the configured RSS feed.
2. Fetch weather data from the BOM.
3. Generate a news script using OpenAI GPT-4.
4. Convert the script into an audio file using TTS.
5. Merge custom sound effects with the generated audio.
6. Save the final audio file to the specified output directory.

## Development

### Project Structure

```plaintext
live-news-break/
│
├── .env                   # Environment variables file
├── src/
│   ├── main.py            # Main script file
│   ├── utils.py           # Utility functions (if applicable)
│   └── ...
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
├── prompt.md              # Instructions for GPT-4 prompt
└── output/                # Directory for output audio files
```

### Adding New Features

1. Fork the repository.
2. Create a new feature branch.
3. Implement and test your changes.
4. Push your changes and create a pull request.

## License

This project is licensed under the Apache License. See the [LICENSE](LICENSE) file for details.