"""
Image processing module for handling image uploads and saving.

Author: Vadim Kalinin
Email: vadimakalin@gmail.com
"""
import hashlib
import json
import os
import random
import re
import shutil
import string
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import UploadFile, HTTPException
import aiofiles
try:
    import pyvips  # type: ignore[import-untyped]
except ImportError:
    pyvips = None  # type: ignore[assignment]

from config import (
    UPLOAD_DIR,
    CONTENT_TYPE_EXTENSIONS,
    MAX_FILE_SIZE,
    DEFAULT_FILE_EXTENSION,
    MAX_FILENAME_LENGTH,
    ALLOWED_FILE_EXTENSIONS,
    JPG_CONVERT_SETTINGS,
    THUMBNAILS,
    DEFAULT_FILENAME,
    USER_DIR_PREFIX,
    ORIGINAL_FILE_SUFFIX,
    CROP_FILE_SUFFIX,
    JPG_EXTENSION,
    RANDOM_SUFFIX_LENGTH,
    UNDERSCORE_LENGTH,
    DEFAULT_DPI,
    INCHES_TO_CM,
    MM_PER_INCH,
    THUMBNAIL_QUALITY,
    DNG_EXTENSIONS,
    DNG_ACCESS_MODE,
    COLOR_SPACE_SRGB,
    COLOR_TYPE_TRUECOLOR,
    BIT_DEPTH_8,
    IMAGE_FORMAT_UCHAR,
    LONG_SIDE_HORIZONTAL,
    LONG_SIDE_VERTICAL,
    LONG_SIDE_EQUAL
)
from logger_config import get_logger

# Mode 0o777: rwx for owner, group, others (Unix). On Windows, chmod is limited but safe to call.
PUBLIC_FILE_MODE = 0o777


