"""
FastAPI application for ImageLab service.

Provides REST API endpoints for image upload with user authorization via RPC.

Author: Vadim Kalinin
Email: vadimakalin@gmail.com
"""
import os
import time
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
import json
import pika
import aiofiles

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY

from image_processor import ImageProcessor
from config import (
    TEMPLATES_DIR, FILES_BASE_DIR, UPLOAD_DIR,
    RABBITMQ_URL, RABBITMQ_EXCHANGE, RABBITMQ_ROUTING_KEY, RABBITMQ_QUEUE,
    STATIC_DIR, STATIC_URL_PATH, STATIC_MOUNT_NAME,
    RPC_METHOD_GET_USER, RPC_METHOD_SAVE_IMAGE, RPC_METHOD_UPDATE_IMAGE,
    RPC_MAX_RETRIES, RPC_RETRY_DELAY, RPC_TIMEOUT,
    RPC_RESPONSE_STATUS, RPC_RESPONSE_OK, RPC_RESPONSE_ERROR,
    RPC_RESPONSE_ERROR_KEY, RPC_RESPONSE_REASON, RPC_RESPONSE_USER, RPC_ERROR_BAD_PAYLOAD,
    RPC_REQUEST_USER_ID, RPC_REQUEST_FOTOLAB_KEY, USER_DATA_ID,
    HTTP_STATUS_FORBIDDEN, HTTP_STATUS_INTERNAL_ERROR, HTTP_STATUS_SERVICE_UNAVAILABLE,
    ERROR_USER_NOT_AUTHORIZED, ERROR_RPC_SERVICE_UNAVAILABLE,
    ERROR_RABBITMQ_CONNECTION, ERROR_INTERNAL_SERVER,
    ERROR_CONNECTION_FAILED, ERROR_RETRY_ATTEMPTS_FAILED,
    TEMPLATE_TEST_FORM, TEMPLATE_MULTIUSER_FORM, FILE_ENCODING, FORM_FIELD_USER_ID, FORM_FIELD_KEY,
    HEALTH_CHECK_RESPONSE,
    MULTIUSER_TITLE, MULTIUSER_DESCRIPTION, MULTIUSER_LABEL_IMAGES_POOL,
    MULTIUSER_LABEL_USERS_COUNT, MULTIUSER_LABEL_USER_IDS, MULTIUSER_PLACEHOLDER_USER_IDS,
    MULTIUSER_BUTTON_START, MULTIUSER_BUTTON_CLEAR, MULTIUSER_STATUS_NO_FILES,
    MULTIUSER_STATUS_RUNNING, MULTIUSER_STATUS_COMPLETED, MULTIUSER_REPORT_USER_ID,
    MULTIUSER_REPORT_FILE_FORMAT, MULTIUSER_REPORT_TOTAL_FORMAT, MULTIUSER_STATUS_OK,
    MULTIUSER_STATUS_ERROR, MULTIUSER_ALLOWED_IDS_TITLE, MULTIUSER_ALLOWED_IDS,
    CORS_ALLOW_ORIGINS, CORS_ALLOW_METHODS, CORS_ALLOW_HEADERS,
    CORS_ALLOW_CREDENTIALS, CORS_EXPOSE_HEADERS,
    PAYLOAD_KEY_USER_ID, PAYLOAD_KEY_NAME, PAYLOAD_KEY_ORIG_NAME,
    PAYLOAD_KEY_WIDTH, PAYLOAD_KEY_HEIGHT, PAYLOAD_KEY_WIDTH_SM,
    PAYLOAD_KEY_HEIGHT_SM, PAYLOAD_KEY_FORMAT, PAYLOAD_KEY_LONG_SIDE,
    PAYLOAD_KEY_FACTOR, PAYLOAD_KEY_RESOLUTION,
    RESPONSE_KEY_IMAGE_DATA, RESPONSE_KEY_RABBITMQ_RESPONSE,
    RESPONSE_KEY_DETAIL, RESPONSE_KEY_FILES,
    ERROR_FAILED_TO_CONNECT_RABBITMQ,
    IMAGE_EXTENSIONS, ARCHIVE_EXTENSIONS, 
    get_fotolab_key, TEST_FORM_SEKRET
)
from rpc import RabbitRpcClient
from rabbitmq_consumer import (
    register_image_copy_action,
    register_image_delete_action,
    register_image_edit_listener,
    start_consumer,
)
from logger_config import setup_logging, get_logger
from unzipper import Unzipper

