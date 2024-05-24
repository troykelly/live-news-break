import os
import requests
import logging
from base64 import b64encode
from pydub import AudioSegment
from io import BytesIO
from datetime import datetime

logging.basicConfig(level=logging.INFO)

class AzuraCastClient:
    """
    Client for interacting with the AzuraCast API.
    """
    
    def __init__(self):
        """
        Initializes the AzuraCast client with environment variables.
        """
        self.host = os.getenv('AZURACAST_HOST')
        self.api_key = os.getenv('AZURACAST_API_KEY')
        self.station_id = os.getenv('AZURACAST_STATIONID')
        self.path = os.getenv('AZURACAST_PATH')
        self.filename = os.getenv('AZURACAST_FILENAME')
        self.playlist_name = os.getenv('AZURACAST_PLAYLIST')

    def _perform_request(self, method, endpoint, headers=None, data=None, json=None):
        """
        Performs an HTTP request.

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE).
            endpoint (str): API endpoint.
            headers (dict, optional): Request headers.
            data (dict, optional): Data to be sent in the body of the request.
            json (dict, optional): JSON data to be sent in the body of the request.

        Returns:
            dict: JSON response.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        url = f"{self.host}/api{endpoint}"
        headers = headers or {}
        headers.update({"X-API-Key": self.api_key})
        response = requests.request(method, url, headers=headers, data=data, json=json)
        response.raise_for_status()
        return response.json()

    def _format_filename(self, filename):
        """
        Formats the filename by substituting placeholders with the current date and time values.
        
        Args:
            filename (str): The filename template with placeholders.
        
        Returns:
            str: The formatted filename.
        """
        current_time = datetime.now()
        formatted_filename = filename.replace('%Y%', current_time.strftime('%Y'))
        formatted_filename = formatted_filename.replace('%m%', current_time.strftime('%m'))
        formatted_filename = formatted_filename.replace('%d%', current_time.strftime('%d'))
        formatted_filename = formatted_filename.replace('%H%', current_time.strftime('%H'))
        formatted_filename = formatted_filename.replace('%M%', current_time.strftime('%M'))
        formatted_filename = formatted_filename.replace('%S%', current_time.strftime('%S'))
        return formatted_filename

    def upload_file(self, file_content, filename, file_format):
        """
        Uploads a file to AzuraCast.

        Args:
            file_content (bytes): Content of the file to be uploaded.
            filename (str): Name of the file to be uploaded.
            file_format (str): Format of the file to be uploaded.

        Returns:
            dict: JSON response from the server.
        """
        endpoint = f"/station/{self.station_id}/files"
        
        # Format filename using current date and time
        filename_with_extension = self._format_filename(filename) + f".{file_format}"

        b64_content = b64encode(file_content).decode('utf-8')
        data = {
            "path": f"{self.path}/{filename_with_extension}",
            "file": b64_content
        }
        return self._perform_request('POST', endpoint, json=data)

    def get_playlist_id(self, playlist_name):
        """
        Retrieves the ID of a playlist by its name.

        Args:
            playlist_name (str): Name of the playlist.

        Returns:
            Optional[int]: ID of the playlist if found, otherwise None.
        """
        endpoint = f"/station/{self.station_id}/playlists"
        playlists = self._perform_request('GET', endpoint)
        for playlist in playlists:
            if playlist['name'] == playlist_name:
                return playlist['id']
        return None

    def empty_playlist(self, playlist_id):
        """
        Empties a playlist.

        Args:
            playlist_id (int): ID of the playlist to be emptied.

        Returns:
            dict: JSON response from the server.
        """
        endpoint = f"/station/{self.station_id}/playlist/{playlist_id}/empty"
        return self._perform_request('DELETE', endpoint)

    def add_to_playlist(self, file_id, playlist_id):
        """
        Adds a file to a playlist.

        Args:
            file_id (int): ID of the file to be added.
            playlist_id (int): ID of the playlist.

        Returns:
            dict: JSON response from the server.
        """
        endpoint = f"/station/{self.station_id}/file/{file_id}"
        data = {
            "playlists": [playlist_id]
        }
        return self._perform_request('PUT', endpoint, json=data)

    def integrate_azuracast_with_audio_segment(self, audio_segment, file_format):
        """
        Integrates with AzuraCast by uploading an AudioSegment and managing its playlist.

        Args:
            audio_segment (AudioSegment): The AudioSegment object to be uploaded.
            file_format (str): The format of the audio file to be uploaded.
        """
        if not all([self.host, self.api_key, self.station_id, self.path, self.filename]):
            logging.info("AzuraCast environment variables are not fully set")
            return

        try:
            # Export AudioSegment to a BytesIO in the specified format
            output_bytes_io = BytesIO()
            audio_segment.export(output_bytes_io, format=file_format)
            output_bytes_io.seek(0)
            file_content = output_bytes_io.read()

            upload_response = self.upload_file(file_content, self.filename, file_format)
            file_id = upload_response['id']
            logging.info(f"Uploaded Azuracast file with ID: {file_id}")

            if self.playlist_name:
                playlist_id = self.get_playlist_id(self.playlist_name)
                if playlist_id:
                    self.empty_playlist(playlist_id)
                    self.add_to_playlist(file_id, playlist_id)
                    logging.info(f"Added file to Azuracast playlist: {self.playlist_name}")
        except requests.RequestException as e:
            logging.error(f"Failed to integrate with AzuraCast: {e}")

# Usage example:
# azuracast_client = AzuraCastClient()
# azuracast_client.integrate_azuracast_with_audio_segment(
#     audio_segment,  # An AudioSegment object
#     'mp3'          # Format of the output file
#)