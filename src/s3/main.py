import os
import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from io import BytesIO

logging.basicConfig(level=logging.INFO)

class S3Client:
    """
    Client for interacting with S3-compatible storage services.
    """
    
    def __init__(self):
        """
        Initializes the S3 client with environment variables.
        """
        self.bucket_name = os.getenv('S3_BUCKET_NAME')
        self.region_name = os.getenv('S3_REGION_NAME', 'us-east-1')
        self.endpoint_url = os.getenv('S3_ENDPOINT_URL')
        self.access_key = os.getenv('S3_ACCESS_KEY')
        self.secret_key = os.getenv('S3_SECRET_KEY')
        self.path = os.getenv('S3_PATH', '').strip('/')
        self.filename_template = os.getenv('S3_FILENAME', 'news_%Y%m%d_%H%M%S.%EXT%')
        
        self.s3_client = boto3.client('s3', 
                                      region_name=self.region_name,
                                      endpoint_url=self.endpoint_url,
                                      aws_access_key_id=self.access_key,
                                      aws_secret_access_key=self.secret_key)

    def format_filename(self, template, extension):
        """
        Formats the filename by substituting placeholders with the current date and time values and extension.
        
        Args:
            template (str): The filename template with placeholders.
            extension (str): The extension of the file to be included in the filename.
        
        Returns:
            str: The formatted filename.
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

    def upload_file(self, file_content, file_key, content_type):
        """
        Uploads a file to S3-compatible storage.

        Args:
            file_content (bytes): Content of the file to be uploaded.
            file_key (str): Key (name) of the file to be uploaded.
            content_type (str): MIME type of the file to be uploaded.

        Returns:
            bool: True if file uploaded successfully, False otherwise.
        """
        try:
            file_key = f"{self.path}/{file_key}" if self.path else file_key

            self.s3_client.put_object(Bucket=self.bucket_name,
                                      Key=file_key,
                                      Body=file_content,
                                      ContentType=content_type)
            logging.info(f"File successfully uploaded with key: {file_key}")
            return True
        except (BotoCoreError, ClientError) as e:
            logging.error(f"Failed to upload file: {e}")
            return False