# Setup logging
setup_logging()

# Get logger for this module
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    logger.info("FastAPI application started")
    # Start RabbitMQ consumer for image_delete and image_copy (runs in background thread)
    register_image_delete_action()
    register_image_copy_action()
    register_image_edit_listener()
    shutdown_event = start_consumer({"image_processor": image_processor})
    app.state.image_delete_consumer_shutdown = shutdown_event
    yield
    logger.info("FastAPI application shutting down")
    shutdown_event.set()


app = FastAPI(lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler to log validation errors"""
    logger.error(
        "Validation error: method=%s, path=%s, errors=%s",
        request.method,
        request.url.path,
        exc.errors()
    )
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={RESPONSE_KEY_DETAIL: exc.errors()}
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request errors"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(
                "Request failed: method=%s, path=%s, error=%s",
                request.method,
                request.url.path,
                str(e),
                exc_info=True
            )
            raise


# Add logging middleware first (before CORS)
app.add_middleware(LoggingMiddleware)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_methods=CORS_ALLOW_METHODS,
    allow_headers=CORS_ALLOW_HEADERS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    expose_headers=CORS_EXPOSE_HEADERS,
)

# Mount static files directory
STATIC_DIR.mkdir(exist_ok=True)
app.mount(STATIC_URL_PATH, StaticFiles(directory=str(STATIC_DIR)), name=STATIC_MOUNT_NAME)
# Initialize image processor
image_processor = ImageProcessor(upload_dir=UPLOAD_DIR)

# Initialize unzipper
unzipper = Unzipper()


def get_file_extension(file: UploadFile) -> str:
    """
    Get file extension from filename.
    
    Args:
        file: UploadFile object
        
    Returns:
        File extension with leading dot (e.g., ".jpg") or empty string
    """
    if file.filename:
        return Path(file.filename).suffix.lower()
    return ""


def is_image_file(file: UploadFile) -> bool:
    """
    Check if file is an image based on extension.
    
    Args:
        file: UploadFile object
        
    Returns:
        True if file extension is in IMAGE_EXTENSIONS, False otherwise
    """
    ext = get_file_extension(file)
    return ext in IMAGE_EXTENSIONS


def is_archive_file(file: UploadFile) -> bool:
    """
    Check if file is an archive based on extension.
    
    Args:
        file: UploadFile object
        
    Returns:
        True if file extension is in ARCHIVE_EXTENSIONS, False otherwise
    """
    ext = get_file_extension(file)
    return ext in ARCHIVE_EXTENSIONS


def get_rpc_client():
    """Lazy initialization of RPC client"""
    if not hasattr(get_rpc_client, 'client') or get_rpc_client.client is None:
        try:
            get_rpc_client.client = RabbitRpcClient(
                RABBITMQ_URL,
                exchange=RABBITMQ_EXCHANGE,
                routing_key=RABBITMQ_ROUTING_KEY,
                queue=RABBITMQ_QUEUE
            )
        except Exception as e:
            logger.error("Failed to initialize RPC client: %s", e, exc_info=True)
            raise RuntimeError(ERROR_FAILED_TO_CONNECT_RABBITMQ.format(error=e)) from e
    return get_rpc_client.client


def authorize_user(user_id: int) -> dict:
    """Authorize user via RPC call.
    
    Args:
        user_id: User ID to authorize
        
    Returns:
        dict: User data if authorization successful
        
    Raises:
        HTTPException: If user is not authorized
    """
    rpc_client = get_rpc_client()
    resp = rpc_client.call(RPC_METHOD_GET_USER, {RPC_REQUEST_USER_ID: user_id, RPC_REQUEST_FOTOLAB_KEY: get_fotolab_key(user_id)})
    if resp.get(RPC_RESPONSE_STATUS) != RPC_RESPONSE_OK:
        logger.warning("User authorization failed: userID=%s", user_id)
        raise HTTPException(status_code=HTTP_STATUS_FORBIDDEN, detail=ERROR_USER_NOT_AUTHORIZED)
    return resp[RPC_RESPONSE_USER]


def prepare_rabbitmq_payload(result: dict, user_id: int) -> dict:
    """Prepare payload for RabbitMQ save_image call.
    
    Args:
        result: Image processing result from image_processor
        user_id: User ID from authorization
        
    Returns:
        dict: Payload for RabbitMQ
    """
    return {
        PAYLOAD_KEY_USER_ID: int(result.get(PAYLOAD_KEY_USER_ID, user_id)),
        PAYLOAD_KEY_NAME: result.get(PAYLOAD_KEY_NAME, ""),
        PAYLOAD_KEY_ORIG_NAME: result.get(PAYLOAD_KEY_ORIG_NAME, ""),
        PAYLOAD_KEY_WIDTH: int(result.get(PAYLOAD_KEY_WIDTH, 0)),
        PAYLOAD_KEY_HEIGHT: int(result.get(PAYLOAD_KEY_HEIGHT, 0)),
        PAYLOAD_KEY_WIDTH_SM: float(result.get(PAYLOAD_KEY_WIDTH_SM, 0.0)),
        PAYLOAD_KEY_HEIGHT_SM: float(result.get(PAYLOAD_KEY_HEIGHT_SM, 0.0)),
        PAYLOAD_KEY_FORMAT: result.get(PAYLOAD_KEY_FORMAT, ""),
        PAYLOAD_KEY_LONG_SIDE: int(result.get(PAYLOAD_KEY_LONG_SIDE, 0)),
        PAYLOAD_KEY_FACTOR: float(result.get(PAYLOAD_KEY_FACTOR, 0.0)),
        PAYLOAD_KEY_RESOLUTION: float(result.get(PAYLOAD_KEY_RESOLUTION, 0.0))
    }


def send_image_to_rabbitmq(rpc_client: RabbitRpcClient, payload: dict) -> dict:
    """Send image data to RabbitMQ with retry logic.
    
    Args:
        rpc_client: RPC client instance
        payload: Payload to send to RabbitMQ
        
    Returns:
        dict: RabbitMQ response
    """
    for attempt in range(1, RPC_MAX_RETRIES + 1):
        try:
            # Reconnect RPC client if retrying
            if attempt > 1:
                get_rpc_client.client = None
                rpc_client = get_rpc_client()
            
            rabbitmq_response = rpc_client.call(RPC_METHOD_SAVE_IMAGE, payload, timeout=RPC_TIMEOUT)
            
            # Check if response indicates connection issue
            if (rabbitmq_response.get(RPC_RESPONSE_STATUS) == RPC_RESPONSE_ERROR and
                rabbitmq_response.get(RPC_RESPONSE_REASON) == RPC_ERROR_BAD_PAYLOAD):
                if attempt < RPC_MAX_RETRIES:
                    time.sleep(RPC_RETRY_DELAY)
                    continue
            
            # Success or non-retryable error
            return rabbitmq_response
            
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError, TimeoutError) as conn_error:
            if attempt < RPC_MAX_RETRIES:
                logger.warning("RabbitMQ connection error, retrying... (attempt %d/%d)", attempt, RPC_MAX_RETRIES)
                time.sleep(RPC_RETRY_DELAY)
                continue
            else:
                logger.error("Failed to send data to RabbitMQ after %d attempts: %s", RPC_MAX_RETRIES, conn_error, exc_info=True)
                return {
                    RPC_RESPONSE_STATUS: RPC_RESPONSE_ERROR,
                    RPC_RESPONSE_ERROR_KEY: ERROR_CONNECTION_FAILED.format(attempts=RPC_MAX_RETRIES, error=str(conn_error))
                }
        except Exception as rabbitmq_error:
            logger.error("Failed to send data to RabbitMQ: %s", rabbitmq_error, exc_info=True)
            return {
                RPC_RESPONSE_STATUS: RPC_RESPONSE_ERROR,
                RPC_RESPONSE_ERROR_KEY: str(rabbitmq_error)
            }
    
    # If all retries failed
    logger.error("Failed to send data to RabbitMQ after all retries")
    return {
        RPC_RESPONSE_STATUS: RPC_RESPONSE_ERROR,
        RPC_RESPONSE_ERROR_KEY: ERROR_RETRY_ATTEMPTS_FAILED
    }



def update_image_data(attributes) -> dict:
    """
    Update image data via RPC call.

    Args:
        attributes: Dict with image attributes or JSON string with such dict.

    Returns:
        dict: Result with keys:
            - success (bool)
            - errors (list of str)
            - attrs (parsed attributes dict or None)
            - rpc_response (RPC response dict, optional)
    """
    result = {
        "success": True,
        "errors": [],
        "attrs": None,
    }

    attrs = attributes

    # Normalize attributes to dict
    try:
        if isinstance(attrs, str):
            try:
                attrs = json.loads(attrs)
            except json.JSONDecodeError as e:
                msg = f"Failed to parse attributes JSON: {e}"
                logger.error(msg, exc_info=True)
                result["errors"].append(msg)
                result["success"] = False
                return result

        if not isinstance(attrs, dict):
            msg = f"Attributes must be a dict, got {type(attrs).__name__}"
            logger.error(msg)
            result["errors"].append(msg)
            result["success"] = False
            return result

        result["attrs"] = attrs

        rpc_client = get_rpc_client()
        message_payload = {"attrs": attrs}
        # RPC_METHOD_UPDATE_IMAGE currently equals underlying action name
        # and is used for clarity and configuration.
        rpc_response = rpc_client.call(RPC_METHOD_UPDATE_IMAGE, message_payload, timeout=RPC_TIMEOUT)
        logger.info("update_image_data RPC response: %s", rpc_response)
        result["rpc_response"] = rpc_response
        return result

    except TimeoutError as e:
        msg = f"RPC timeout in update_image_data: {e}"
    except (
        pika.exceptions.AMQPConnectionError,
        pika.exceptions.AMQPChannelError,
        pika.exceptions.StreamLostError,
    ) as e:
        msg = f"RabbitMQ error in update_image_data: {e}"
    except Exception as e:
        msg = f"Unexpected error in update_image_data: {e}"

    logger.error(msg, exc_info=True)
    result["errors"].append(msg)
    result["success"] = False
    return result


def _make_crop_result(success: bool, errors: list, attrs, method: str = "cropx") -> dict:
    return {
        "success": bool(success),
        "errors": errors or [],
        "attrs": attrs,
        "method": method,
    }


def _json_string_response(payload: dict) -> Response:
    """
    Return response whose body is a JSON-encoded string of the payload.
    So the HTTP body is a string like: "{\"success\":true,...}".
    When the client parses the response once (e.g. response.json()), they get
    a string; they can then JSON.parse that string to get the object.
    This matches frontends that expect to receive a JSON string and call JSON.parse on it.
    """
    json_str = json.dumps(payload, ensure_ascii=False)
    return Response(
        content=json.dumps(json_str),
        media_type="application/json",
    )


def crop_image(attributes: dict) -> dict:
    """
    Crop/edit image based on attributes.

    Args:
        attributes: dict with image attributes (must contain was_cropped, user_id, name, etc.)

    Returns:
        dict result with keys: success (bool), errors (list), attrs (dict), method (str)
    """
    if not isinstance(attributes, dict):
        return _make_crop_result(
            success=False,
            errors=[f"attributes must be a dict, got {type(attributes).__name__}"],
            attrs=attributes,
        )

    attrs = attributes
    logger.info("crop_image() start: user_id=%s, name=%s, was_cropped_raw=%s", attrs.get("user_id"), attrs.get("name"), attrs.get("was_cropped"))
    was_cropped_raw = attrs.get("was_cropped", 0)
    try:
        was_cropped = int(was_cropped_raw)
    except (TypeError, ValueError):
        was_cropped = 0

    try:
        if was_cropped == 2:
            logger.info("crop_image() calling drop_edit_image")
            result = image_processor.drop_edit_image(attrs)
            logger.info("crop_image() drop_edit_image done")
        else:
            logger.info("crop_image() calling edit_image")
            result = image_processor.edit_image(attrs, was_cropped=(was_cropped == 1))
            logger.info("crop_image() edit_image done")
    except Exception as e:
        logger.error("crop_image() processing failed: %s", e, exc_info=True)
        return _make_crop_result(
            success=False,
            errors=[f"crop_image() processing failed: {e}"],
            attrs=attrs,
        )

    if not isinstance(result, dict):
        return _make_crop_result(
            success=False,
            errors=["ImageProcessor returned non-dict result"],
            attrs=attrs,
        )

    # Ensure standard keys exist
    result.setdefault("success", False)
    result.setdefault("errors", [])
    result.setdefault("attrs", attrs)
    result.setdefault("method", "cropx")

    if result.get("success") is True:
        try:
            logger.info("crop_image() calling update_image_data")
            update_result = update_image_data(result.get("attrs"))
            logger.info("crop_image() update_image_data done: success=%s", update_result.get("success") if isinstance(update_result, dict) else None)
            if isinstance(update_result, dict) and not update_result.get("success", True):
                result["success"] = False
                result["errors"].extend(update_result.get("errors", []) or [])
        except Exception as e:
            logger.error("Failed to update image data in crop_image(): %s", e, exc_info=True)
            result["success"] = False
            result["errors"].append(f"Failed to update image data: {e}")

    logger.info("crop_image() returning success=%s", result.get("success"))
    return result


async def _get_request_field_attrs(request: Request):
    """
    Extract 'attrs' field from request body for AJAX POST.
    Supports JSON body and form-encoded body.
    """
    try:
        body = None
        try:
            body = await request.json()
        except Exception:
            body = None
        if isinstance(body, dict) and "attrs" in body:
            return body.get("attrs")
    except Exception:
        # Intentionally ignore; we'll try form next
        pass

    try:
        form = await request.form()
        if form is not None:
            return form.get("attrs")
    except Exception:
        pass

    return None


@app.post("/crop")
async def crop(request: Request):
    """
    AJAX endpoint to crop/edit image.

    Expects POST body field 'attrs' containing JSON string or dict of attributes.
    """
    # Log immediately on entry (before any await) to confirm request reaches this handler
    logger.info(
        "crop() entry: method=%s, path=%s, url=%s",
        request.method,
        request.url.path,
        str(request.url),
    )
    input_attrs = await _get_request_field_attrs(request)
    logger.info(
        "crop() after body: raw_attrs_type=%s",
        type(input_attrs).__name__,
    )
    if input_attrs is None:
        return _json_string_response(_make_crop_result(
            success=False,
            errors=["Missing required field 'attrs' in request body"],
            attrs=input_attrs,
        ))

    attrs = input_attrs
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse attrs JSON in crop(): %s", e, exc_info=True)
            return _json_string_response(_make_crop_result(
                success=False,
                errors=[f"Failed to parse attrs JSON: {e}"],
                attrs=input_attrs,
            ))

    if not isinstance(attrs, dict):
        return _json_string_response(_make_crop_result(
            success=False,
            errors=[f"attrs must be a JSON object (dict), got {type(attrs).__name__}"],
            attrs=input_attrs,
        ))

    logger.info(
        "crop() parsed attrs keys: %s",
        sorted(attrs.keys()),
    )

    # pyvips and filesystem operations are CPU/blocking; keep event loop responsive.
    logger.info("crop() calling run_in_threadpool(crop_image, attrs)")
    try:
        result = await run_in_threadpool(crop_image, attrs)
        logger.info("crop() run_in_threadpool returned")
    except Exception as e:
        logger.exception("crop() run_in_threadpool raised: %s", e)
        return _json_string_response(_make_crop_result(
            success=False,
            errors=[f"Server error during crop: {e}"],
            attrs=attrs,
        ))
    return _json_string_response(result)



# Health check endpoint
@app.get("/health")
def health():
    """Health check endpoint that returns the service status."""
    return HEALTH_CHECK_RESPONSE

# List files
@app.get("/list-files")
def list_files():
    """List files in the base directory.
    
    Returns:
        dict: Dictionary containing a list of filenames in the base directory.
              If directory doesn't exist, returns empty list.
    """
    try:
        files = os.listdir(FILES_BASE_DIR)
    except FileNotFoundError:
        files = []
    return {RESPONSE_KEY_FILES: files}

# Upload form
@app.get("/upload", response_class=HTMLResponse)
def test_form():
    """Returns a simple form with file upload and userID fields"""
    html_file = TEMPLATES_DIR / TEMPLATE_TEST_FORM
    with open(html_file, "r", encoding=FILE_ENCODING) as f:
        html_content = f.read()
    html_content = html_content.replace(
        "{{TEST_FORM_SEKRET_JSON}}",
        json.dumps(TEST_FORM_SEKRET),
    )
    return html_content

# Multi-user upload test form
@app.get("/multiuser", response_class=HTMLResponse)
def multiuser_form():
    """Returns a multi-user test form for concurrent image uploads"""
    html_file = TEMPLATES_DIR / TEMPLATE_MULTIUSER_FORM
    with open(html_file, "r", encoding=FILE_ENCODING) as f:
        html_content = f.read()
    return (
        html_content
        .replace("{{TEST_FORM_SEKRET}}", TEST_FORM_SEKRET)
        .replace("{{MULTIUSER_TITLE}}", MULTIUSER_TITLE)
        .replace("{{MULTIUSER_DESCRIPTION}}", MULTIUSER_DESCRIPTION)
        .replace("{{MULTIUSER_LABEL_IMAGES_POOL}}", MULTIUSER_LABEL_IMAGES_POOL)
        .replace("{{MULTIUSER_LABEL_USERS_COUNT}}", MULTIUSER_LABEL_USERS_COUNT)
        .replace("{{MULTIUSER_LABEL_USER_IDS}}", MULTIUSER_LABEL_USER_IDS)
        .replace("{{MULTIUSER_PLACEHOLDER_USER_IDS}}", MULTIUSER_PLACEHOLDER_USER_IDS)
        .replace("{{MULTIUSER_BUTTON_START}}", MULTIUSER_BUTTON_START)
        .replace("{{MULTIUSER_BUTTON_CLEAR}}", MULTIUSER_BUTTON_CLEAR)
        .replace("{{MULTIUSER_STATUS_NO_FILES}}", MULTIUSER_STATUS_NO_FILES)
        .replace("{{MULTIUSER_STATUS_RUNNING}}", MULTIUSER_STATUS_RUNNING)
        .replace("{{MULTIUSER_STATUS_COMPLETED}}", MULTIUSER_STATUS_COMPLETED)
        .replace("{{MULTIUSER_REPORT_USER_ID}}", MULTIUSER_REPORT_USER_ID)
        .replace("{{MULTIUSER_REPORT_FILE_FORMAT}}", MULTIUSER_REPORT_FILE_FORMAT)
        .replace("{{MULTIUSER_REPORT_TOTAL_FORMAT}}", MULTIUSER_REPORT_TOTAL_FORMAT)
        .replace("{{MULTIUSER_STATUS_OK}}", MULTIUSER_STATUS_OK)
        .replace("{{MULTIUSER_STATUS_ERROR}}", MULTIUSER_STATUS_ERROR)
        .replace("{{MULTIUSER_ALLOWED_IDS_TITLE}}", MULTIUSER_ALLOWED_IDS_TITLE)
        .replace("{{MULTIUSER_ALLOWED_IDS}}", MULTIUSER_ALLOWED_IDS)
    )

# Upload file
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Form(..., alias=FORM_FIELD_USER_ID),
    key: str = Form(..., alias=FORM_FIELD_KEY)
):
    """Handles file upload: processes images or extracts ZIP archives"""
    if key != TEST_FORM_SEKRET and key != get_fotolab_key(user_id):
        raise HTTPException(status_code=400, detail="Invalid key")
    try:
        # 1. Authorize user
        user_data = authorize_user(user_id)
        user_data_id = user_data[USER_DATA_ID]
        
        # 2. Check file extension and process accordingly
        if is_archive_file(file):
            # Handle ZIP archive
            logger.info("Processing ZIP archive: %s for user_id=%s", file.filename, user_data_id)
            
            # Save ZIP file to temporary location
            temp_dir = Path(tempfile.gettempdir())
            temp_zip_path = temp_dir / f"upload_{user_data_id}_{file.filename}"
            
            try:
                # Save uploaded file to temporary location
                async with aiofiles.open(temp_zip_path, 'wb') as temp_file:
                    content = await file.read()
                    await temp_file.write(content)
                
                # Extract ZIP archive, process files, and get results
                processed_files = unzipper.unzip_for_user(temp_zip_path, user_data_id, image_processor)
                
                logger.info("Processed %d files from ZIP archive %s", len(processed_files), file.filename)
                
                # Send each processed file to RabbitMQ
                rpc_client = get_rpc_client()
                rabbitmq_responses = []
                
                for file_result in processed_files:
                    try:
                        payload = prepare_rabbitmq_payload(file_result, user_data_id)
                        rabbitmq_response = send_image_to_rabbitmq(rpc_client, payload)
                        rabbitmq_responses.append(rabbitmq_response)
                    except Exception as rabbitmq_error:
                        logger.error("Failed to send file to RabbitMQ: %s", rabbitmq_error, exc_info=True)
                        rabbitmq_responses.append({
                            RPC_RESPONSE_STATUS: RPC_RESPONSE_ERROR,
                            RPC_RESPONSE_ERROR_KEY: str(rabbitmq_error)
                        })
                
                # Clean up temporary ZIP file
                try:
                    temp_zip_path.unlink()
                except Exception as cleanup_error:
                    logger.warning("Failed to cleanup temporary ZIP file %s: %s", temp_zip_path, cleanup_error)
                
                # Determine overall RabbitMQ response status
                # Check if all responses are successful
                all_successful = all(
                    resp.get(RPC_RESPONSE_STATUS) == RPC_RESPONSE_OK 
                    for resp in rabbitmq_responses
                ) if rabbitmq_responses else True
                
                # Create unified response format similar to image upload
                # Use first file's data as primary image_data for Uppy compatibility
                primary_image_data = processed_files[0] if processed_files else {}
                
                # Create combined RabbitMQ response
                combined_rabbitmq_response = {
                    RPC_RESPONSE_STATUS: RPC_RESPONSE_OK if all_successful else RPC_RESPONSE_ERROR,
                    "files_count": len(processed_files),
                    "responses": rabbitmq_responses
                }
                
                return {
                    RESPONSE_KEY_IMAGE_DATA: primary_image_data,
                    "is_archive": True,
                    RESPONSE_KEY_RABBITMQ_RESPONSE: combined_rabbitmq_response,
                    RESPONSE_KEY_FILES: processed_files,
                    "files_processed": len(processed_files),
                    "filename": file.filename
                }
                
            except Exception as zip_error:
                # Clean up temporary file on error
                try:
                    if temp_zip_path.exists():
                        temp_zip_path.unlink()
                except:
                    pass
                logger.error("Error processing ZIP archive: %s", zip_error, exc_info=True)
                raise
            
        elif is_image_file(file):
            # Handle image file
            logger.info("Processing image file: %s for user_id=%s", file.filename, user_data_id)
            
            try:
                result = await image_processor.save(file, user_data_id)
            except Exception as save_error:
                logger.error("Error in image_processor.save: %s", save_error, exc_info=True)
                raise
            
            # Send data to RabbitMQ
            rpc_client = get_rpc_client()
            payload = prepare_rabbitmq_payload(result, user_data_id)
            rabbitmq_response = send_image_to_rabbitmq(rpc_client, payload)
            
            return {
                RESPONSE_KEY_IMAGE_DATA: result,
                'is_archive': False,
                RESPONSE_KEY_RABBITMQ_RESPONSE: rabbitmq_response
            }
        else:
            # Unsupported file type
            ext = get_file_extension(file)
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Only image files and ZIP archives are allowed."
            )

    except TimeoutError as e:
        logger.error("RPC timeout error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_STATUS_SERVICE_UNAVAILABLE,
            detail=ERROR_RPC_SERVICE_UNAVAILABLE
        ) from e
    except pika.exceptions.AMQPConnectionError as e:
        logger.error("RabbitMQ connection error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_STATUS_SERVICE_UNAVAILABLE,
            detail=ERROR_RABBITMQ_CONNECTION.format(error=str(e))
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during file upload: %s", e, exc_info=True)
        raise HTTPException(
            status_code=HTTP_STATUS_INTERNAL_ERROR,
            detail=ERROR_INTERNAL_SERVER.format(error=str(e))
        ) from e
