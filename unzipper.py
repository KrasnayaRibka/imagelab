"""
Module for extracting and processing ZIP archives containing images.

Author: Vadim Kalinin
Email: vadimakalin@gmail.com
"""
import zipfile
from pathlib import Path
from typing import List, Optional, Dict, Any
import os
import shutil

from logger_config import get_logger
from config import UPLOAD_DIR, USER_DIR_PREFIX, IMAGE_EXTENSIONS


class Unzipper:
    """
    Class for extracting and processing ZIP archives containing images.
    
    Provides functionality for extracting ZIP archives and handling
    image files contained within them.
    
    Author: Vadim Kalinin
    Email: vadimakalin@gmail.com
    """
    
    def __init__(self, extract_dir: Optional[Path] = None):
        """
        Initialize Unzipper with configuration.
        
        Args:
            extract_dir: Base directory for extracting ZIP archives.
                        If None, a default directory will be used.
        """
        self.extract_dir = extract_dir
        self.logger = get_logger(__name__)
    
    def unzipp(
        self,
        zip_path: Path,
        extract_to: Optional[Path] = None
    ) -> List[Path]:
        """
        Extract ZIP archive containing images.
        
        Args:
            zip_path: Path to the ZIP archive file
            extract_to: Directory where to extract files.
                       If None, uses self.extract_dir or creates a default directory.
        
        Returns:
            List of paths to extracted image files
        
        Raises:
            FileNotFoundError: If ZIP file doesn't exist
            zipfile.BadZipFile: If file is not a valid ZIP archive
            PermissionError: If extraction directory is not writable
        """
        # Validate ZIP file exists
        zip_path = Path(zip_path)
        if not zip_path.exists():
            self.logger.error("ZIP file not found: %s", zip_path)
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")
        
        # Determine extraction directory
        if extract_to is None:
            extract_to = self.extract_dir
        
        if extract_to is None:
            # Create default extraction directory next to ZIP file
            extract_to = zip_path.parent / f"{zip_path.stem}_extracted"
        
        extract_to = Path(extract_to)
        
        # Create extraction directory if it doesn't exist
        try:
            extract_to.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error("Failed to create extraction directory %s: %s", extract_to, e)
            raise PermissionError(f"Failed to create extraction directory: {extract_to}") from e
        
        # Verify directory is writable
        if not os.access(extract_to, os.W_OK):
            self.logger.error("Extraction directory is not writable: %s", extract_to)
            raise PermissionError(f"Extraction directory is not writable: {extract_to}")
        
        # Extract ZIP archive
        extracted_files = []
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Get list of all files in archive
                file_list = zip_ref.namelist()
                self.logger.info("Extracting ZIP archive %s with %d files", zip_path, len(file_list))
                
                # Extract all files
                zip_ref.extractall(extract_to)
                
                # Get paths to extracted files
                for filename in file_list:
                    extracted_path = extract_to / filename
                    if extracted_path.exists() and extracted_path.is_file():
                        extracted_files.append(extracted_path)
                
                self.logger.info("Successfully extracted %d files from %s", len(extracted_files), zip_path)
                
        except zipfile.BadZipFile as e:
            self.logger.error("Invalid ZIP file: %s", zip_path, exc_info=True)
            raise zipfile.BadZipFile(f"Invalid ZIP file: {zip_path}") from e
        except Exception as e:
            self.logger.error("Failed to extract ZIP archive %s: %s", zip_path, e, exc_info=True)
            raise
        
        return extracted_files
    
    def _is_valid_image_file(self, file_path: Path) -> bool:
        """
        Check if file is a valid image file based on its extension.
        
        Args:
            file_path: Path to the file to check
        
        Returns:
            True if file has a valid image extension, False otherwise
        """
        if not file_path.is_file():
            return False
        
        file_extension = file_path.suffix.lower()
        return file_extension in IMAGE_EXTENSIONS
    
    def _cleanup_invalid_files(self, directory: Path) -> List[Path]:
        """
        Remove files that are not valid images from the directory.
        
        Recursively scans the directory and removes all files that are not
        valid image files according to IMAGE_EXTENSIONS.
        
        Args:
            directory: Directory to clean up
        
        Returns:
            List of paths to remaining valid image files
        """
        valid_files = []
        deleted_count = 0
        
        # Recursively walk through all files in directory
        for item in directory.rglob('*'):
            if item.is_file():
                if self._is_valid_image_file(item):
                    valid_files.append(item)
                else:
                    # Delete invalid file
                    try:
                        item.unlink()
                        deleted_count += 1
                        self.logger.debug("Deleted invalid file: %s", item)
                    except Exception as e:
                        self.logger.warning("Failed to delete invalid file %s: %s", item, e)
        
        if deleted_count > 0:
            self.logger.info("Cleaned up %d invalid files from %s, %d valid image files remaining", 
                           deleted_count, directory, len(valid_files))
        
        return valid_files
    
    def process_unzipped_files(
        self,
        file_paths: List[Path],
        user_id: int,
        image_processor
    ) -> List[Dict[str, Any]]:
        """
        Process unzipped image files using image_processor.
        
        Each file is processed using the same logic as files from form upload:
        - Transliteration of filename
        - Unique filename generation
        - Original file with _orig prefix
        - JPG conversion
        - Thumbnail creation
        - Metadata extraction
        
        Args:
            file_paths: List of paths to image files in unzipped directory
            user_id: User ID for processing
            image_processor: ImageProcessor instance to use for processing
            
        Returns:
            List of dictionaries with file processing results (same format as save())
        """
        processed_files = []
        
        for file_path in file_paths:
            try:
                self.logger.info("Processing file from archive: %s", file_path)
                result = image_processor.save_from_path(file_path, user_id)
                processed_files.append(result)
                self.logger.info("Successfully processed file: %s", file_path)
            except Exception as e:
                self.logger.error("Failed to process file %s: %s", file_path, e, exc_info=True)
                # Continue processing other files even if one fails
                continue
        
        return processed_files
    
    def unzip_for_user(
        self,
        zip_path: Path,
        user_id: int,
        image_processor
    ) -> List[Dict[str, Any]]:
        """
        Extract ZIP archive to user's unzipped directory and process all files.
        
        Files are extracted to unzipped directory, invalid files are removed,
        then all valid image files are processed using image_processor.
        After processing, unzipped directory is deleted.
        
        Args:
            zip_path: Path to the ZIP archive file
            user_id: User ID to determine user directory
            image_processor: ImageProcessor instance to use for processing files
        
        Returns:
            List of dictionaries with file processing results (same format as save())
        
        Raises:
            FileNotFoundError: If ZIP file doesn't exist
            zipfile.BadZipFile: If file is not a valid ZIP archive
            PermissionError: If extraction directory is not writable
        """
        # Get user directory
        user_dir = UPLOAD_DIR / f"{USER_DIR_PREFIX}{user_id}"
        
        # Create user directory if it doesn't exist
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error("Failed to create user directory %s: %s", user_dir, e)
            raise PermissionError(f"Failed to create user directory: {user_dir}") from e
        
        # Create unzipped directory inside user directory
        unzipped_dir = user_dir / "unzipped"
        
        try:
            # Extract to user's unzipped directory
            extracted_files = self.unzipp(zip_path, extract_to=unzipped_dir)
            
            # Clean up invalid files (non-image files and files with invalid extensions)
            valid_image_files = self._cleanup_invalid_files(unzipped_dir)
            
            # Process all valid image files
            processed_files = self.process_unzipped_files(valid_image_files, user_id, image_processor)
            
            return processed_files
            
        finally:
            # Always try to remove unzipped directory after processing
            try:
                if unzipped_dir.exists():
                    shutil.rmtree(unzipped_dir)
                    self.logger.info("Removed unzipped directory: %s", unzipped_dir)
            except Exception as e:
                self.logger.warning("Failed to remove unzipped directory %s: %s", unzipped_dir, e)

