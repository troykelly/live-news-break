import os
import requests
import logging
from base64 import b64encode

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

    def upload_file(self, file_path, file_content):
        """
        Uploads a file to AzuraCast.

        Args:
            file_path (str): Path to the file to be uploaded.
            file_content (bytes): Content of the file to be uploaded.

        Returns:
            dict: JSON response from the server.
        """
        endpoint = f"/station/{self.station_id}/files"
        b64_content = b64encode(file_content).decode('utf-8')
        data = {
            "path": f"{self.path}/{self.filename}",
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

    def integrate_azuracast(self, file_path, file_content):
        """
        Integrates with AzuraCast by uploading a file and managing its playlist.

        Args:
            file_path (str): Local path to the file to be uploaded.
            file_content (bytes): Content of the file to be uploaded.
        """
        if not all([self.host, self.api_key, self.station_id, self.path, self.filename]):
            logging.info("AzuraCast environment variables are not fully set")
            return

        try:
            upload_response = self.upload_file(file_path, file_content)
            file_id = upload_response['id']

            if self.playlist_name:
                playlist_id = self.get_playlist_id(self.playlist_name)
                if playlist_id:
                    self.empty_playlist(playlist_id)
                    self.add_to_playlist(file_id, playlist_id)
        except requests.RequestException as e:
            logging.error(f"Failed to integrate with AzuraCast: {e}")

# Usage example:
# azuracast_client = AzuraCastClient()
# azuracast_client.integrate_azuracast("/path/to/generated/news_report.mp3", open("/path/to/generated/news_report.mp3", "rb").read())