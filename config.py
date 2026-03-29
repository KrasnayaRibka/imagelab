"""
Configuration file for the application.

Author: Vadim Kalinin
Email: vadimakalinin@gmail.com
"""
import os
from pathlib import Path
from typing import Dict
from hashlib import md5

# Base paths
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
UPLOAD_DIR = Path("/data")
FILES_BASE_DIR = "/data"

# RabbitMQ settings
# Use host.docker.internal to connect from container to host machine
# %2F is URL-encoded forward slash for default virtual host
# Set via environment variable RABBITMQ_URL (see .env.example)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "")
RABBITMQ_EXCHANGE = "imagelab.rpc"
RABBITMQ_ROUTING_KEY = "imagelab.rpc"  # Must match PHP rpc_routing setting
RABBITMQ_QUEUE = "imagelab.rpc.php"  # Queue name that PHP server listens to
# Queue and routing key for image_delete commands consumed by imagelab
RABBITMQ_QUEUE_IMAGE_DELETE = "imagelab.image_delete"
RABBITMQ_ROUTING_KEY_IMAGE_DELETE = "imagelab.image_delete"
# Queue and routing key for image_copy commands consumed by imagelab
RABBITMQ_QUEUE_IMAGE_COPY = "imagelab.image_copy"
RABBITMQ_ROUTING_KEY_IMAGE_COPY = "imagelab.image_copy"
# Queue and routing key for image_edit (RPC) commands consumed by imagelab
RABBITMQ_QUEUE_IMAGE_EDIT = "imagelab.image_edit"
RABBITMQ_ROUTING_KEY_IMAGE_EDIT = "imagelab.image_edit"
# Queue and routing key for copy_result messages produced by imagelab
RABBITMQ_QUEUE_COPY_RESULT = "imagelab.copy_result"
RABBITMQ_ROUTING_KEY_COPY_RESULT = "imagelab.copy_result"

# Content type to file extension mapping
CONTENT_TYPE_EXTENSIONS: Dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp"
}

# Image processing settings
MAX_FILE_SIZE: int = None  # None means no limit (in bytes)
DEFAULT_FILE_EXTENSION: str = ".jpg"
MAX_FILENAME_LENGTH: int = 64  # Maximum length for filename base name (without extension and suffix)
MAX_FILES_COUNT: int = 300  # Maximum number of files that can be uploaded simultaneously
JPG_CONVERT_SETTINGS: dict = {
    'max_longest_edge': 13000,
    'max_shortest_edge': 7000,
    'color_space': 'srgb',
    'color_type': 'truecolor',
    'depth': 8,
    'quality': 100,
}
THUMBNAILS: list = [
        {
            'longest_edge': 800,
            'shortest_edge': 600,
            'no_crop': True,
            'main_image': True,
            'prefix': '800x600',
        },
        {
            'longest_edge': 600,
            'shortest_edge': 452,
            'no_crop': False,
            'main_image': False,
            'prefix': '600x452',
        },
        {
            'longest_edge': 120,
            'shortest_edge': 90,
            'no_crop': False,
            'main_image': False,
            'prefix': '120x90',
        }
]

# Allowed file extensions (without leading dot)
ALLOWED_FILE_EXTENSIONS: list = ['jpg', 'jpeg', 'png', 'gif', 'tif', 'psd', 'zip', 'heic', 'dng', 'zip']

# Image file extensions (with leading dot, lowercase)
IMAGE_EXTENSIONS: list = ['.jpg', '.jpeg', '.png', '.gif', '.tif', '.tiff', '.psd', '.heic', '.dng']

# Archive file extensions (with leading dot, lowercase)
ARCHIVE_EXTENSIONS: list = ['.zip']

# Static files settings
STATIC_DIR = BASE_DIR / "static"
STATIC_URL_PATH = "/static"
STATIC_MOUNT_NAME = "static"

# Logging settings
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 5  # Keep 5 backup files

# Filename generation settings
DEFAULT_FILENAME = "file"  # Default base name when filename is empty
USER_DIR_PREFIX = "user_id_"  # Prefix for user directory names
ORIGINAL_FILE_SUFFIX = "_orig"  # Suffix for original file names
CROP_FILE_SUFFIX = "crop"  # Suffix for crop file names (before extension)
JPG_EXTENSION = ".jpg"  # JPG file extension
RANDOM_SUFFIX_LENGTH = 5  # Length of random suffix for filename uniqueness
UNDERSCORE_LENGTH = 1  # Length of underscore separator

