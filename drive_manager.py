"""
Google Drive Manager for HOA Parking Compliance Tracker.

Manages photo uploads using the service account's own Drive storage.
Auto-creates a folder on first use and makes it publicly accessible.
"""

import os
from datetime import datetime
from io import BytesIO
from typing import Tuple, Optional, List, Dict

from PIL import Image
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError


# Folder name used by the service account (consistent across runs)
HOA_FOLDER_NAME = "HOA-Parking-Compliance-Photos"


class DriveManager:
    """Manages Google Drive photo uploads with self-provisioning folder."""

    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

    def __init__(self, credentials_path: str, legacy_folder_id: str = None):
        """
        Initialize DriveManager.

        Args:
            credentials_path: Path to Google service account JSON key file.
            legacy_folder_id: (Optional) Previously configured folder ID for backwards compat.
        """
        self.credentials_path = credentials_path
        self.legacy_folder_id = legacy_folder_id
        self._service = None
        self._root_folder_id = None
        self._monthly_folder_cache: Dict[str, str] = {}

    @property
    def service(self):
        """Lazy-initialize the Drive service."""
        if self._service is None:
            scopes = ['https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scopes
            )
            self._service = build('drive', 'v3', credentials=creds)
        return self._service

    @property
    def root_folder_id(self) -> str:
        """Get or create the root photo folder. Cached after first call."""
        if self._root_folder_id is None:
            self._root_folder_id = self._get_or_create_root_folder()
        return self._root_folder_id

    def _get_or_create_root_folder(self) -> str:
        """
        Find the existing HOA folder or create a new one.
        Makes it publicly accessible via link.
        """
        # Search for existing folder by name (owned by this service account)
        query = (
            f"name = '{HOA_FOLDER_NAME}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"trashed = false"
        )
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1
        ).execute()

        files = results.get('files', [])

        if files:
            # Folder already exists — reuse it
            folder_id = files[0]['id']
        else:
            # Create new folder
            folder_metadata = {
                'name': HOA_FOLDER_NAME,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            folder_id = folder['id']

            # Make it publicly accessible (anyone with link can view)
            self._set_public_access(folder_id)

        return folder_id

    def _set_public_access(self, file_or_folder_id: str):
        """Set 'anyone with the link' can view permission."""
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        try:
            self.service.permissions().create(
                fileId=file_or_folder_id,
                body=permission,
                fields='id'
            ).execute()
        except Exception:
            # Permission may already exist, ignore
            pass

    def _get_or_create_monthly_folder(self, year_month: str) -> str:
        """
        Get or create a monthly subfolder (e.g., '2026-06').

        Args:
            year_month: Folder name in 'YYYY-MM' format.

        Returns:
            Folder ID of the monthly subfolder.
        """
        if year_month in self._monthly_folder_cache:
            return self._monthly_folder_cache[year_month]

        # Search for existing monthly folder
        query = (
            f"name = '{year_month}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"'{self.root_folder_id}' in parents and "
            f"trashed = false"
        )
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1
        ).execute()

        files = results.get('files', [])

        if files:
            folder_id = files[0]['id']
        else:
            # Create monthly subfolder
            folder_metadata = {
                'name': year_month,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.root_folder_id]
            }
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            folder_id = folder['id']

        self._monthly_folder_cache[year_month] = folder_id
        return folder_id

    @staticmethod
    def convert_to_jpg(image_bytes: bytes) -> bytes:
        """
        Convert image to JPG format.

        Args:
            image_bytes: Original image bytes.

        Returns:
            Converted image as JPG bytes.
        """
        image = Image.open(BytesIO(image_bytes))

        # Convert RGBA/P to RGB
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        output = BytesIO()
        image.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        return output.getvalue()

    def upload_photo(
        self,
        file_bytes: bytes,
        license_plate: str,
        tag_number: str,
        original_filename: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload a photo to the appropriate monthly folder.

        Args:
            file_bytes: Raw image bytes.
            license_plate: Vehicle license plate (used in filename).
            tag_number: Vehicle tag number (used in filename).
            original_filename: Original file name for extension detection.

        Returns:
            Tuple of (success, photo_url, error_message)
        """
        try:
            # Validate file size
            if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
                size_mb = len(file_bytes) / (1024 * 1024)
                return False, None, f"File size ({size_mb:.1f}MB) exceeds maximum ({self.MAX_FILE_SIZE_MB}MB)"

            # Convert to JPG
            try:
                jpg_bytes = self.convert_to_jpg(file_bytes)
            except Exception as e:
                return False, None, f"Failed to process image: {str(e)}"

            # Determine monthly folder
            now = datetime.now()
            year_month = now.strftime('%Y-%m')
            monthly_folder_id = self._get_or_create_monthly_folder(year_month)

            # Build filename: PLATE_TAG_TIMESTAMP.jpg
            timestamp_str = now.strftime('%Y%m%d_%H%M%S')
            safe_plate = license_plate.replace(' ', '').replace('/', '_')
            safe_tag = str(tag_number).replace(' ', '').replace('/', '_')
            filename = f"{safe_plate}_{safe_tag}_{timestamp_str}.jpg"

            # Upload
            file_metadata = {
                'name': filename,
                'parents': [monthly_folder_id]
            }

            media = MediaIoBaseUpload(
                BytesIO(jpg_bytes),
                mimetype='image/jpeg',
                resumable=True
            )

            uploaded_file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()

            # Make the file publicly viewable
            self._set_public_access(uploaded_file['id'])

            file_url = f"https://drive.google.com/file/d/{uploaded_file['id']}/view"
            return True, file_url, None

        except HttpError as e:
            return False, None, f"Google Drive API error: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error uploading photo: {str(e)}"

    def get_storage_quota(self) -> Dict[str, any]:
        """
        Get storage usage and quota for the service account.

        Returns:
            Dict with 'used_bytes', 'total_bytes', 'used_percent',
            'used_human', 'total_human'
        """
        try:
            about = self.service.about().get(
                fields='storageQuota'
            ).execute()

            quota = about.get('storageQuota', {})
            used = int(quota.get('usage', 0))
            # Service accounts typically get 15GB
            total = int(quota.get('limit', 15 * 1024 * 1024 * 1024))

            percent = (used / total * 100) if total > 0 else 0

            return {
                'used_bytes': used,
                'total_bytes': total,
                'used_percent': round(percent, 2),
                'used_human': self._bytes_to_human(used),
                'total_human': self._bytes_to_human(total),
            }
        except Exception as e:
            return {
                'used_bytes': 0,
                'total_bytes': 15 * 1024 * 1024 * 1024,
                'used_percent': 0,
                'used_human': 'Unknown',
                'total_human': '15 GB',
                'error': str(e)
            }

    def list_monthly_folders(self) -> List[Dict[str, str]]:
        """
        List all monthly subfolders in the root folder.

        Returns:
            List of dicts with 'id', 'name' (sorted newest first).
        """
        try:
            query = (
                f"'{self.root_folder_id}' in parents and "
                f"mimeType = 'application/vnd.google-apps.folder' and "
                f"trashed = false"
            )
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                orderBy='name desc',
                pageSize=100
            ).execute()

            return results.get('files', [])
        except Exception:
            return []

    def list_files_in_folder(self, folder_id: str) -> List[Dict]:
        """
        List all files in a specific folder.

        Returns:
            List of dicts with 'id', 'name', 'size', 'createdTime'.
        """
        try:
            all_files = []
            page_token = None

            while True:
                query = (
                    f"'{folder_id}' in parents and "
                    f"mimeType != 'application/vnd.google-apps.folder' and "
                    f"trashed = false"
                )
                results = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, size, createdTime)',
                    pageSize=100,
                    pageToken=page_token
                ).execute()

                all_files.extend(results.get('files', []))
                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            return all_files
        except Exception:
            return []

    def list_files_in_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[Dict]:
        """
        List all photo files created within a date range.

        Args:
            start_date: Start of range (inclusive).
            end_date: End of range (inclusive).

        Returns:
            List of file dicts with 'id', 'name', 'size', 'createdTime'.
        """
        try:
            all_files = []

            # Go through monthly folders that overlap with the date range
            monthly_folders = self.list_monthly_folders()

            for folder in monthly_folders:
                folder_name = folder['name']  # e.g., '2026-06'
                try:
                    folder_date = datetime.strptime(folder_name, '%Y-%m')
                    # Calculate end of that month
                    if folder_date.month == 12:
                        folder_end = datetime(folder_date.year + 1, 1, 1)
                    else:
                        folder_end = datetime(folder_date.year, folder_date.month + 1, 1)

                    # Skip folders that don't overlap with date range
                    if folder_end <= start_date or folder_date > end_date:
                        continue
                except ValueError:
                    continue

                files = self.list_files_in_folder(folder['id'])
                for f in files:
                    try:
                        created = datetime.fromisoformat(
                            f['createdTime'].replace('Z', '+00:00')
                        ).replace(tzinfo=None)
                        if start_date <= created <= end_date:
                            f['folder_name'] = folder_name
                            all_files.append(f)
                    except (ValueError, KeyError):
                        continue

            return all_files
        except Exception:
            return []

    def delete_files(self, file_ids: List[str]) -> Tuple[int, int]:
        """
        Permanently delete files by ID.

        Args:
            file_ids: List of Google Drive file IDs to delete.

        Returns:
            Tuple of (success_count, fail_count)
        """
        success = 0
        failed = 0
        for file_id in file_ids:
            try:
                self.service.files().delete(fileId=file_id).execute()
                success += 1
            except Exception:
                failed += 1
        return success, failed

    def delete_monthly_folder_contents(self, folder_id: str) -> Tuple[int, int]:
        """
        Delete all files inside a monthly folder.

        Args:
            folder_id: The monthly folder ID.

        Returns:
            Tuple of (success_count, fail_count)
        """
        files = self.list_files_in_folder(folder_id)
        file_ids = [f['id'] for f in files]
        return self.delete_files(file_ids)

    def get_folder_url(self) -> str:
        """Get the public URL for the root photos folder."""
        return f"https://drive.google.com/drive/folders/{self.root_folder_id}"

    @staticmethod
    def _bytes_to_human(num_bytes: int) -> str:
        """Convert bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if abs(num_bytes) < 1024:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024
        return f"{num_bytes:.1f} TB"