class ImageProcessor:
    """
    Class for processing and saving uploaded images.
    
    Provides functionality for validating, processing, and saving image files
    with support for user-specific directories and configurable settings.
    """ 
    def __init__(
        self,
        upload_dir: Path = UPLOAD_DIR,
        content_type_extensions: Optional[Dict[str, str]] = None,
        max_file_size: Optional[int] = MAX_FILE_SIZE
    ):
        """
        Initialize ImageProcessor with configuration.
        
        Args:
            upload_dir: Base directory for storing uploaded images
            content_type_extensions: Mapping of content types to file extensions
            max_file_size: Maximum file size in bytes (None for no limit)
        """
        self.upload_dir = Path(upload_dir)
        self.content_type_extensions = (
            content_type_extensions or CONTENT_TYPE_EXTENSIONS
        )
        self.max_file_size = max_file_size
        self.logger = get_logger(__name__)

    def _ensure_file_accessible(self, file_path: Path) -> None:
        """
        Set file permissions so that other processes (e.g. PHP monolith) can read/write.
        On Unix sets 0o777 (rwxrwxrwx); on Windows chmod is limited but safe (clears read-only if set).
        """
        try:
            os.chmod(file_path, PUBLIC_FILE_MODE)
        except OSError as e:
            self.logger.warning("Could not set permissions for %s: %s", file_path, e)
    
    def _apply_jpg_settings(self, image: pyvips.Image) -> pyvips.Image:
        """
        Apply JPG conversion settings to image.
        
        Args:
            image: pyvips Image object
            
        Returns:
            Processed pyvips Image object with applied settings
        """
        processed_image = image
        
        # Convert color space to sRGB
        color_space = JPG_CONVERT_SETTINGS.get('color_space', COLOR_SPACE_SRGB)
        if color_space.lower() == COLOR_SPACE_SRGB:
            # Convert to sRGB color space
            try:
                # Check current interpretation
                current_interpretation = processed_image.interpretation
                if current_interpretation != 'srgb':
                    # Convert to sRGB color space
                    processed_image = processed_image.colourspace('srgb')
            except Exception:
                # If conversion fails, continue with original image
                pass
        
        # Remove alpha channel if present (for truecolor)
        color_type = JPG_CONVERT_SETTINGS.get('color_type', COLOR_TYPE_TRUECOLOR)
        if color_type == COLOR_TYPE_TRUECOLOR:
            # Flatten image to remove alpha channel
            try:
                if processed_image.has_alpha():
                    processed_image = processed_image.flatten()
            except Exception:
                # If flattening fails, continue
                pass
        
        # Set bit depth to 8
        depth = JPG_CONVERT_SETTINGS.get('depth', BIT_DEPTH_8)
        if depth == BIT_DEPTH_8:
            # Cast to 8-bit unsigned char
            try:
                if processed_image.format != IMAGE_FORMAT_UCHAR:
                    processed_image = processed_image.cast(IMAGE_FORMAT_UCHAR)
            except Exception:
                # If casting fails, continue
                pass
        
        return processed_image
    
    def create_thumbnail(
        self,
        source_image_path: Path,
        thumbnail_path: Path,
        longest_edge: int,
        shortest_edge: int
    ) -> None:
        """
        Create a thumbnail from source image that fits within specified rectangle.
        
        The thumbnail will be scaled proportionally to fit within a rectangle
        defined by longest_edge and shortest_edge, similar to ImageMagick -resize command.
        The image will be scaled so that:
        - The entire image fits within the rectangle
        - Aspect ratio is preserved
        - Neither width nor height exceeds the specified longest_edge and shortest_edge
        
        Args:
            source_image_path: Path to source image file
            thumbnail_path: Path where thumbnail should be saved
            longest_edge: Maximum length for the longest edge of the thumbnail
            shortest_edge: Maximum length for the shortest edge of the thumbnail
            
        Raises:
            Exception: If thumbnail creation fails
        """
        try:
            # Load source image
            image = pyvips.Image.new_from_file(str(source_image_path))
            
            # Get current dimensions
            width = image.width
            height = image.height
            
            # Determine current longest and shortest edges
            current_longest = max(width, height)
            current_shortest = min(width, height)
            
            # Calculate scaling factors for both edges
            # Factor for longest edge constraint
            scale_longest = longest_edge / current_longest if current_longest > 0 else 1.0
            # Factor for shortest edge constraint
            scale_shortest = shortest_edge / current_shortest if current_shortest > 0 else 1.0
            
            # Use minimum scale to ensure both edges fit within limits
            # This ensures the entire image fits within the rectangle
            scale = min(scale_longest, scale_shortest)
            
            # If image is already smaller than target size, scale can be > 1.0
            # But we only want to downscale, so cap at 1.0
            if scale > 1.0:
                scale = 1.0
            
            # Resize image if scaling is needed
            if scale < 1.0:
                # Resize image using scale factor (applies to both axes, preserving aspect ratio)
                resized_image = image.resize(scale)
            else:
                resized_image = image
            
            # Apply JPG settings to ensure consistency
            processed_image = self._apply_jpg_settings(resized_image)
            
            # Save as JPG with 100% quality
            processed_image.write_to_file(str(thumbnail_path), Q=100)
            self._ensure_file_accessible(thumbnail_path)
        except Exception as e:
            self.logger.error(
                "Failed to create thumbnail from %s to %s (longest_edge=%d, shortest_edge=%d): %s",
                source_image_path, thumbnail_path, longest_edge, shortest_edge,
                str(e), exc_info=True
            )
            raise
    
    def _create_secondary_thumbnails(
        self,
        source_path: Path,
        base_name: str,
        user_dir: Path,
        thumbnails_config: list,
        skip_no_crop: bool = False,
    ) -> None:
        """
        Create secondary thumbnails (with main_image=False) from source image.
        
        Args:
            source_path: Path to source image file (main thumbnail or original JPG)
            base_name: Base name for thumbnail filenames (without extension),
                      already includes uniqueness suffix if needed (e.g., "name_1")
            user_dir: User directory where thumbnails should be saved
            thumbnails_config: List of thumbnail configurations from THUMBNAILS
            skip_no_crop: If True, skip thumbnails that have 'no_crop': True (used when creating from cropped image)
        """
        for thumbnail_config in thumbnails_config:
            is_main = thumbnail_config.get('main_image', False)
            if is_main:
                continue
            if skip_no_crop and thumbnail_config.get('no_crop', False):
                continue
            
            prefix = thumbnail_config.get('prefix', '')
            longest_edge = thumbnail_config.get('longest_edge')
            shortest_edge = thumbnail_config.get('shortest_edge')
            
            # Create thumbnail filename with prefix
            # base_name already includes uniqueness suffix, so no need to check again
            thumbnail_filename = f"{base_name}{prefix}{JPG_EXTENSION}"
            thumbnail_path = user_dir / thumbnail_filename
            
            # Create thumbnail from source image
            self.create_thumbnail(
                source_path,
                thumbnail_path,
                longest_edge,
                shortest_edge
            )
    
    def validate_image(self, file: UploadFile) -> None:
        """
        Validates that the uploaded file has allowed extension.
        
        Args:
            file: UploadFile object to validate
            
        Raises:
            HTTPException: If file extension is not allowed
        """
        # Get file extension from filename
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        
        file_ext = Path(file.filename).suffix.lower()
        # Remove leading dot
        if file_ext.startswith('.'):
            file_ext = file_ext[1:]
        
        # Check if extension is allowed
        if file_ext not in ALLOWED_FILE_EXTENSIONS:
            allowed_str = ', '.join(ALLOWED_FILE_EXTENSIONS)
            raise HTTPException(
                status_code=400, 
                detail=f"File extension '{file_ext}' is not allowed. Allowed extensions: {allowed_str}"
            )
  
    def get_file_extension(self, file: UploadFile) -> str:
        """
        Determines file extension from filename or content type.
        
        Args:
            file: UploadFile object
            
        Returns:
            File extension with leading dot (e.g., ".jpg")
        """
        # Try to get extension from filename
        if file.filename:
            file_ext = Path(file.filename).suffix
            if file_ext:
                return file_ext
        
        # Fallback to content type mapping
        if file.content_type:
            return self.content_type_extensions.get(file.content_type, DEFAULT_FILE_EXTENSION)
        
        # Default extension
        return DEFAULT_FILE_EXTENSION
    
    def _get_user_directory(self, user_id: int) -> Path:
        """
        Get or create user-specific directory.
        
        Args:
            user_id: User ID
            
        Returns:
            Path to user directory with format user_id_X
            
        Raises:
            HTTPException: If directory creation fails or directory is not writable
        """
        user_dir = self.upload_dir / f"{USER_DIR_PREFIX}{user_id}"
        
        # Ensure base upload directory exists
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error("Failed to create base upload directory %s: %s", self.upload_dir, e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create base upload directory: {str(e)}"
            ) from e
        
        # Create user directory
        try:
            user_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error("Failed to create user directory %s: %s", user_dir, e)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create user directory: {str(e)}"
            ) from e
        
        # Verify directory exists and is writable
        if not user_dir.exists():
            raise HTTPException(
                status_code=500,
                detail=f"User directory does not exist: {user_dir}"
            )
        
        if not os.access(user_dir, os.W_OK):
            raise HTTPException(
                status_code=500,
                detail=f"User directory is not writable: {user_dir}"
            )
        
        return user_dir
    
    def _get_base_jpg_path(self, user_dir: Path, name: str) -> Path:
        """
        Build path to the operational (base) JPG file in the user directory.
        
        Args:
            user_dir: User directory path
            name: Filename of the JPG (e.g. from attributes["name"])
            
        Returns:
            Path to the base JPG file
        """
        return user_dir / name
    
    def _get_crop_file_path(self, base_jpg_path: Path) -> Path:
        """
        Build path to the crop file from the base JPG path.
        Crop filename is base stem + CROP_FILE_SUFFIX + extension (e.g. image.jpg -> imagecrop.jpg).
        
        Args:
            base_jpg_path: Path to the base JPG file
            
        Returns:
            Path to the crop file
        """
        return base_jpg_path.parent / (
            base_jpg_path.stem + CROP_FILE_SUFFIX + base_jpg_path.suffix
        )
    
    def _load_image_safe(self, path: Path) -> Tuple[Optional["pyvips.Image"], Optional[Path]]:
        """
        Load image from path in a way that works when file is locked by another process.
        Tries direct load first; on failure copies to a temp file via chunked read and loads from temp.
        Caller must unlink the returned temp path when done with the image if it is not None.
        
        Args:
            path: Path to the image file
            
        Returns:
            Tuple of (pyvips.Image or None, temp_path or None)
        """
        if pyvips is None:
            return (None, None)
        try:
            image = pyvips.Image.new_from_file(str(path))
            return (image, None)
        except Exception:
            pass
        chunk_size = 1024 * 1024
        try:
            fd, tmp_name = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
            try:
                with os.fdopen(fd, "wb") as tmp:
                    with open(path, "rb") as f:
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            tmp.write(chunk)
                tmp_path = Path(tmp_name)
                image = pyvips.Image.new_from_file(str(tmp_path))
                return (image, tmp_path)
            except Exception:
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                return (None, None)
        except Exception as e:
            self.logger.debug("_load_image_safe copy to temp failed for %s: %s", path, e)
            return (None, None)
    
    def _save_image_safe(
        self, image: "pyvips.Image", path: Path, quality: int = 100
    ) -> bool:
        """
        Save image to path. Always writes to a temp file in the same directory
        then moves to the target path to avoid issues with the target file being
        locked by another process.
        
        Args:
            image: pyvips Image to save
            path: Destination path
            quality: JPG quality (default 100)
            
        Returns:
            True if save succeeded, False otherwise
        """
        if pyvips is None:
            return False
        self.logger.info("_save_image_safe: start path=%s", path)
        fd = None
        tmp_path = None
        try:
            fd, tmp_name = tempfile.mkstemp(suffix=path.suffix, dir=path.parent)
            os.close(fd)
            fd = None
            tmp_path = Path(tmp_name)
            self.logger.info("_save_image_safe: writing to temp %s", tmp_path)
            image.write_to_file(str(tmp_path), Q=quality)
            self.logger.info("_save_image_safe: write_to_file temp done, moving to %s", path)
            shutil.move(str(tmp_path), str(path))
            tmp_path = None
            self._ensure_file_accessible(path)
            self.logger.info("_save_image_safe: move done")
            return True
        except Exception as e:
            self.logger.warning("_save_image_safe failed: %s", e, exc_info=True)
            if tmp_path is not None and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            return False
    
    def _apply_rotate_to_image(
        self, image: "pyvips.Image", angle_degrees: float
    ) -> "pyvips.Image":
        """
        Rotate image by given angle (degrees). Analogous to ImageMagick -rotate.
        If angle is 0, returns the same image.
        
        Args:
            image: pyvips Image
            angle_degrees: Rotation angle in degrees
            
        Returns:
            Rotated image
        """
        angle = float(angle_degrees)
        if angle == 0:
            return image
        return image.rotate(angle)
    
    def _apply_extent_crop_to_image(
        self,
        image: "pyvips.Image",
        crop_width: int,
        crop_height: int,
        offset_x: float,
        offset_y: float,
    ) -> "pyvips.Image":
        """
        Crop image with offset. Analogous to ImageMagick -gravity Center -extent WxH+X+Y.
        Extracts region of size (crop_width, crop_height) at top-left (offset_x, offset_y).
        Out-of-image areas are filled with zero. If all parameters are 0, returns the same image.
        
        Args:
            image: pyvips Image
            crop_width: Width of crop region
            crop_height: Height of crop region
            offset_x: Left position of crop region
            offset_y: Top position of crop region
            
        Returns:
            Cropped image
        """
        cw, ch = int(crop_width), int(crop_height)
        ox, oy = int(offset_x), int(offset_y)
        if cw == 0 and ch == 0 and ox == 0 and oy == 0:
            return image
        self.logger.info("_apply_extent_crop_to_image: calling image.crop(ox=%s oy=%s cw=%s ch=%s)", ox, oy, cw, ch)
        cropped = image.crop(ox, oy, cw, ch)
        self.logger.info("_apply_extent_crop_to_image: image.crop() returned, size %sx%s", cropped.width, cropped.height)
        return cropped
    
    def _transliterate(self, text: str) -> str:
        """
        Transliterate Cyrillic characters to Latin.
        
        Args:
            text: Text containing Cyrillic characters
            
        Returns:
            Text with Cyrillic characters replaced by Latin equivalents
        """
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
            'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
            'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
            'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
            'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E',
            'Ё': 'Yo', 'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K',
            'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R',
            'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'Ts',
            'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch', 'Ъ': '', 'Ы': 'Y', 'Ь': '',
            'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
        }
        
        result = []
        for char in text:
            result.append(translit_map.get(char, char))
        return ''.join(result)
    
    def _generate_unique_filename(
        self,
        original_filename: Optional[str],
        file_ext: str,
        user_dir: Path
    ) -> str:
        """
        Generate unique filename based on original filename.
        
        Steps:
        1. Transliterate Cyrillic characters to Latin
        2. Remove all characters except Latin letters, digits, and underscores
        3. Truncate to maximum configured length
        4. Add random 5-character sequence (letters and digits) to increase uniqueness
        5. Check uniqueness and add numeric suffix _1, _2, etc. if needed
        
        Args:
            original_filename: Original filename (can be None)
            file_ext: File extension with leading dot
            user_dir: User directory to check for existing files
            
        Returns:
            Unique filename
        """
        # Convert file extension to lowercase
        file_ext = file_ext.lower()
        
        # If no original filename, use default name
        if not original_filename:
            base_name = DEFAULT_FILENAME
        else:
            # Get base name without extension
            base_name = Path(original_filename).stem
            
            # Step 1: Transliterate Cyrillic to Latin
            base_name = self._transliterate(base_name)
            
            # Step 2: Remove all characters except Latin letters, digits, and underscores
            base_name = re.sub(r'[^a-zA-Z0-9_]', '', base_name)
            
            # If base_name is empty after cleaning, use default
            if not base_name:
                base_name = DEFAULT_FILENAME
        
        # Convert base_name to lowercase
        base_name = base_name.lower()
        
        # Step 3: Truncate to maximum configured length (base name only)
        max_length = MAX_FILENAME_LENGTH
        
        # Generate random character sequence (letters and digits)
        random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=RANDOM_SUFFIX_LENGTH))
        
        # Adjust base_name length to accommodate random suffix with underscore separator
        # Total length of base_name + underscore + random suffix should not exceed max_length
        available_length = max_length - RANDOM_SUFFIX_LENGTH - UNDERSCORE_LENGTH
        base_name_truncated = base_name[:available_length] if len(base_name) > available_length else base_name
        
        # Step 4: Check uniqueness and add suffix if needed
        # Start with base_name + underscore + random suffix
        filename = f"{base_name_truncated}_{random_chars}{file_ext}"
        file_path = user_dir / filename
        
        counter = 1
        while file_path.exists():
            # Generate new name with numeric suffix
            # Already have random_chars with underscore, so add numeric suffix after it
            suffix = f"_{counter}"
            # Adjust base_name length to accommodate underscore, random_chars and numeric suffix
            # Total length of base_name + underscore + random_chars + suffix should not exceed max_length
            available_length = max_length - RANDOM_SUFFIX_LENGTH - UNDERSCORE_LENGTH - len(suffix)
            base_name_truncated = base_name[:available_length] if len(base_name) > available_length else base_name
            
            filename = f"{base_name_truncated}_{random_chars}{suffix}{file_ext}"
            file_path = user_dir / filename
            counter += 1
        
        return filename
    
    def _generate_original_filename(
        self,
        unique_filename: str,
        user_dir: Path
    ) -> Tuple[str, Path]:
        """
        Generate unique filename for original file with _orig prefix.
        
        Args:
            unique_filename: Unique filename generated by _generate_unique_filename
            user_dir: User directory to check for existing files
            
        Returns:
            Tuple of (original_filename, original_file_path)
        """
        # Create original filename with _orig prefix
        base_name = Path(unique_filename).stem
        original_ext = Path(unique_filename).suffix
        original_filename = f"{base_name}{ORIGINAL_FILE_SUFFIX}{original_ext}"
        original_file_path = user_dir / original_filename
        
        # Check uniqueness of original filename
        counter = 1
        while original_file_path.exists():
            original_filename = f"{base_name}{ORIGINAL_FILE_SUFFIX}_{counter}{original_ext}"
            original_file_path = user_dir / original_filename
            counter += 1
        
        return original_filename, original_file_path
    
    def _create_all_thumbnails(
        self,
        jpg_file_path: Path,
        base_name: str,
        user_dir: Path,
        skip_no_crop: bool = False,
    ) -> None:
        """
        Create all thumbnails. Source image = jpg_file_path; destination paths = user_dir / (base_name + prefix + .jpg).
        
        When creating from a cropped file, pass the crop file as jpg_file_path and the base JPG stem as base_name.
        Use skip_no_crop=False so all thumbnails (including no_crop sizes) are built from the cropped image.
        
        First creates thumbnails with main_image=True from jpg_file_path, then secondary (main_image=False)
        from the first main thumbnail or from jpg_file_path if none.
        
        Args:
            jpg_file_path: Path to the source image (main JPG or cropped file)
            base_name: Base name for thumbnail filenames (without extension); use base JPG stem for normal paths
            user_dir: User directory where thumbnails are saved
            skip_no_crop: If True, skip thumbnails with no_crop=True (use when source is cropped image)
        """
        try:
            main_thumbnail_path = None
            
            # First pass: create all thumbnails with main_image=True from original JPG
            for thumbnail_config in THUMBNAILS:
                is_main = thumbnail_config.get('main_image', False)
                if not is_main:
                    continue
                if skip_no_crop and thumbnail_config.get('no_crop', False):
                    continue
                
                prefix = thumbnail_config.get('prefix', '')
                longest_edge = thumbnail_config.get('longest_edge')
                shortest_edge = thumbnail_config.get('shortest_edge')
                
                # Create thumbnail filename with prefix
                # base_name already includes uniqueness suffix, so no need to check again
                thumbnail_filename = f"{base_name}{prefix}{JPG_EXTENSION}"
                thumbnail_path = user_dir / thumbnail_filename
                
                # Create main thumbnail from original JPG
                self.create_thumbnail(
                    jpg_file_path,
                    thumbnail_path,
                    longest_edge,
                    shortest_edge
                )
                
                # Store first main thumbnail path to use as source for other thumbnails
                if main_thumbnail_path is None:
                    main_thumbnail_path = thumbnail_path
            
            # Second pass: create all other thumbnails from main thumbnail
            # If skip_no_crop is True, keep using the original source file for consistency.
            # Otherwise, use the first main thumbnail (if created) as an optimized source.
            if skip_no_crop:
                source_path = jpg_file_path
            else:
                source_path = main_thumbnail_path if main_thumbnail_path else jpg_file_path
            
            # Create secondary thumbnails (with main_image=False)
            self._create_secondary_thumbnails(
                source_path,
                base_name,
                user_dir,
                THUMBNAILS,
                skip_no_crop=skip_no_crop,
            )
        except Exception as e:
            # Log error but don't fail the entire operation if thumbnail creation fails
            # Continue with returning success response for main image
            self.logger.error(
                "Failed to create thumbnails for %s: %s",
                jpg_file_path, str(e), exc_info=True
            )

    def _get_thumbnail_paths(self, base_name: str, user_dir: Path) -> List[Path]:
        """
        Get paths to all thumbnail files for a given base name according to THUMBNAILS config.

        Args:
            base_name: Base name for thumbnail filenames (without extension)
            user_dir: User directory where thumbnails are stored

        Returns:
            List of Path objects for all thumbnail files
        """
        paths = []
        for thumbnail_config in THUMBNAILS:
            prefix = thumbnail_config.get('prefix', '')
            thumbnail_filename = f"{base_name}{prefix}{JPG_EXTENSION}"
            paths.append(user_dir / thumbnail_filename)
        return paths

    def delete_product_preview(
        self,
        user_id: int,
        product_preview_name: str
    ) -> None:
        """
        Delete the product preview file in the user's directory if it exists.

        Args:
            user_id: User ID
            product_preview_name: Name of the product preview file

        Raises:
            HTTPException: If user directory cannot be obtained (from _get_user_directory)
        """
        if not product_preview_name or not product_preview_name.strip():
            return
        user_dir = self._get_user_directory(user_id)
        product_preview_path = user_dir / product_preview_name.strip()
        if product_preview_path.exists() and product_preview_path.is_file():
            self._delete_file_with_retry(product_preview_path)

    def _delete_file_with_retry(
        self,
        file_path: Path,
        max_attempts: int = 10,
        initial_delay: float = 0.5,
        backoff_factor: float = 1.5
    ) -> None:
        """
        Delete a file with retries when it is locked by another process.
        Waits between attempts so the holding process can release the file.

        Args:
            file_path: Path to the file to delete.
            max_attempts: Maximum number of delete attempts (default 10).
            initial_delay: Delay in seconds before first retry (default 0.5).
            backoff_factor: Multiplier for delay after each failed attempt (default 1.5).
        """
        delay = initial_delay
        last_error = None
        for attempt in range(max_attempts):
            try:
                file_path.unlink()
                self.logger.info("Deleted file: %s", file_path)
                return
            except OSError as e:
                last_error = e
                if attempt < max_attempts - 1:
                    self.logger.debug(
                        "File in use, retry %s/%s after %.1fs: %s",
                        attempt + 1, max_attempts, delay, file_path
                    )
                    time.sleep(delay)
                    delay *= backoff_factor
        self.logger.warning(
            "Failed to delete file after %s attempts: %s (last error: %s)",
            max_attempts, file_path, last_error
        )

    def delete_image_with_preview(
        self,
        source_image_name: str,
        user_id: int,
        product_preview_name: str = ""
    ) -> None:
        """
        Delete the image and all its previews (base JPG, original file, thumbnails, optional product preview).

        Args:
            source_image_name: Name of the source image with extension (required)
            user_id: User ID (required)
            product_preview_name: Name of the product preview file (default empty string)

        Raises:
            ValueError: If source_image_name or user_id is missing
            HTTPException: If user directory cannot be obtained (from _get_user_directory)
        """
        if source_image_name is None or (isinstance(source_image_name, str) and source_image_name.strip() == ""):
            raise ValueError("Source image name is required")
        if user_id is None:
            raise ValueError("User ID is required")

        user_dir = self._get_user_directory(user_id)

        # Base JPG name: replace extension with .jpg if not already jpg
        source_path = Path(source_image_name)
        if source_path.suffix.lower() != JPG_EXTENSION:
            jpg_name = source_path.stem + JPG_EXTENSION
        else:
            jpg_name = source_image_name
        jpg_path = user_dir / jpg_name

        # Original name: source_image_name with original prefix from settings before extension (e.g. image.jpg -> image_orig.jpg)
        source_path = Path(source_image_name)
        original_filename = f"{source_path.stem}{ORIGINAL_FILE_SUFFIX}{source_path.suffix}"
        original_path = user_dir / original_filename

        # Paths to all thumbnails (using existing method)
        jpg_base_name = Path(jpg_name).stem
        thumbnail_paths = self._get_thumbnail_paths(jpg_base_name, user_dir)

        files_to_delete = [jpg_path, original_path] + thumbnail_paths


        # First pass: try to delete each file once; collect failures for retry
        files_to_retry = []
        for file_path in files_to_delete:
            if file_path.exists() and file_path.is_file():
                try:
                    file_path.unlink()
                    self.logger.info("Deleted file: %s", file_path)
                except OSError:
                    files_to_retry.append(file_path)

        # Second pass: retry locked files with backoff (does not block deletion of others)
        for file_path in files_to_retry:
            self._delete_file_with_retry(file_path)

        if product_preview_name and product_preview_name.strip() != "":
            self.delete_product_preview(user_id, product_preview_name)

    async def save(
        self,
        file: UploadFile,
        user_id: int
    ) -> dict:
        """
        Saves uploaded image to the specified directory.
        Creates original file with _orig prefix and JPG copy with original name.
        
        Args:
            file: UploadFile object containing the image
            user_id: User ID to organize files in subdirectories
            
        Returns:
            Dictionary with information about saved file:
            - filename: Original filename
            - saved_filename: Generated unique filename (JPG copy)
            - original_filename: Original file with _orig prefix
            - content_type: File content type
            - userID: User ID
            - file_path: Full path to saved JPG file
            - original_file_path: Full path to saved original file
            - message: Success message
            
        Raises:
            HTTPException: If file validation or saving fails
        """
        # Validate that file is an image
        self.validate_image(file)

        # Get user directory
        user_dir = self._get_user_directory(user_id)
        
        # Get file extension
        file_ext = self.get_file_extension(file)
        
        # Generate unique filename for original (will add _orig prefix)
        unique_filename = self._generate_unique_filename(
            file.filename,
            file_ext,
            user_dir
        )
        
        # Generate original filename with _orig prefix
        original_filename, original_file_path = self._generate_original_filename(
            unique_filename,
            user_dir
        )
        
        # Extract base name from unique filename for JPG filename
        base_name = Path(unique_filename).stem
        
        # Generate unique JPG filename
        jpg_filename, jpg_file_path = self._generate_jpg_filename(base_name, user_dir)
        
        # Save original file
        await self._save_original_file(file, original_file_path)
        
        # Convert to JPG and resize if needed
        self._convert_to_jpg(original_file_path, jpg_file_path, file_ext)
        
        # Create thumbnails
        jpg_base_name = Path(jpg_filename).stem
        self._create_all_thumbnails(jpg_file_path, jpg_base_name, user_dir)
        
        # Extract metadata and prepare response
        metadata = self._extract_image_metadata(jpg_file_path, original_filename, file_ext)
        
        return {
            "user_id": user_id,
            "name": jpg_filename,
            "orig_name": metadata["orig_name"],
            "width": metadata["width"],
            "height": metadata["height"],
            "width_sm": metadata["width_sm"],
            "height_sm": metadata["height_sm"],
            "format": metadata["format"],
            "long_side": metadata["long_side"],
            "factor": metadata["factor"],
            "resolution": metadata["resolution"]
        }
    
    def save_from_path(
        self,
        file_path: Path,
        user_id: int
    ) -> dict:
        """
        Saves image file from filesystem path to the specified directory.
        Creates original file with _orig prefix and JPG copy with original name.
        Uses the same processing logic as save() method.
        
        Args:
            file_path: Path to the image file on filesystem
            user_id: User ID to organize files in subdirectories
            
        Returns:
            Dictionary with information about saved file (same format as save())
            
        Raises:
            HTTPException: If file validation or saving fails
        """
        # Validate file exists and is a file
        file_path = Path(file_path)
        if not file_path.exists():
            raise HTTPException(status_code=400, detail=f"File not found: {file_path}")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")
        
        # Validate file extension
        file_ext = file_path.suffix.lower()
        if not file_ext:
            raise HTTPException(status_code=400, detail="File has no extension")
        
        # Check if extension is allowed
        file_ext_no_dot = file_ext.lstrip('.')
        if file_ext_no_dot not in ALLOWED_FILE_EXTENSIONS:
            allowed_str = ', '.join(ALLOWED_FILE_EXTENSIONS)
            raise HTTPException(
                status_code=400, 
                detail=f"File extension '{file_ext_no_dot}' is not allowed. Allowed extensions: {allowed_str}"
            )
        
        # Get user directory
        user_dir = self._get_user_directory(user_id)
        
        # Get original filename from path
        original_filename = file_path.name
        
        # Generate unique filename for original (will add _orig prefix)
        unique_filename = self._generate_unique_filename(
            original_filename,
            file_ext,
            user_dir
        )
        
        # Generate original filename with _orig prefix
        orig_filename, original_file_path = self._generate_original_filename(
            unique_filename,
            user_dir
        )
        
        # Copy file to user directory with original filename
        self._copy_file_to_path(file_path, original_file_path)
        
        # Extract base name from unique filename for JPG filename
        base_name = Path(unique_filename).stem
        
        # Generate unique JPG filename
        jpg_filename, jpg_file_path = self._generate_jpg_filename(base_name, user_dir)
        
        # Convert to JPG and resize if needed
        self._convert_to_jpg(original_file_path, jpg_file_path, file_ext)
        
        # Create thumbnails
        jpg_base_name = Path(jpg_filename).stem
        self._create_all_thumbnails(jpg_file_path, jpg_base_name, user_dir)
        
        # Extract metadata and prepare response
        metadata = self._extract_image_metadata(jpg_file_path, orig_filename, file_ext)
        
        return {
            "user_id": user_id,
            "name": jpg_filename,
            "orig_name": metadata["orig_name"],
            "width": metadata["width"],
            "height": metadata["height"],
            "width_sm": metadata["width_sm"],
            "height_sm": metadata["height_sm"],
            "format": metadata["format"],
            "long_side": metadata["long_side"],
            "factor": metadata["factor"],
            "resolution": metadata["resolution"]
        }
    
    def edit_image(
        self,
        attributes: Dict,
        was_cropped: bool = True,
    ) -> Dict:
        """
        Edit image: copy base JPG to crop file, apply rotation and extent crop, then regenerate thumbnails.
        Used for cropping and for resetting crop (was_cropped=False).
        
        Args:
            attributes: Dict with image metadata (id, user_id, name, angel, croped_width_px,
                       croped_height_px, offset_x, offset_y, etc.)
            was_cropped: Value to set in attributes["was_cropped"] (default True; use False when resetting crop)
            
        Returns:
            Dict with keys: success (bool), errors (list), attrs (attributes with was_cropped set), method ('cropx')
        """
        attrs = dict(attributes)
        attrs["was_cropped"] = 1 if was_cropped else 0
        self.edit_attributes = attrs
        self.logger.info("edit_image() start: user_id=%s, name=%s", attrs.get("user_id"), attrs.get("name"))

        result = {
            "success": True,
            "errors": [],
            "attrs": attrs,
            "method": "cropx",
        }

        user_id = attrs.get("user_id")
        if user_id is None:
            result["errors"].append("user_id is required")
            result["success"] = False
            return result
        
        try:
            user_dir = self._get_user_directory(user_id)
            self.logger.info("edit_image() user_dir ok: %s", user_dir)
        except HTTPException as e:
            msg = "User directory unavailable: %s" % (e.detail or str(e))
            self.logger.error(msg)
            result["errors"].append(msg)
            result["success"] = False
            return result
        name = attrs.get("name") or ""
        if not name:
            result["errors"].append("name is required")
            result["success"] = False
            return result
        
        base_jpg_path = self._get_base_jpg_path(user_dir, name)
        if not base_jpg_path.exists() or not base_jpg_path.is_file():
            msg = "Base JPG file not found or not accessible: %s" % base_jpg_path
            self.logger.error(msg)
            result["errors"].append(msg)
            result["success"] = False
            return result
        self.logger.info("edit_image() base_jpg_path exists: %s", base_jpg_path)

        crop_path = self._get_crop_file_path(base_jpg_path)
        self.logger.info("edit_image() copying base to crop: %s -> %s", base_jpg_path, crop_path)
        if not self.file_copy(base_jpg_path, crop_path):
            msg = "Failed to copy base JPG to crop file: %s -> %s" % (base_jpg_path, crop_path)
            self.logger.error(msg)
            result["errors"].append(msg)
            result["success"] = False
            return result
        self.logger.info("edit_image() file_copy done")

        image, load_temp_path = self._load_image_safe(crop_path)
        if image is None:
            msg = "Failed to open crop file for editing: %s" % crop_path
            self.logger.error(msg)
            result["errors"].append(msg)
            result["success"] = False
            return result
        self.logger.info("edit_image() image loaded (pyvips), size %sx%s", image.width, image.height)

        try:
            quality = JPG_CONVERT_SETTINGS.get('quality', 100)

            # Stage 1: rotate
            angel = attrs.get("angel", 0)
            try:
                angle_val = float(angel) if angel is not None else 0.0
            except (TypeError, ValueError):
                angle_val = 0.0
            if angle_val != 0:
                self.logger.info("edit_image() applying rotate: angle=%s", angle_val)
                try:
                    image = self._apply_rotate_to_image(image, angle_val)
                    if not self._save_image_safe(image, crop_path, quality=quality):
                        result["errors"].append("Failed to save crop file after rotate")
                        result["success"] = False
                        return result
                    self.logger.info("edit_image() rotate done and saved")
                except Exception as e:
                    self.logger.error("Rotate failed for %s: %s", crop_path, e, exc_info=True)
                    result["errors"].append("Rotate failed: %s" % str(e))
                    result["success"] = False
                    return result
            else:
                self.logger.info("edit_image() rotate skipped (angle=0)")

            # Stage 2: extent crop (shift and crop)
            cw = attrs.get("croped_width_px", 0) or 0
            ch = attrs.get("croped_height_px", 0) or 0
            ox = attrs.get("offset_x", 0) or 0
            oy = attrs.get("offset_y", 0) or 0
            if cw != 0 or ch != 0 or ox != 0 or oy != 0:
                self.logger.info("edit_image() applying extent crop: cw=%s ch=%s ox=%s oy=%s", cw, ch, ox, oy)
                try:
                    image = self._apply_extent_crop_to_image(image, cw, ch, ox, oy)
                    self.logger.info("edit_image() extent crop applied, calling _save_image_safe")
                    if not self._save_image_safe(image, crop_path, quality=quality):
                        result["errors"].append("Failed to save crop file after extent crop")
                        result["success"] = False
                        return result
                    self.logger.info("edit_image() extent crop done and saved")
                except Exception as e:
                    self.logger.error("Extent crop failed for %s: %s", crop_path, e, exc_info=True)
                    result["errors"].append("Extent crop failed: %s" % str(e))
                    result["success"] = False
                    return result
            else:
                self.logger.info("edit_image() extent crop skipped (no crop params)")

            # Recreate previews from cropped file so all sizes (including no_crop) match the crop.
            base_name_for_previews = Path(name).stem  # base JPG name, not crop filename
            self.logger.info(
                "edit_image() creating thumbnails: source=%s, base_name=%s (paths like %s)",
                crop_path, base_name_for_previews, f"{base_name_for_previews}<prefix>.jpg",
            )
            try:
                self._create_all_thumbnails(
                    crop_path,
                    base_name_for_previews,
                    user_dir,
                    skip_no_crop=True,
                )
            except Exception as e:
                self.logger.error(
                    "Failed to create thumbnails from crop for %s: %s",
                    crop_path, str(e), exc_info=True
                )
                result["errors"].append("Thumbnails failed: %s" % str(e))
                result["success"] = False
                return result
            self.logger.info("edit_image() thumbnails done")
        finally:
            if load_temp_path is not None and load_temp_path.exists():
                try:
                    load_temp_path.unlink()
                except OSError:
                    pass
        self.logger.info("edit_image() returning success")
        return result

    def drop_edit_image(self, attributes: Dict) -> Dict:
        """
        Drop all previously applied edit/crop changes for an image.

        Accepts attributes as dict or as JSON string; normalizes and updates fields to defaults,
        regenerates thumbnails from base JPG and removes crop file if it exists.

        Returns:
            Dict with keys: success (bool), errors (list), attrs (dict), method ('cropx')
        """
        result = {
            "success": True,
            "errors": [],
            "attrs": attributes,
            "method": "cropx",
        }

        attrs = attributes
        try:
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except json.JSONDecodeError as e:
                    msg = f"Failed to parse attributes JSON: {e}"
                    self.logger.error(msg, exc_info=True)
                    result["errors"].append(msg)
                    result["success"] = False
                    return result
            if not isinstance(attrs, dict):
                msg = f"Attributes must be a dict, got {type(attrs).__name__}"
                self.logger.error(msg)
                result["errors"].append(msg)
                result["success"] = False
                return result
        except Exception as e:
            msg = f"Unexpected error while normalizing attributes: {e}"
            self.logger.error(msg, exc_info=True)
            result["errors"].append(msg)
            result["success"] = False
            return result

        # Save as class-level attributes variable (reusing existing one)
        self.edit_attributes = attrs
        result["attrs"] = attrs

        user_id = attrs.get("user_id")
        if user_id is None:
            result["errors"].append("user_id is required")
            result["success"] = False
            return result

        name = attrs.get("name") or ""
        if not name:
            result["errors"].append("name is required")
            result["success"] = False
            return result

        # Reset edit-related fields
        attrs["croped_width_px"] = attrs.get("width")
        attrs["croped_height_px"] = attrs.get("height")
        attrs["angel"] = 0
        attrs["offset_x"] = 0
        attrs["offset_y"] = 0
        attrs["result_resolution"] = attrs.get("resolution")
        attrs["text_exists"] = 0
        attrs["text_str"] = ""
        attrs["text_x"] = 0
        attrs["text_y"] = 0
        attrs["text_w"] = 0
        attrs["text_size"] = 0
        attrs["text_color"] = None
        attrs["text_font"] = None
        attrs["text_align"] = None
        attrs["was_cropped"] = 0

        try:
            user_dir = self._get_user_directory(user_id)
        except HTTPException as e:
            msg = "User directory unavailable: %s" % (e.detail or str(e))
            self.logger.error(msg)
            result["errors"].append(msg)
            result["success"] = False
            return result

        base_jpg_path = self._get_base_jpg_path(user_dir, name)
        if not base_jpg_path.exists() or not base_jpg_path.is_file():
            msg = "Base JPG file not found or not accessible: %s" % base_jpg_path
            self.logger.error(msg)
            result["errors"].append(msg)
            result["success"] = False
            return result

        # Recreate all thumbnails from base JPG (all sizes so they match uncropped image)
        base_name = Path(name).stem
        try:
            self._create_all_thumbnails(
                base_jpg_path,
                base_name,
                user_dir,
                skip_no_crop=False,
            )
        except Exception as e:
            msg = "Failed to create thumbnails from base JPG %s: %s" % (base_jpg_path, str(e))
            self.logger.error(msg, exc_info=True)
            result["errors"].append(msg)
            result["success"] = False
            return result

        # Remove cropped file if it exists (suffix "crop" before extension, without underscore)
        crop_path = self._get_crop_file_path(base_jpg_path)
        if crop_path.exists() and crop_path.is_file():
            try:
                self._delete_file_with_retry(crop_path)
            except Exception as e:
                msg = "Failed to delete crop file %s: %s" % (crop_path, str(e))
                self.logger.error(msg, exc_info=True)
                result["errors"].append(msg)
                result["success"] = False
                return result
        return result
    
    def _copy_file_to_path(self, source_path: Path, destination_path: Path) -> None:
        """
        Copy file from source path to destination path.
        
        Args:
            source_path: Path to source file
            destination_path: Path where file should be copied
            
        Raises:
            HTTPException: If file copying fails
        """
        try:
            shutil.copy2(source_path, destination_path)
            self._ensure_file_accessible(destination_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to copy file: {str(e)}") from e

    def file_copy(
        self,
        from_path: Path,
        to_path: Path,
    ) -> bool:
        """
        Safely copy a file from source to destination with integrity verification.

        Uses read-byte stream copy to work around source file being locked by
        another process (when shared read is allowed). After each copy attempt,
        MD5 hashes of source and destination are compared; on mismatch the copy
        is retried. Up to five attempts are made. If verification fails after
        all attempts, the situation is logged and the method returns False.

        Args:
            from_path: Path to the source file.
            to_path: Path to the destination file.

        Returns:
            True if the file was copied and MD5 verification passed,
            False if all five attempts failed or verification never succeeded.
        """
        # Normalize to POSIX-style paths (forward slashes) for Linux container
        from_path = Path(str(from_path).strip().replace("\\", "/"))
        to_path = Path(str(to_path).strip().replace("\\", "/"))
        max_attempts = 5
        chunk_size = 1024 * 1024  # 1 MiB
        retry_delay_seconds = 0.5

        def _compute_md5(path: Path) -> str:
            hasher = hashlib.md5()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()

        for attempt in range(1, max_attempts + 1):
            try:
                to_path.parent.mkdir(parents=True, exist_ok=True)
                # Copy by reading/writing in chunks (helps when source is locked
                # by another process with shared read allowed). Compute source
                # MD5 during the same read pass to avoid reopening a locked file.
                with open(from_path, "rb") as src:
                    source_hasher = hashlib.md5()
                    with tempfile.NamedTemporaryFile(
                        dir=to_path.parent,
                        delete=False,
                        prefix=".filecopy_",
                        suffix=to_path.suffix or "",
                    ) as tmp:
                        tmp_path = Path(tmp.name)
                    try:
                        with open(tmp_path, "wb") as dst:
                            while True:
                                chunk = src.read(chunk_size)
                                if not chunk:
                                    break
                                source_hasher.update(chunk)
                                dst.write(chunk)
                        # Replace destination with temp file
                        shutil.move(str(tmp_path), str(to_path))
                        self._ensure_file_accessible(to_path)
                    except Exception:
                        if tmp_path.exists():
                            try:
                                tmp_path.unlink()
                            except OSError:
                                pass
                        raise
                source_md5 = source_hasher.hexdigest()
                dest_md5 = _compute_md5(to_path)
                if source_md5 == dest_md5:
                    return True
                # Verification failed, remove bad copy and retry
                try:
                    to_path.unlink()
                except OSError:
                    pass
            except (OSError, IOError) as e:
                self.logger.warning(
                    "file_copy attempt %d/%d failed for %s -> %s: %s",
                    attempt,
                    max_attempts,
                    from_path,
                    to_path,
                    e,
                )
            if attempt < max_attempts:
                time.sleep(retry_delay_seconds)

        self.logger.error(
            "file_copy failed after %d attempts: source=%s, destination=%s",
            max_attempts,
            from_path,
            to_path,
        )
        return False

    def copy_listed_images(self, images_to_copy: List[Dict]) -> Dict:
        """
        Copy base/cropped and original files for a list of images.

        Selection logic:
        - If `wasCropped` is truthy, try `cropped.from -> cropped.to` first.
        - If cropped source is missing or `wasCropped` is falsy, fallback to
          `base.from -> base.to`.
        - Original is always copied via `orig.from -> orig.to`.

        Copy is considered successful for an image only when both base and
        original copies succeed.

        Args:
            images_to_copy: List of image copy descriptors.

        Returns:
            Copy report dictionary with success counters and image ID lists.
        """
        report = {
            "success": True,
            "copied": 0,
            "failed": 0,
            "copied_id_list": [],
            "failed_id_list": [],
        }

        for image_data in images_to_copy:
            image_id = image_data.get("image_id")
            base_data = image_data.get("base", {}) or {}
            cropped_data = image_data.get("cropped", {}) or {}
            orig_data = image_data.get("orig", {}) or {}
            was_cropped = bool(image_data.get("wasCropped"))

            base_from = Path(str(cropped_data.get("from", "")).strip().replace("\\", "/"))
            base_to = Path(str(cropped_data.get("to", "")).strip().replace("\\", "/"))

            if (not was_cropped) or (not base_from.exists()):
                base_from = Path(str(base_data.get("from", "")).strip().replace("\\", "/"))
                base_to = Path(str(base_data.get("to", "")).strip().replace("\\", "/"))

            orig_from = Path(str(orig_data.get("from", "")).strip().replace("\\", "/"))
            orig_to = Path(str(orig_data.get("to", "")).strip().replace("\\", "/"))

            base_copy_result = self.file_copy(base_from, base_to)
            orig_copy_result = self.file_copy(orig_from, orig_to)

            if base_copy_result and orig_copy_result:
                report["copied_id_list"].append(image_id)
            else:
                report["failed_id_list"].append(image_id)

        report["copied"] = len(report["copied_id_list"])
        report["failed"] = len(report["failed_id_list"])
        report["success"] = report["failed"] == 0 and not report["failed_id_list"]

        return report

    def write_copy_report(self, order_folder_path: str, report_json: Dict) -> None:
        """
        Write copy report to order folder as JSON file.

        Args:
            order_folder_path: Path to order folder.
            report_json: Copy report dictionary.
        """
        order_folder = Path(str(order_folder_path).strip().replace("\\", "/"))
        report_file_path = order_folder / "copy_report.json"

        # Ensure the order folder exists before writing the report.
        report_file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_file_path, "w", encoding="utf-8") as report_file:
            json.dump(report_json, report_file, ensure_ascii=False, indent=4)

    def _generate_jpg_filename(self, base_name: str, user_dir: Path) -> Tuple[str, Path]:
        """
        Generate unique JPG filename.
        
        Args:
            base_name: Base name without extension
            user_dir: User directory to check for existing files
            
        Returns:
            Tuple of (jpg_filename, jpg_file_path)
        """
        jpg_filename = f"{base_name}{JPG_EXTENSION}"
        jpg_file_path = user_dir / jpg_filename
        
        # Check uniqueness of JPG filename
        counter = 1
        while jpg_file_path.exists():
            jpg_filename = f"{base_name}_{counter}{JPG_EXTENSION}"
            jpg_file_path = user_dir / jpg_filename
            counter += 1
        
        return jpg_filename, jpg_file_path
    
    async def _save_original_file(self, file: UploadFile, original_file_path: Path) -> None:
        """
        Save original uploaded file to disk.
        
        Args:
            file: UploadFile object containing the image
            original_file_path: Path where original file should be saved
            
        Raises:
            HTTPException: If file reading or saving fails
        """
        # Read file content
        try:
            await file.seek(0)
            content = await file.read()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}") from e
        
        # Save original file
        try:
            async with aiofiles.open(original_file_path, 'wb') as f:
                await f.write(content)
            self._ensure_file_accessible(original_file_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save original file: {str(e)}") from e
    
    def _convert_to_jpg(self, original_file_path: Path, jpg_file_path: Path, file_ext: str) -> None:
        """
        Convert image to JPG format with resizing if needed.
        
        Args:
            original_file_path: Path to original image file
            jpg_file_path: Path where JPG should be saved
            file_ext: Original file extension
            
        Raises:
            HTTPException: If conversion fails
        """
        try:
            # Load image with pyvips
            file_ext_lower = file_ext.lower() if file_ext else ''
            if file_ext_lower in DNG_EXTENSIONS:
                image = pyvips.Image.new_from_file(
                    str(original_file_path),
                    access=DNG_ACCESS_MODE
                )
                image = image.autorot()
            else:
                image = pyvips.Image.new_from_file(str(original_file_path))
                image = image.autorot() 
            
            # Apply JPG conversion settings
            processed_image = self._apply_jpg_settings(image)
            
            # Get quality from settings
            quality = JPG_CONVERT_SETTINGS.get('quality', 100)
            
            # Convert to JPG and save
            processed_image.write_to_file(str(jpg_file_path), Q=quality)
            self._ensure_file_accessible(jpg_file_path)

            # Check and resize JPG if dimensions exceed maximum allowed
            self._resize_jpg_if_needed(jpg_file_path, quality)
            self._ensure_file_accessible(jpg_file_path)
        except Exception as e:
            # If conversion fails, remove original file and raise error
            try:
                original_file_path.unlink()
            except:
                pass
            raise HTTPException(status_code=500, detail=f"Failed to convert image to JPG: {str(e)}") from e
    
    def _resize_jpg_if_needed(self, jpg_file_path: Path, quality: int) -> None:
        """
        Resize JPG image if dimensions exceed maximum allowed.
        
        Args:
            jpg_file_path: Path to JPG file
            quality: JPG quality setting
            
        Raises:
            HTTPException: If resizing fails
        """
        try:
            jpg_image = pyvips.Image.new_from_file(str(jpg_file_path))
            width = jpg_image.width
            height = jpg_image.height
            
            # Determine longest and shortest edges
            longest_edge = max(width, height)
            shortest_edge = min(width, height)
            
            max_longest = JPG_CONVERT_SETTINGS.get('max_longest_edge', 13000)
            max_shortest = JPG_CONVERT_SETTINGS.get('max_shortest_edge', 7000)
            
            self.logger.info(
                "Checking image dimensions: %dx%d (longest=%d, shortest=%d), "
                "max allowed: longest=%d, shortest=%d",
                width, height, longest_edge, shortest_edge, max_longest, max_shortest
            )
            
            # Calculate scaling factors for both edges
            scale_longest = max_longest / longest_edge if longest_edge > max_longest else 1.0
            scale_shortest = max_shortest / shortest_edge if shortest_edge > max_shortest else 1.0
            
            # Use minimum scale to ensure both edges fit within limits
            scale = min(scale_longest, scale_shortest)
            
            # Resize if needed
            if scale < 1.0:
                self.logger.info(
                    "Image exceeds maximum dimensions. Resizing with scale factor: %.4f "
                    "(from %dx%d to approximately %dx%d)",
                    scale, width, height,
                    int(width * scale), int(height * scale)
                )
                resized_image = jpg_image.resize(scale)
                resized_image = self._apply_jpg_settings(resized_image)
                
                # Close the original image to release file handle
                del jpg_image
                
                # Write to temporary file first, then replace original atomically
                temp_file_path = jpg_file_path.with_suffix('.tmp' + jpg_file_path.suffix)
                try:
                    resized_image.write_to_file(str(temp_file_path), Q=quality)
                    # Replace original file atomically
                    temp_file_path.replace(jpg_file_path)
                    self._ensure_file_accessible(jpg_file_path)
                    self.logger.info("Image resized successfully")
                except Exception as write_error:
                    # Clean up temporary file if it exists
                    if temp_file_path.exists():
                        try:
                            temp_file_path.unlink()
                        except:
                            pass
                    raise write_error
            else:
                self.logger.debug("Image dimensions are within limits, no resize needed")
        except Exception as e:
            self.logger.error(
                "Failed to resize image %s: %s",
                jpg_file_path, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to resize image: {str(e)}"
            ) from e
    
    def _extract_image_metadata(
        self,
        jpg_file_path: Path,
        original_filename: str,
        file_ext: str
    ) -> dict:
        """
        Extract metadata from JPG image.
        
        Args:
            jpg_file_path: Path to JPG file
            original_filename: Original filename with _orig suffix
            file_ext: Original file extension
            
        Returns:
            Dictionary with image metadata
        """
        # Initialize default values
        width = 0
        height = 0
        width_sm = 0.0
        height_sm = 0.0
        resolution = DEFAULT_DPI
        long_side = LONG_SIDE_EQUAL
        factor = 1.0
        
        # Get original name without _orig prefix
        if f"{ORIGINAL_FILE_SUFFIX}_" in original_filename:
            orig_name = original_filename.replace(f"{ORIGINAL_FILE_SUFFIX}_", '_')
        else:
            orig_name = original_filename.replace(ORIGINAL_FILE_SUFFIX, '')
        
        # Get format (extension without leading dot)
        format_ext = file_ext.lstrip('.') if file_ext else ''
        
        try:
            final_jpg = pyvips.Image.new_from_file(str(jpg_file_path))
            width = final_jpg.width
            height = final_jpg.height
            
            # Get resolution (DPI) from metadata
            try:
                xres = final_jpg.get("xres")
                yres = final_jpg.get("yres")

                if not xres or xres <= 0:
                    xres = DEFAULT_DPI / MM_PER_INCH
                if not yres or yres <= 0:
                    yres = DEFAULT_DPI / MM_PER_INCH

                dpi_x = xres * MM_PER_INCH
                dpi_y = yres * MM_PER_INCH
                
                resolution = (dpi_x + dpi_y) / 2.0
            except (AttributeError, TypeError, ValueError):
                resolution = DEFAULT_DPI
            
            # Calculate dimensions in centimeters
            width_sm = (width / resolution) * INCHES_TO_CM if resolution > 0 else 0.0
            height_sm = (height / resolution) * INCHES_TO_CM if resolution > 0 else 0.0
            
            # Calculate long_side
            if width > height:
                long_side = LONG_SIDE_HORIZONTAL
            elif height > width:
                long_side = LONG_SIDE_VERTICAL
            else:
                long_side = LONG_SIDE_EQUAL
            
            # Calculate factor: ratio of long side to short side
            longest = max(width, height)
            shortest = min(width, height)
            factor = longest / shortest if shortest > 0 else 1.0
            
        except Exception:
            # If metadata extraction fails, use defaults
            if resolution <= 0:
                resolution = DEFAULT_DPI
        
        return {
            "orig_name": orig_name,
            "width": width,
            "height": height,
            "width_sm": round(width_sm, 2),
            "height_sm": round(height_sm, 2),
            "format": format_ext,
            "long_side": long_side,
            "factor": round(factor, 2),
            "resolution": round(resolution, 2)
        }


# Create default instance for backward compatibility
_default_processor = ImageProcessor()


# Backward compatibility function
async def save_image(file: UploadFile, user_id: int, upload_dir: Path = None) -> dict:
    """
    Backward compatibility function for saving images.
    
    This function is maintained for backward compatibility.
    For new code, use ImageProcessor class directly.
    
    Args:
        file: UploadFile object containing the image
        user_id: User ID to organize files in subdirectories
        upload_dir: Base directory for uploads (optional)
        
    Returns:
        Dictionary with information about saved file
    """
    if upload_dir:
        processor = ImageProcessor(upload_dir=upload_dir)
    else:
        processor = _default_processor
    return await processor.save(file, user_id)