# Image processing constants
DEFAULT_DPI = 300.0  # Default DPI resolution
INCHES_TO_CM = 2.54  # Conversion factor from inches to centimeters
MM_PER_INCH = 25.4  # Millimeters per inch (for DPI conversion)
THUMBNAIL_QUALITY = 100  # Quality for thumbnail images

# Image format settings
DNG_EXTENSIONS = ['.dng', 'dng']  # DNG file extensions
DNG_ACCESS_MODE = 'sequential'  # Access mode for DNG files
COLOR_SPACE_SRGB = 'srgb'  # sRGB color space
COLOR_TYPE_TRUECOLOR = 'truecolor'  # Truecolor color type
BIT_DEPTH_8 = 8  # 8-bit depth
IMAGE_FORMAT_UCHAR = 'uchar'  # Unsigned char image format

# Image orientation constants
LONG_SIDE_HORIZONTAL = 1  # Horizontal orientation (width > height)
LONG_SIDE_VERTICAL = 2  # Vertical orientation (height > width)
LONG_SIDE_EQUAL = 0  # Square orientation (width == height)

# RPC method names
RPC_METHOD_GET_USER = "get_user"
RPC_METHOD_SAVE_IMAGE = "save_image"
RPC_METHOD_UPDATE_IMAGE = "update_image"

# RPC retry settings
RPC_MAX_RETRIES = 3
RPC_RETRY_DELAY = 1.0  # seconds
RPC_TIMEOUT = 10.0  # seconds
RPC_DEFAULT_TIMEOUT = 5.0  # seconds (default timeout for RPC calls)

# RPC connection settings
RPC_EXCHANGE_TYPE = "direct"  # Exchange type for RabbitMQ
RPC_CONTENT_TYPE = "application/json"  # Content type for RPC messages
RPC_DELIVERY_MODE = 2  # Persistent delivery mode (2 = persistent)
RPC_ENCODING = "utf-8"  # Encoding for message encoding/decoding

# RPC response waiting settings
RPC_RESPONSE_CHECK_STEP = 0.1  # Check interval in seconds (100ms)
RPC_CPU_DELAY = 0.01  # CPU delay in seconds to free CPU during waiting
RPC_CALLBACK_QUEUE_NAME = ""  # Empty string for temporary exclusive queue

# RPC response keys
RPC_RESPONSE_STATUS = "status"
RPC_RESPONSE_OK = "ok"
RPC_RESPONSE_ERROR = "error"
RPC_RESPONSE_ERROR_KEY = "error"  # Key name for error messages in response
RPC_RESPONSE_REASON = "reason"
RPC_RESPONSE_USER = "user"
RPC_ERROR_BAD_PAYLOAD = "bad_payload"
RPC_REQUEST_USER_ID = "user_id"
RPC_REQUEST_FOTOLAB_KEY = "key"

# User data keys
USER_DATA_ID = "id"

# HTTP status codes
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_INTERNAL_ERROR = 500
HTTP_STATUS_SERVICE_UNAVAILABLE = 503

# HTTP error messages
ERROR_USER_NOT_AUTHORIZED = "User not authorized"
ERROR_RPC_SERVICE_UNAVAILABLE = "RPC service unavailable: timeout waiting for response."
ERROR_RABBITMQ_CONNECTION = "RabbitMQ connection error: {error}"
ERROR_INTERNAL_SERVER = "Internal server error: {error}"
ERROR_CONNECTION_FAILED = "Connection failed after {attempts} attempts: {error}"
ERROR_RETRY_ATTEMPTS_FAILED = "Failed after all retry attempts"

# Template files
TEMPLATE_TEST_FORM = "test_form.html"
TEMPLATE_MULTIUSER_FORM = "multiuser_form.html"
FILE_ENCODING = "utf-8"

