"""
Google Drive integration module for HOA Parking Compliance Tracker.
Handles photo uploads, folder management, and file organization.
"""

import os
from datetime import datetime
from io import BytesIO
from typing import Optional, Tuple
from PIL import Image
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError


class DriveManager:
    """Manages Google Drive operations for photo storage."""
    
    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    SUPPORTED_FORMATS = ['jpg', 'jpeg', 'png', 'heic', 'webp', 'bmp', 'gif']
    
    def __init__(self, folder_id: str, credentials_path: str):
        """
        Initialize the Drive Manager.
        
        Args:
            folder_id: Google Drive folder ID for photo storage
            credentials_path: Path to service account JSON key file
        """
        self.folder_id = folder_id
        self.credentials_path = credentials_path
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Drive API using service account."""
        scopes = [
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
        ]
        
        creds = Credentials.from_service_account_file(
            self.credentials_path,
            scopes=scopes
        )
        
        self.service = build('drive', 'v3', credentials=creds)
    
    @staticmethod
    def get_month_folder_name(date: datetime = None) -> str:
        """
        Get the folder name for a given month.
        
        Args:
            date: Date to get folder name for (defaults to current date)
            
        Returns:
            Folder name in format "Jan-2026"
        """
        if date is None:
            date = datetime.now()
        return date.strftime("%b-%Y")
    
    def find_folder_by_name(self, folder_name: str, parent_id: str) -> Optional[str]:
        """
        Find a folder by name within a parent folder.
        
        Args:
            folder_name: Name of folder to find
            parent_id: Parent folder ID
            
        Returns:
            Folder ID if found, None otherwise
        """
        try:
            query = (
                f"name='{folder_name}' and "
                f"'{parent_id}' in parents and "
                f"mimeType='application/vnd.google-apps.folder' and "
                f"trashed=false"
            )
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            
            return None
            
        except HttpError as e:
            print(f"Error finding folder: {e}")
            return None
    
    def create_folder(self, folder_name: str, parent_id: str) -> Optional[str]:
        """
        Create a new folder in Google Drive.
        
        Args:
            folder_name: Name of the folder to create
            parent_id: Parent folder ID
            
        Returns:
            Created folder ID if successful, None otherwise
        """
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
            
            return folder.get('id')
            
        except HttpError as e:
            print(f"Error creating folder: {e}")
            return None
    
    def get_or_create_month_folder(self, date: datetime = None) -> Optional[str]:
        """
        Get existing month folder or create new one if it doesn't exist.
        
        Args:
            date: Date to get/create folder for (defaults to current date)
            
        Returns:
            Month folder ID if successful, None otherwise
        """
        folder_name = self.get_month_folder_name(date)
        
        # Check if folder exists
        folder_id = self.find_folder_by_name(folder_name, self.folder_id)
        
        if folder_id:
            return folder_id
        
        # Create new folder
        return self.create_folder(folder_name, self.folder_id)
    
    @staticmethod
    def validate_file_size(file_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate that file size is within limits.
        
        Args:
            file_bytes: File content as bytes
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        file_size = len(file_bytes)
        
        if file_size > DriveManager.MAX_FILE_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            return False, f"File size ({size_mb:.1f}MB) exceeds maximum allowed size ({DriveManager.MAX_FILE_SIZE_MB}MB)"
        
        return True, None
    
    @staticmethod
    def convert_to_jpg(image_bytes: bytes, format_hint: Optional[str] = None) -> bytes:
        """
        Convert image to JPG format.
        
        Args:
            image_bytes: Original image bytes
            format_hint: Optional format hint (e.g., 'png', 'heic')
            
        Returns:
            Converted image as JPG bytes
        """
        try:
            # Open image
            image = Image.open(BytesIO(image_bytes))
            
            # Convert RGBA to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Save as JPG
            output = BytesIO()
            image.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            return output.getvalue()
            
        except Exception as e:
            print(f"Error converting image to JPG: {e}")
            raise
    
    @staticmethod
    def generate_filename(license_plate: str, tag_number: str) -> str:
        """
        Generate filename for uploaded photo.
        
        Args:
            license_plate: Vehicle license plate
            tag_number: Parking tag number
            
        Returns:
            Filename in format "LICENSE_TAG_TIMESTAMP.jpg"
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize license plate and tag for filename
        safe_license = license_plate.replace(' ', '').replace('-', '')
        safe_tag = tag_number.replace(' ', '').replace('-', '')
        return f"{safe_license}_{safe_tag}_{timestamp}.jpg"
    
    def upload_photo(
        self,
        file_bytes: bytes,
        license_plate: str,
        tag_number: str,
        original_filename: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload photo to Google Drive with proper naming and organization.
        
        Args:
            file_bytes: Photo file content as bytes
            license_plate: Vehicle license plate
            tag_number: Parking tag number
            original_filename: Original filename (for format detection)
            
        Returns:
            Tuple of (success, file_url, error_message)
        """
        try:
            # Validate file size
            is_valid, error = self.validate_file_size(file_bytes)
            if not is_valid:
                return False, None, error
            
            # Convert to JPG
            try:
                jpg_bytes = self.convert_to_jpg(file_bytes)
            except Exception as e:
                return False, None, f"Failed to process image: {str(e)}"
            
            # Get or create month folder
            month_folder_id = self.get_or_create_month_folder()
            
            if not month_folder_id:
                return False, None, "Failed to create/access month folder in Google Drive"
            
            # Generate filename
            filename = self.generate_filename(license_plate, tag_number)
            
            # Upload file
            file_metadata = {
                'name': filename,
                'parents': [month_folder_id]
            }
            
            media = MediaIoBaseUpload(
                BytesIO(jpg_bytes),
                mimetype='image/jpeg',
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()
            
            file_id = file.get('id')
            
            # Make file accessible via link
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission,
                supportsAllDrives=True
            ).execute()
            
            # Get shareable link
            file_url = f"https://drive.google.com/file/d/{file_id}/view"
            
            return True, file_url, None
            
        except HttpError as e:
            error_msg = f"Google Drive API error: {str(e)}"
            print(error_msg)
            return False, None, error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error uploading photo: {str(e)}"
            print(error_msg)
            return False, None, error_msg
