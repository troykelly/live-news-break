import os
import logging
import time
from base64 import b64encode
from datetime import datetime
from typing import Dict, Optional, Union

import requests
from requests import RequestException

from logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

RETRY_COUNT = 5
BACKOFF_FACTOR = 0.3

class AzuraCastClient:
    """Client for interacting with the AzuraCast API."""

    def __init__(self) -> None:
        """Initializes the AzuraCast client with environment variables."""
        self.host: Optional[str] = os.getenv('AZURACAST_HOST')
        self.api_key: Optional[str] = os.getenv('AZURACAST_API_KEY')
        self.station_id: Optional[int] = int(os.getenv('AZURACAST_STATIONID', '0'))
        self.path: Optional[str] = os.getenv('AZURACAST_PATH')
        self.playlist_name: Optional[str] = os.getenv('AZURACAST_PLAYLIST')
        self.filename_template: str = os.getenv('AZURACAST_FILENAME', 'news.%EXT%')

    def _perform_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Union[str, int]]] = None,
        json: Optional[Dict[str, Union[str, int, list]]] = None
    ) -> Dict[str, Union[str, int, list]]:
        """Performs an HTTP request with retries and exponential backoff.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint.
            headers: Optional request headers.
            data: Optional data to be sent in the body of the request.
            json: Optional JSON data to be sent in the body of the request.

        Returns:
            A dictionary containing the JSON response.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        url = f"{self.host}/api{endpoint}"
        headers = headers or {}
        headers.update({"X-API-Key": self.api_key})
        
        for attempt in range(RETRY_COUNT):
            try:
                response = requests.request(method, url, headers=headers, data=data, json=json)
                response.raise_for_status()
                return response.json()
            except RequestException as e:
                status_code = e.response.status_code if e.response else None
                if status_code in {500, 502, 503, 504}:
                    logging.error(f"Attempt {attempt + 1} failed with status {status_code}: {e}")
                    if attempt < RETRY_COUNT - 1:
                        sleep_time = BACKOFF_FACTOR * (2 ** attempt)
                        logging.info(f"Retrying in {sleep_time} seconds...")
                        time.sleep(sleep_time)
                    else:
                        logging.error("Maximum retry attempts reached.")
                        raise
                else:
                    logging.error(f"Request failed with status {status_code}: {e}")
                    raise

    def format_filename(self, template: str, extension: str) -> str:
        """Formats the filename by substituting placeholders with the current date and time values and extension.

        Args:
            template: The filename template with placeholders.
            extension: The extension of the file to be included in the filename.

        Returns:
            The formatted filename.
        """
        current_time = datetime.now()
        formatted_filename = template.replace('%Y', current_time.strftime('%Y'))
        formatted_filename = formatted_filename.replace('%m', current_time.strftime('%m'))
        formatted_filename = formatted_filename.replace('%d', current_time.strftime('%d'))
        formatted_filename = formatted_filename.replace('%H', current_time.strftime('%H'))
        formatted_filename = formatted_filename.replace('%M', current_time.strftime('%M'))
        formatted_filename = formatted_filename.replace('%S', current_time.strftime('%S'))
        formatted_filename = formatted_filename.replace('%EXT%', extension)
        return formatted_filename

    def upload_file_to_azuracast(self, file_content: bytes, file_key: str) -> Dict[str, Union[str, int]]:
        """Uploads a file to AzuraCast.

        Args:
            file_content: Content of the file to be uploaded.
            file_key: Key (name) of the file to be uploaded.

        Returns:
            A dictionary containing the JSON response from the server.
        """
        endpoint = f"/station/{self.station_id}/files"
        
        b64_content = b64encode(file_content).decode('utf-8')
        data = {
            "path": file_key,
            "file": b64_content
        }
        return self._perform_request('POST', endpoint, json=data)

    def get_playlist_id(self, playlist_name: str) -> Optional[int]:
        """Retrieves the ID of a playlist by its name.

        Args:
            playlist_name: Name of the playlist.

        Returns:
            The ID of the playlist if found, otherwise None.
        """
        endpoint = f"/station/{self.station_id}/playlists"
        playlists = self._perform_request('GET', endpoint)
        for playlist in playlists:
            if playlist['name'] == playlist_name:
                return playlist['id']
        return None

    def empty_playlist(self, playlist_id: int) -> None:
        """Empties a playlist.

        Args:
            playlist_id: ID of the playlist to be emptied.
        """
        endpoint = f"/station/{self.station_id}/playlist/{playlist_id}/empty"
        self._perform_request('DELETE', endpoint)

    def add_to_playlist(self, file_id: int, playlist_id: int) -> None:
        """Adds a file to a playlist.

        Args:
            file_id: ID of the file to be added.
            playlist_id: ID of the playlist.
        """
        endpoint = f"/station/{self.station_id}/file/{file_id}"
        data = {
            "playlists": [playlist_id]
        }
        self._perform_request('PUT', endpoint, json=data)

    def update_track_metadata(self, track_id: int, metadata: Dict[str, Union[str, int]]) -> None:
        """Updates metadata for an existing track in AzuraCast.

        Args:
            track_id: The ID of the track.
            metadata: Metadata dictionary containing fields to update.
        """
        if not all([self.host, self.api_key, self.station_id]):
            logging.info("AzuraCast environment variables are not fully set")
            return
        
        endpoint = f"/station/{self.station_id}/file/{track_id}"
        self._perform_request('PUT', endpoint, json=metadata)

    def upload_file(self, file_content: bytes, file_key: str) -> int:
        """Integrates with AzuraCast by uploading a file and managing its playlist.

        Args:
            file_content: Content of the file to be uploaded.
            file_key: Key (name) of the file to be uploaded.
            
        Returns:
            The ID of the uploaded file.
        """
        if not all([self.host, self.api_key, self.station_id]):
            logging.info("AzuraCast environment variables are not fully set")
            return

        try:
            file_key = f"{self.path}/{file_key}" if self.path else file_key
            
            upload_response = self.upload_file_to_azuracast(file_content, file_key)
            file_id = upload_response['id']
            logging.info(f"Uploaded Azuracast file with ID: {file_id}")

            if self.playlist_name:
                playlist_id = self.get_playlist_id(self.playlist_name)
                if playlist_id:
                    self.empty_playlist(playlist_id)
                    self.add_to_playlist(file_id, playlist_id)
                    logging.info(f"Added file to Azuracast playlist: {self.playlist_name}")
                    
            # Ensure the file ID is an integer and return it
            if isinstance(file_id, int):
                return file_id
        except requests.RequestException as e:
            logging.error(f"Failed to integrate with AzuraCast: {e}")

# Example usage:
# azuracast_client = AzuraCastClient()
# azuracast_client.upload_file(file_content, 'filename.mp3')