# Multiuser form translations (Russian)
MULTIUSER_TITLE = "Многопользовательский тест загрузки"
MULTIUSER_DESCRIPTION = (
    "<p>Пул файлов изображений будет отправлен одновременно несколькими имитированными пользователями. "
    "ID пользователей можно определить двумя путями.</p>"
    "<ol>"
    "<li>Выбрать набор ID из пула внизу формы и скопировать его в поле “ID пользователей”. "
    "ID непременно должны быть разделены запятой.</li>"
    "<li>Оставить поле “ID пользователей” пустым и ввести число пользователей в поле ”Количество пользователей”. "
    "В этом случае все виртуальные пользователи будут иметь ID 26.</li>"
    "</ol>"
    "<p>Первый способ имеет приоритет. Если в в поле “ID пользователей” есть данные, "
    "поле количества пользователей игнорируется.</p>"
)
MULTIUSER_LABEL_IMAGES_POOL = "Пул изображений:"
MULTIUSER_LABEL_USERS_COUNT = "Количество пользователей:"
MULTIUSER_LABEL_USER_IDS = "ID пользователей (через запятую):"
MULTIUSER_PLACEHOLDER_USER_IDS = "101, 102, 103"
MULTIUSER_BUTTON_START = "Начать загрузку"
MULTIUSER_BUTTON_CLEAR = "Очистить лог"
MULTIUSER_STATUS_NO_FILES = "Выберите хотя бы один файл."
MULTIUSER_STATUS_RUNNING = "Выполняется {count} запросов..."
MULTIUSER_STATUS_COMPLETED = "Готово. Успешно: {success}, Ошибок: {failed}"
MULTIUSER_REPORT_USER_ID = "User ID"
MULTIUSER_REPORT_FILE_FORMAT = "Файл {name}: размер {size_kb} кб, загружался {time_sec} сек, статус {status}."
MULTIUSER_REPORT_TOTAL_FORMAT = "Вся загрузка пользователя: {size_kb} кб, {time_sec} сек."
MULTIUSER_STATUS_OK = "успешно"
MULTIUSER_STATUS_ERROR = "ошибка"
MULTIUSER_ALLOWED_IDS_TITLE = "Список допустимых ID."
MULTIUSER_ALLOWED_IDS = os.getenv("MULTIUSER_ALLOWED_IDS", "")

# Form field aliases
FORM_FIELD_USER_ID = "userID"
FORM_FIELD_KEY = "key"

# Health check response
HEALTH_CHECK_STATUS = "ok"
HEALTH_CHECK_RESPONSE = {"status": HEALTH_CHECK_STATUS}

# CORS settings
CORS_ALLOW_ORIGINS = ["*"]  # Temporarily allow all for debugging
CORS_ALLOW_METHODS = ["POST", "OPTIONS", "GET"]
CORS_ALLOW_HEADERS = ["*"]  # Allow all headers
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["*"]

# Fotolab key (set in .env for production)
FOTOLAB_KEY = os.getenv("FOTOLAB_KEY", "")

def get_fotolab_key(uid: int) -> str:
    """Get Fotolab key from environment variable or return default value."""
    key = str(uid) + FOTOLAB_KEY + str(uid)
    return md5(key.encode('utf-8')).hexdigest()
TEST_FORM_SEKRET = os.getenv("TEST_FORM_SEKRET", "")

# RabbitMQ payload keys
PAYLOAD_KEY_USER_ID = "user_id"
PAYLOAD_KEY_NAME = "name"
PAYLOAD_KEY_ORIG_NAME = "orig_name"
PAYLOAD_KEY_WIDTH = "width"
PAYLOAD_KEY_HEIGHT = "height"
PAYLOAD_KEY_WIDTH_SM = "width_sm"
PAYLOAD_KEY_HEIGHT_SM = "height_sm"
PAYLOAD_KEY_FORMAT = "format"
PAYLOAD_KEY_LONG_SIDE = "long_side"
PAYLOAD_KEY_FACTOR = "factor"
PAYLOAD_KEY_RESOLUTION = "resolution"

# Response keys
RESPONSE_KEY_IMAGE_DATA = "image_data"
RESPONSE_KEY_RABBITMQ_RESPONSE = "rabbitmq_response"
RESPONSE_KEY_DETAIL = "detail"
RESPONSE_KEY_FILES = "files"

# Error messages
ERROR_FAILED_TO_CONNECT_RABBITMQ = "Failed to connect to RabbitMQ: {error}"

