# src/replaygain/main.py

import logging
import json
from io import BytesIO
from typing import Tuple, Optional
from mutagen import File as MutagenFile
from subprocess import Popen, PIPE, CalledProcessError
from math import isnan

from logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

def calculate_replaygain(file_like: BytesIO, file_format: str) -> Tuple[float, float, dict]:
    """Calculate ReplayGain values for an audio file using ffmpeg with loudnorm filter.

    Args:
        file_like: A file-like object representing the audio content.
        file_format: The format of the audio file (e.g., 'mp3', 'flac', 'opus').

    Returns:
        A tuple containing the gain (in dB), peak values, and the full parsed JSON data.

    Raises:
        RuntimeError: If ReplayGain calculation fails or could not be parsed.
    """
    command = [
        'ffmpeg',
        '-hide_banner',
        '-i', 'pipe:0',
        '-af', 'loudnorm=I=-23:LRA=7:TP=-2:print_format=json',
        '-f', 'null', '-'
    ]

    with Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE) as process:
        out, err = process.communicate(input=file_like.getvalue())

    if process.returncode != 0:
        logger.error(f"ffmpeg command failed with error {process.returncode}: {err.decode('utf-8')}")
        raise CalledProcessError(process.returncode, command, output=out, stderr=err)

    json_output, json_lines = '', False
    for line in err.decode('utf-8').splitlines():
        line = line.strip()
        if line == "{":
            json_output += line
            json_lines = True
        elif json_lines:
            json_output += line
            if line == "}":
                json_lines = False

    if not json_output:
        logger.error("No valid JSON output found from ffmpeg.")
        raise RuntimeError("Failed to parse ReplayGain data from ffmpeg output.")

    parsed_data = json.loads(json_output)

    gain = float(parsed_data.get('input_i', 'nan'))
    peak = float(parsed_data.get('input_tp', 'nan'))

    if isnan(gain) or isnan(peak):
        logger.error(f"Invalid gain or peak values found: gain={gain}, peak={peak}")
        raise RuntimeError("ReplayGain calculation failed or could not be parsed.")

    return gain, peak, parsed_data

def ffmpeg_process(input_bytes, cmd):
    # Start the FFmpeg process
    proc = Popen(
        cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE
    )
    # Pass the input data and get the output
    output, error = proc.communicate(input=input_bytes)
    if proc.returncode != 0:
        raise Exception("FFmpeg error: " + error.decode('utf-8'))
    return BytesIO(output)

def apply_replaygain(
    file_like: BytesIO,
    gain: float,
    peak: float,
    file_format: str,
    r128_track_gain: Optional[int] = None,
    r128_album_gain: Optional[int] = None,
    loudness_metadata: Optional[dict] = None,
) -> bytes:
    """Apply ReplayGain and additional loudness metadata to an audio file using FFmpeg and return as BytesIO.

    Args:
        file_like (BytesIO): The audio file data.
        gain (float): ReplayGain track gain to set (in dB).
        peak (float): ReplayGain track peak to set.
        file_format (str): Format of the audio file ('mp3', 'flac', 'opus', etc.).
        r128_track_gain (Optional[int]): Optional R128 track gain.
        r128_album_gain (Optional[int]): Optional R128 album gain.
        loudness_metadata (Optional[dict]): Additional loudness metadata to be embedded.

    Returns:
        BytesIO: The modified audio file data as a BytesIO object.

    Raises:
        Exception: If FFmpeg processing fails.
    """
    logger.debug("Starting to apply ReplayGain and other loudness metadata...")

    metadata_cmd = [
        '-metadata', f'replaygain_track_gain={gain} dB',
        '-metadata', f'replaygain_track_peak={peak}'
    ]

    if r128_track_gain is not None:
        metadata_cmd.extend(['-metadata', f'R128_TRACK_GAIN={r128_track_gain}'])

    if r128_album_gain is not None:
        metadata_cmd.extend(['-metadata', f'R128_ALBUM_GAIN={r128_album_gain}'])

    if loudness_metadata:
        for key, value in loudness_metadata.items():
            metadata_cmd.extend(['-metadata', f'{key}={value}'])

    extra_opts = []
    if file_format.lower() == 'mp3':
        extra_opts = ['-id3v2_version', '3', '-write_id3v1', '1']

    command = [
        'ffmpeg', '-hide_banner', '-y',
        '-i', '-',  
        '-c', 'copy',  
        '-map_metadata', '0',
    ] + extra_opts + metadata_cmd + [
        '-f', file_format, 
        '-'
    ]

    with Popen(command, stdin=PIPE, stdout=PIPE, stderr=PIPE) as process:
        output, error = process.communicate(input=file_like.getvalue())

    if process.returncode != 0:
        logger.error(f"FFmpeg error: {error.decode()}")
        raise Exception(f"FFmpeg error: {error.decode()}")

    return output

def process_replaygain(file_content: bytes, file_format: str) -> bytes:
    """Process ReplayGain for a given audio file content.

    Args:
        file_content: The binary content of the audio file.
        file_format: The format of the audio file.

    Returns:
        bytes: The binary content of the audio file with ReplayGain and other loudness metadata.
    """
    file_like = BytesIO(file_content)

    gain, peak, loudness_metadata = calculate_replaygain(file_like, file_format)
    r128_track_gain = int((gain - 1.0) * 256) if 'R128_TRACK_GAIN' not in loudness_metadata else int(loudness_metadata['R128_TRACK_GAIN'])
    r128_album_gain = 0

    updated_content = apply_replaygain(
        file_like, gain, peak, file_format,
        r128_track_gain=r128_track_gain,
        r128_album_gain=r128_album_gain,
        loudness_metadata=loudness_metadata
    )

    final_size = len(updated_content)
    logger.debug(f"Final post-replaygain file size: {final_size} bytes")

    return updated_content

def has_replaygain_metadata(content: BytesIO, file_format: str) -> bool:
    """Check if the file content has ReplayGain metadata.

    Args:
        content: The binary content of the audio file.
        file_format: The format of the audio file.

    Returns:
        bool: True if ReplayGain metadata is present, False otherwise.
    """
    content.seek(0)
    try:
        from mutagen import File as MutagenFile
        audio_file = MutagenFile(content, easy=True)
    except Exception as e:
        logger.error(f"Error reading file with Mutagen: {e}")
        return False

    if audio_file is None:
        logger.error("Unsupported file format or corrupted file.")
        return False

    def log_replaygain_metadata(tags, metadata_keys):
        has_metadata = False
        for key in metadata_keys:
            if key in tags:
                logger.debug(f"Found ReplayGain metadata: {key} = {tags[key]}")
                has_metadata = True
        return has_metadata

    metadata_keys = {
        "mp3": ["replaygain_track_gain", "replaygain_track_peak"],
        "flac": ["replaygain_track_gain", "replaygain_track_peak"],
        "opus": ["R128_TRACK_GAIN", "R128_ALBUM_GAIN"]
    }.get(file_format.lower(), [])

    return log_replaygain_metadata(audio_file, metadata_keys)
