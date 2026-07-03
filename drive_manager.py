"""
Google Drive Manager for HOA Parking Compliance Tracker.

Manages photo uploads to a Google Drive folder using per-user OAuth credentials.
Read operations (list, delete, storage usage) use the service account.
Upload operations require user OAuth credentials (each user's uploads count
against their own Google Drive storage quota).
"""

import os
from datetime import datetime
from io import BytesIO
from typing import Tuple, Optional, List, Dict

from PIL import Image, ImageOps

# Register HEIC support with Pillow (iOS default photo format)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError


class DriveManager:
    """Manages Google Drive photo uploads with per-user OAuth."""

    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

    def __init__(self, folder_id: str, credentials_path: str):
        """
        Initialize DriveManager.

        Args:
            folder_id: Google Drive folder ID (shared with service account as Editor).
            credentials_path: Path to Google service account JSON key file.
        """
        self.folder_id = folder_id
        self.credentials_path = credentials_path
        self._service = None  # Service account service (for read/list/delete)
        self._monthly_folder_cache = {}

    @property
    def service(self):
        """Lazy-initialize the Drive service (service account — for read ops)."""
        if self._service is None:
            scopes = ['https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_service_account_file(
                self.credentials_path,
                scopes=scopes
            )
            self._service = build('drive', 'v3', credentials=creds)
        return self._service

    def _get_oauth_service(self, oauth_credentials: OAuthCredentials):
        """Build a Drive service using user OAuth credentials (for uploads)."""
        return build('drive', 'v3', credentials=oauth_credentials)

    def _get_or_create_monthly_folder(self, year_month: str, drive_service=None) -> str:
        """
        Get or create a monthly subfolder (e.g., '2026-06').

        Args:
            year_month: Folder name in 'YYYY-MM' format.
            drive_service: Optional Drive service to use (OAuth). Falls back to service account.

        Returns:
            Folder ID of the monthly subfolder.
        """
        if year_month in self._monthly_folder_cache:
            return self._monthly_folder_cache[year_month]

        svc = drive_service or self.service

        query = (
            f"name = '{year_month}' and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"'{self.folder_id}' in parents and "
            f"trashed = false"
        )
        results = svc.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1
        ).execute()

        files = results.get('files', [])

        if files:
            folder_id = files[0]['id']
        else:
            folder_metadata = {
                'name': year_month,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.folder_id]
            }
            folder = svc.files().create(
                body=folder_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
            folder_id = folder['id']

        self._monthly_folder_cache[year_month] = folder_id
        return folder_id

    @staticmethod
    def convert_to_jpg(image_bytes: bytes) -> bytes:
        """Convert image to JPG format, preserving EXIF orientation."""
        image = Image.open(BytesIO(image_bytes))
        
        try:
            # Bake EXIF orientation into pixel data before re-encoding
            # (re-saving as JPEG strips the EXIF orientation tag, so without
            # this the image would appear rotated on viewers like Google Drive)
            image = ImageOps.exif_transpose(image)

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
        finally:
            # Explicitly close the image to free memory
            image.close()

    def upload_photo(
        self,
        file_bytes: bytes,
        license_plate: str,
        tag_number: str,
        original_filename: Optional[str] = None,
        oauth_credentials: Optional[OAuthCredentials] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Upload a photo to the appropriate monthly folder.

        Uses OAuth credentials if provided (per-user upload).
        Falls back to service account if no OAuth credentials (will likely fail
        due to storage quota on free GCP projects).

        Args:
            file_bytes: Raw image bytes.
            license_plate: License plate for filename.
            tag_number: Tag number for filename.
            original_filename: Original filename (unused, kept for API compat).
            oauth_credentials: User's OAuth credentials for upload.

        Returns:
            Tuple of (success, photo_url, error_message)
        """
        if oauth_credentials is None:
            return False, None, (
                "Google sign-in required for photo uploads. "
                "Please sign in with your Google account above."
            )

        try:
            if len(file_bytes) > self.MAX_FILE_SIZE_BYTES:
                size_mb = len(file_bytes) / (1024 * 1024)
                return False, None, f"File size ({size_mb:.1f}MB) exceeds maximum ({self.MAX_FILE_SIZE_MB}MB)"

            try:
                jpg_bytes = self.convert_to_jpg(file_bytes)
            except Exception as e:
                return False, None, f"Failed to process image: {str(e)}"

            # Use OAuth service for the upload
            oauth_service = self._get_oauth_service(oauth_credentials)

            now = datetime.now()
            year_month = now.strftime('%Y-%m')
            monthly_folder_id = self._get_or_create_monthly_folder(year_month, oauth_service)

            timestamp_str = now.strftime('%Y%m%d_%H%M%S')
            safe_plate = license_plate.replace(' ', '').replace('/', '_')
            safe_tag = str(tag_number).replace(' ', '').replace('/', '_')
            filename = f"{safe_plate}_{safe_tag}_{timestamp_str}.jpg"

            file_metadata = {
                'name': filename,
                'parents': [monthly_folder_id]
            }

            media = MediaIoBaseUpload(
                BytesIO(jpg_bytes),
                mimetype='image/jpeg',
                resumable=True
            )

            uploaded_file = oauth_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink',
                supportsAllDrives=True
            ).execute()

            # Make publicly viewable
            try:
                permission = {'type': 'anyone', 'role': 'reader'}
                oauth_service.permissions().create(
                    fileId=uploaded_file['id'],
                    body=permission,
                    fields='id',
                    supportsAllDrives=True
                ).execute()
            except Exception:
                pass

            file_url = f"https://drive.google.com/file/d/{uploaded_file['id']}/view"
            return True, file_url, None

        except HttpError as e:
            return False, None, f"Google Drive API error: {str(e)}"
        except Exception as e:
            return False, None, f"Unexpected error uploading photo: {str(e)}"

    def get_storage_usage(self) -> Dict[str, any]:
        """
        Calculate storage usage by summing file sizes in the shared folder.

        Returns:
            Dict with 'used_bytes', 'used_human', 'file_count'
        """
        try:
            total_size = 0
            file_count = 0

            monthly_folders = self.list_monthly_folders()
            for folder in monthly_folders:
                files = self.list_files_in_folder(folder['id'])
                for f in files:
                    total_size += int(f.get('size', 0))
                    file_count += 1

            return {
                'used_bytes': total_size,
                'used_human': self._bytes_to_human(total_size),
                'file_count': file_count,
            }
        except Exception as e:
            return {
                'used_bytes': 0,
                'used_human': 'Unknown',
                'file_count': 0,
                'error': str(e)
            }

    def list_monthly_folders(self) -> List[Dict[str, str]]:
        """List all monthly subfolders (sorted newest first)."""
        try:
            query = (
                f"'{self.folder_id}' in parents and "
                f"mimeType = 'application/vnd.google-apps.folder' and "
                f"trashed = false"
            )
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                orderBy='name desc',
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            return results.get('files', [])
        except Exception:
            return []

    def list_files_in_folder(self, folder_id: str) -> List[Dict]:
        """List all files in a specific folder."""
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
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()

                all_files.extend(results.get('files', []))
                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            return all_files
        except Exception:
            return []

    def list_files_in_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """List all photo files created within a date range."""
        try:
            all_files = []
            monthly_folders = self.list_monthly_folders()

            for folder in monthly_folders:
                folder_name = folder['name']
                try:
                    folder_date = datetime.strptime(folder_name, '%Y-%m')
                    if folder_date.month == 12:
                        folder_end = datetime(folder_date.year + 1, 1, 1)
                    else:
                        folder_end = datetime(folder_date.year, folder_date.month + 1, 1)

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
        """Permanently delete files by ID. Returns (success_count, fail_count)."""
        success = 0
        failed = 0
        for file_id in file_ids:
            try:
                self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
                success += 1
            except Exception:
                failed += 1
        return success, failed

    def delete_monthly_folder_contents(self, folder_id: str) -> Tuple[int, int]:
        """Delete all files inside a monthly folder."""
        files = self.list_files_in_folder(folder_id)
        file_ids = [f['id'] for f in files]
        return self.delete_files(file_ids)

    def get_folder_url(self) -> str:
        """Get the URL for the photos folder."""
        return f"https://drive.google.com/drive/folders/{self.folder_id}"

    def _get_or_create_exports_folder(self, oauth_credentials: OAuthCredentials) -> str:
        """
        Get or create the 'exports' folder (sibling to monthly folders).

        Uses OAuth credentials since it may need to create a folder.

        Returns:
            Folder ID of the exports folder.
        """
        if 'exports' in self._monthly_folder_cache:
            return self._monthly_folder_cache['exports']

        svc = self._get_oauth_service(oauth_credentials)

        query = (
            f"name = 'exports' and "
            f"mimeType = 'application/vnd.google-apps.folder' and "
            f"'{self.folder_id}' in parents and "
            f"trashed = false"
        )
        results = svc.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1
        ).execute()

        files = results.get('files', [])

        if files:
            folder_id = files[0]['id']
        else:
            folder_metadata = {
                'name': 'exports',
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [self.folder_id]
            }
            folder = svc.files().create(
                body=folder_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
            folder_id = folder['id']

        self._monthly_folder_cache['exports'] = folder_id
        return folder_id

    @staticmethod
    def extract_file_id_from_url(url: str) -> Optional[str]:
        """Extract Google Drive file ID from a Drive URL."""
        if not url or not isinstance(url, str):
            return None
        # Handle https://drive.google.com/file/d/FILE_ID/view
        if '/file/d/' in url:
            parts = url.split('/file/d/')[1]
            return parts.split('/')[0]
        # Handle https://drive.google.com/open?id=FILE_ID
        if 'id=' in url:
            return url.split('id=')[1].split('&')[0]
        return None

    def export_vehicle_photos(
        self,
        license_plate: str,
        make: str,
        model: str,
        photo_urls: List[str],
        first_seen: str,
        last_seen: str,
        oauth_credentials: OAuthCredentials
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Create an export folder with shortcuts to all photos for a vehicle.

        Creates: exports/{PLATE}_{MAKE}_{MODEL}_{first}_to_{last}/
        with Drive shortcuts (not copies) to each photo file.

        Args:
            license_plate: Vehicle plate.
            make: Vehicle make.
            model: Vehicle model.
            photo_urls: List of Google Drive photo URLs.
            first_seen: First seen date string (YYYY-MM-DD).
            last_seen: Last seen date string (YYYY-MM-DD).
            oauth_credentials: User OAuth credentials.

        Returns:
            Tuple of (success, folder_url, error_message)
        """
        if not oauth_credentials:
            return False, None, "Sign in with Google to export photos."

        # Extract valid file IDs from URLs
        file_ids = []
        for url in photo_urls:
            fid = self.extract_file_id_from_url(url)
            if fid:
                file_ids.append(fid)

        if not file_ids:
            return False, None, "No photos found to export."

        try:
            svc = self._get_oauth_service(oauth_credentials)

            # Get or create the exports parent folder
            exports_folder_id = self._get_or_create_exports_folder(oauth_credentials)

            # Build a descriptive folder name
            safe_plate = license_plate.replace(' ', '').replace('/', '_')
            parts = [safe_plate]
            if make and str(make).strip():
                parts.append(str(make).strip().replace(' ', '-'))
            if model and str(model).strip():
                parts.append(str(model).strip().replace(' ', '-'))
            parts.append(f"{first_seen}_to_{last_seen}")
            folder_name = '_'.join(parts)

            # Create the export subfolder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [exports_folder_id]
            }
            export_folder = svc.files().create(
                body=folder_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
            export_folder_id = export_folder['id']

            # Create shortcuts to each photo
            created = 0
            failed = 0
            for file_id in file_ids:
                try:
                    # Get the original file name
                    original = svc.files().get(
                        fileId=file_id,
                        fields='name',
                        supportsAllDrives=True
                    ).execute()

                    shortcut_metadata = {
                        'name': original.get('name', file_id),
                        'mimeType': 'application/vnd.google-apps.shortcut',
                        'shortcutDetails': {
                            'targetId': file_id
                        },
                        'parents': [export_folder_id]
                    }
                    svc.files().create(
                        body=shortcut_metadata,
                        fields='id',
                        supportsAllDrives=True
                    ).execute()
                    created += 1
                except Exception:
                    failed += 1

            folder_url = f"https://drive.google.com/drive/folders/{export_folder_id}"

            if created == 0:
                return False, None, f"Failed to create any shortcuts ({failed} errors)"

            msg = f"Exported {created} photo(s)"
            if failed > 0:
                msg += f" ({failed} failed)"

            return True, folder_url, msg

        except HttpError as e:
            return False, None, f"Google Drive API error: {str(e)}"
        except Exception as e:
            return False, None, f"Export failed: {str(e)}"

    @staticmethod
    def _bytes_to_human(num_bytes: int) -> str:
        """Convert bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if abs(num_bytes) < 1024:
                return f"{num_bytes:.1f} {unit}"
            num_bytes /= 1024
        return f"{num_bytes:.1f} TB"
