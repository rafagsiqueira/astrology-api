"""Google Cloud Storage service for storing chart SVG files."""

import os
import hashlib
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound, GoogleCloudError
from config import get_logger

logger = get_logger(__name__)

# Configuration
BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'cosmic-guru-charts')
CHARTS_FOLDER = 'charts'


class CloudStorageService:
    """Service for managing chart SVG files in Google Cloud Storage."""
    
    def __init__(self):
        """Initialize the Cloud Storage client."""
        try:
            self.client = storage.Client()
            self.bucket = self.client.bucket(BUCKET_NAME)
            logger.info(f"Initialized Cloud Storage service with bucket: {BUCKET_NAME}")
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Storage: {e}")
            self.client = None
            self.bucket = None
    
    def _generate_chart_filename(self, user_id: str, birth_data_hash: str) -> str:
        """Generate a unique filename for a chart SVG."""
        return f"{CHARTS_FOLDER}/{user_id}/{birth_data_hash}.svg"
    
    def _hash_birth_data(self, birth_data: dict) -> str:
        """Generate a hash from birth data for unique identification."""
        # Create a consistent string representation of birth data
        data_str = f"{birth_data.get('birth_date')}_{birth_data.get('birth_time')}_{birth_data.get('latitude')}_{birth_data.get('longitude')}"
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    def upload_chart_svg(self, user_id: str, birth_data: dict, svg_content: str) -> Optional[str]:
        """
        Upload chart SVG to Cloud Storage and return the public URL.
        
        Args:
            user_id: The user's Firebase UID
            birth_data: Dictionary containing birth data for hashing
            svg_content: The SVG content as string
            
        Returns:
            Public URL of the uploaded SVG or None if upload failed
        """
        if not self.bucket:
            logger.error("Cloud Storage not initialized")
            return None
            
        try:
            # Generate unique filename
            birth_hash = self._hash_birth_data(birth_data)
            filename = self._generate_chart_filename(user_id, birth_hash)
            
            # Check if file already exists
            blob = self.bucket.blob(filename)
            if blob.exists():
                logger.debug(f"Chart already exists: {filename}")
                blob.make_public()
                return blob.public_url
            
            # Upload new file
            blob.upload_from_string(
                svg_content,
                content_type='image/svg+xml'
            )
            
            # Make the blob publicly readable
            blob.make_public()
            
            public_url = blob.public_url
            logger.info(f"Successfully uploaded chart: {filename} -> {public_url}")
            return public_url
            
        except GoogleCloudError as e:
            logger.error(f"Google Cloud Storage error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading chart: {e}")
            return None
    
    def delete_chart_svg(self, user_id: str, birth_data: dict) -> bool:
        """
        Delete a chart SVG from Cloud Storage.
        
        Args:
            user_id: The user's Firebase UID
            birth_data: Dictionary containing birth data for hashing
            
        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.bucket:
            logger.error("Cloud Storage not initialized")
            return False
            
        try:
            birth_hash = self._hash_birth_data(birth_data)
            filename = self._generate_chart_filename(user_id, birth_hash)
            
            blob = self.bucket.blob(filename)
            blob.delete()
            
            logger.info(f"Successfully deleted chart: {filename}")
            return True
            
        except NotFound:
            logger.warning(f"Chart not found for deletion: {filename}")
            return True  # Consider this success since the desired state is achieved
        except GoogleCloudError as e:
            logger.error(f"Google Cloud Storage error during deletion: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting chart: {e}")
            return False
    
    def list_user_charts(self, user_id: str) -> list:
        """
        List all chart SVGs for a user.
        
        Args:
            user_id: The user's Firebase UID
            
        Returns:
            List of chart filenames
        """
        if not self.bucket:
            logger.error("Cloud Storage not initialized")
            return []
            
        try:
            prefix = f"{CHARTS_FOLDER}/{user_id}/"
            blobs = self.bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
            
        except GoogleCloudError as e:
            logger.error(f"Google Cloud Storage error listing charts: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing charts: {e}")
            return []
    
    def get_chart_url(self, user_id: str, birth_data: dict) -> Optional[str]:
        """
        Get the public URL for an existing chart without uploading.
        
        Args:
            user_id: The user's Firebase UID
            birth_data: Dictionary containing birth data for hashing
            
        Returns:
            Public URL if chart exists, None otherwise
        """
        if not self.bucket:
            logger.error("Cloud Storage not initialized")
            return None
            
        try:
            birth_hash = self._hash_birth_data(birth_data)
            filename = self._generate_chart_filename(user_id, birth_hash)
            
            blob = self.bucket.blob(filename)
            if blob.exists():
                blob.make_public()
                return blob.public_url
            else:
                return None
                
        except GoogleCloudError as e:
            logger.error(f"Google Cloud Storage error getting chart URL: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting chart URL: {e}")
            return None


# Global instance
cloud_storage_service = CloudStorageService()


def upload_chart_to_storage(user_id: str, birth_data: dict, svg_content: str) -> Optional[str]:
    """Convenience function to upload chart SVG."""
    return cloud_storage_service.upload_chart_svg(user_id, birth_data, svg_content)


def get_chart_from_storage(user_id: str, birth_data: dict) -> Optional[str]:
    """Convenience function to get chart URL."""
    return cloud_storage_service.get_chart_url(user_id, birth_data)


def delete_chart_from_storage(user_id: str, birth_data: dict) -> bool:
    """Convenience function to delete chart SVG."""
    return cloud_storage_service.delete_chart_svg(user_id, birth_data)