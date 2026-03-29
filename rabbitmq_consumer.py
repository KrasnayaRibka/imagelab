"""
Universal RabbitMQ consumer with pluggable action handlers.

Listens to configured queues, parses messages by "action" field,
and dispatches to registered handlers. New actions can be added
via register_action() and add_queue_binding().

Author: Vadim Kalinin
Email: vadimakalin@gmail.com
"""
import json
import threading
import ast
from typing import Any, Callable, Dict, List, Optional, Tuple

import pika

from pathlib import Path

from config import (
    RABBITMQ_URL,
    RABBITMQ_EXCHANGE,
    RPC_EXCHANGE_TYPE,
    RABBITMQ_QUEUE_IMAGE_DELETE,
    RABBITMQ_ROUTING_KEY_IMAGE_DELETE,
    RABBITMQ_QUEUE_IMAGE_COPY,
    RABBITMQ_ROUTING_KEY_IMAGE_COPY,
    RABBITMQ_QUEUE_IMAGE_EDIT,
    RABBITMQ_ROUTING_KEY_IMAGE_EDIT,
    RABBITMQ_QUEUE_COPY_RESULT,
    RABBITMQ_ROUTING_KEY_COPY_RESULT,
    RPC_ENCODING,
)
from logger_config import get_logger
from rpc import RabbitRpcClient

logger = get_logger(__name__)

# Action name used in message payload
KEY_ACTION = "action"
KEY_DATA = "data"

# Registry: action_name -> handler(data, context)
_ACTION_HANDLERS: Dict[str, Callable[[dict, dict], None]] = {}

# List of (queue_name, routing_key) to consume from
_QUEUE_BINDINGS: List[Tuple[str, str]] = []

# Single consumer thread and shutdown event (one loop serves all queues)
_consumer_shutdown_event: Optional[threading.Event] = None
_consumer_started = False
_consumer_started_lock = threading.Lock()
_copy_result_client: Optional[RabbitRpcClient] = None
_copy_result_client_lock = threading.Lock()

# --- image_delete constants (used by built-in handler) ---
COMMAND_IMAGE_DELETE = "image_delete"
KEY_SOURCE_IMAGE_NAME = "source_image_name"
KEY_USER_ID = "user_id"
KEY_PRODUCT_PREVIEW_NAME = "product_preview_name"
KEY_ONLY_PREVIEW = "only_preview"

# --- image_copy constants (used by built-in handler) ---
COMMAND_IMAGE_COPY = "image_copy"
COMMAND_IMAGE_COPY_RESULT = "image_copy_result"
KEY_FROM = "from"
KEY_TO = "to"
KEY_LIST_COPY = "list_copy"
KEY_IMAGE_LIST = "image_list"
KEY_ORDER_FOLDER_PATH = "order_folder_path"
KEY_ORDER_ID = "order_id"
KEY_BX_ORDER_ID = "bx_order_id"

# --- image_edit (RPC) ---
ACTION_IMAGE_CROP = "image_crop"
ACTION_PRODUCT_CROP = "product_crop"
KEY_ATTRS = "attrs"


class ImageEditActions:
    """
    Image edit actions handler (RPC).

    Author: Vadim Kalinin
    Email: vadimakalin@gmail.com
    """

    def image_crop(self, data: dict) -> dict:
        attrs = {}
        if isinstance(data, dict):
            attrs = data.get(KEY_ATTRS)
        try:
            # Local import to avoid circular import (app.py imports rabbitmq_consumer.py)
            from app import crop_image as _crop_image

            result = _crop_image(attrs)
        except Exception as e:
            logger.exception("image_crop failed: %s", e)
            result = {"success": False, "errors": [f"image_crop failed: {e}"], "attrs": attrs}

        if not isinstance(result, dict):
            result = {"success": False, "errors": ["crop_image returned non-dict result"], "attrs": attrs}

        status = "OK" if bool(result.get("success")) else "FAIL"
        result["status"] = status
        return result

    def product_crop(self, data: dict) -> Optional[dict]:
        pass


def _get_copy_result_client() -> RabbitRpcClient:
    """Lazily initialize and return a shared RPC client for copy_result publishing."""
    global _copy_result_client
    with _copy_result_client_lock:
        if _copy_result_client is None:
            _copy_result_client = RabbitRpcClient(
                RABBITMQ_URL,
                exchange=RABBITMQ_EXCHANGE,
                routing_key=RABBITMQ_ROUTING_KEY_COPY_RESULT,
                queue=RABBITMQ_QUEUE_COPY_RESULT,
            )
        return _copy_result_client


def send_copy_result_message(message: dict) -> None:
    """
    Send copy result message to RabbitMQ copy_result queue.

    Args:
        message: Message payload (JSON-serializable dict).
    """
    if not isinstance(message, dict):
        raise ValueError("send_copy_result_message: message must be a dict")
    rpc_client = _get_copy_result_client()
    rpc_client.publish_message(message)
    logger.info("copy_result message published: keys=%s", sorted(message.keys()))


def register_action(action_name: str, handler: Callable[[dict, dict], None]) -> None:
    """
    Register a handler for the given action name.
    Handlers receive (data: dict, context: dict) and return None.
    """
    if not action_name or not callable(handler):
        raise ValueError("action_name must be non-empty and handler must be callable")
    _ACTION_HANDLERS[action_name] = handler
    logger.debug("Registered action handler: %s", action_name)


def add_queue_binding(queue_name: str, routing_key: str) -> None:
    """Add a queue and routing key to the list of bindings for the consumer."""
    if not queue_name or not routing_key:
        raise ValueError("queue_name and routing_key must be non-empty")
    binding = (queue_name.strip(), routing_key.strip())
    if binding not in _QUEUE_BINDINGS:
        _QUEUE_BINDINGS.append(binding)
        logger.debug("Added queue binding: queue=%s, routing_key=%s", queue_name, routing_key)


def _parse_message_body(body: bytes) -> Optional[dict]:
    """Decode and parse JSON message body. Returns None on failure."""
    try:
        return json.loads(body.decode(RPC_ENCODING))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Failed to parse message body: %s", e)
        return None


def _parse_message_body_lenient(body: bytes) -> Optional[dict]:
    """
    Decode and parse message body into dict.

    Supports strict JSON and a Python-literal fallback (e.g. single quotes),
    because some senders may send payloads like:
    {action:'image_crop', data:{attrs:{...}}}
    """
    if body is None:
        return None

    try:
        text = body.decode(RPC_ENCODING)
    except Exception as e:
        logger.warning("Failed to decode message body: %s", e)
        return None

    # First attempt: strict JSON
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    # Fallback: Python literal (handles single quotes)
    try:
        fixed = text
        # Make common JSON literals compatible with Python literal_eval
        fixed = fixed.replace(": null", ": None").replace(": true", ": True").replace(": false", ": False")
        parsed = ast.literal_eval(fixed)
        return parsed if isinstance(parsed, dict) else None
    except Exception as e:
        logger.warning("Lenient parse failed: %s", e)
        return None


def _is_only_preview(data: dict) -> bool:
    """Return True if only_preview is truthy."""
    val = data.get(KEY_ONLY_PREVIEW)
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def _handle_image_delete_message(data: dict, context: dict) -> None:
    """
    Handle a single image_delete command: validate user_id, then call
    delete_image_with_preview or delete_product_preview.
    """
    image_processor = context.get("image_processor")
    if image_processor is None:
        raise ValueError("image_delete: image_processor not found in context")

    user_id_raw = data.get(KEY_USER_ID)
    if user_id_raw is None:
        err = "image_delete: user_id is required"
        logger.error(err)
        raise ValueError(err)
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        err = "image_delete: user_id must be an integer"
        logger.error("%s, got: %s", err, user_id_raw)
        raise ValueError(err) from None
    if user_id <= 0:
        logger.error("image_delete: user_id must be positive, got %s", user_id)
        raise ValueError("image_delete: user_id must be positive")

    only_preview = _is_only_preview(data)
    product_preview_name = data.get(KEY_PRODUCT_PREVIEW_NAME) or ""

    if only_preview:
        image_processor.delete_product_preview(user_id, product_preview_name)
        logger.info("image_delete: executed delete_product_preview user_id=%s", user_id)
    else:
        source_image_name = data.get(KEY_SOURCE_IMAGE_NAME)
        if not source_image_name or (isinstance(source_image_name, str) and source_image_name.strip() == ""):
            err = "image_delete: source_image_name is required when only_preview is false"
            logger.error(err)
            raise ValueError(err)
        image_processor.delete_image_with_preview(
            source_image_name=str(source_image_name).strip(),
            user_id=user_id,
            product_preview_name=product_preview_name if isinstance(product_preview_name, str) else "",
        )
        logger.info(
            "image_delete: executed delete_image_with_preview source=%s user_id=%s",
            source_image_name,
            user_id,
        )


def _handle_image_copy_message(data: dict, context: dict) -> None:
    """
    Handle a single image_copy command.

    Modes:
    - list_copy falsy: copy a single file via file_copy(from, to)
    - list_copy truthy: copy listed images via copy_listed_images(image_list)
    """
    image_processor = context.get("image_processor")
    if image_processor is None:
        raise ValueError("image_copy: image_processor not found in context")

    def _is_truthy(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes", "on")
        return bool(value)

    list_copy = _is_truthy(data.get(KEY_LIST_COPY))

    if list_copy:
        image_list = data.get(KEY_IMAGE_LIST)
        if isinstance(image_list, str):
            try:
                image_list = json.loads(image_list)
            except json.JSONDecodeError as e:
                logger.error(
                    "image_copy: list_copy is true but 'image_list' JSON parsing failed: %s",
                    e,
                )
                return

        if not isinstance(image_list, list):
            logger.error(
                "image_copy: list_copy is true but 'image_list' has invalid type: %s",
                type(image_list).__name__,
            )
            return
        if not image_list:
            logger.info("image_copy: list_copy is true but 'image_list' is empty, nothing to copy")
            return

        report = image_processor.copy_listed_images(image_list)
        order_folder_path = data.get(KEY_ORDER_FOLDER_PATH)
        if order_folder_path:
            image_processor.write_copy_report(order_folder_path, report)
        report["action"] = COMMAND_IMAGE_COPY_RESULT
        report["user_id"] = data.get(KEY_USER_ID)
        report["order_id"] = data.get(KEY_ORDER_ID)
        report["bx_order_id"] = data.get(KEY_BX_ORDER_ID)
        try:
            send_copy_result_message(report)
            logger.info("image_copy: copy_result message published: keys=%s", sorted(report.keys()))
        except Exception as e:
            logger.exception("image_copy: failed to publish copy_result message: %s", e)
        logger.info(
            "image_copy: copy_listed_images finished, copied=%s failed=%s success=%s",
            report.get("copied"),
            report.get("failed"),
            report.get("success"),
        )
        return

    from_path_raw = data.get(KEY_FROM)
    to_path_raw = data.get(KEY_TO)
    if from_path_raw is None or (isinstance(from_path_raw, str) and not from_path_raw.strip()):
        logger.error("image_copy: 'from' is empty, skipping single file copy")
        return
    if to_path_raw is None or (isinstance(to_path_raw, str) and not to_path_raw.strip()):
        logger.error("image_copy: 'to' is empty, skipping single file copy")
        return

    # Normalize path separators to forward slashes (container runs Linux; sender may send Windows paths)
    from_path = Path(str(from_path_raw).strip().replace("\\", "/"))
    to_path = Path(str(to_path_raw).strip().replace("\\", "/"))

    success = image_processor.file_copy(from_path, to_path)
    if success:
        logger.info("image_copy: copied %s -> %s", from_path, to_path)
    else:
        logger.error("image_copy: failed to copy %s -> %s after max attempts", from_path, to_path)


def _dispatch_message(data: dict, context: dict) -> None:
    """Dispatch parsed message to the handler for data['action']."""
    action = data.get(KEY_ACTION)
    if not action or not isinstance(action, str):
        logger.warning("Message missing or invalid 'action' field, skipping")
        return
    action = action.strip()
    handler = _ACTION_HANDLERS.get(action)
    if handler is None:
        logger.warning("No handler registered for action '%s', skipping message", action)
        return
    try:
        handler(data, context)
    except ValueError as e:
        logger.error("%s validation error: %s", action, e)
    except Exception as e:
        logger.exception("%s execution error: %s", action, e)


def _run_consumer_loop(context: dict, shutdown_event: threading.Event) -> None:
    """Run the RabbitMQ consumer loop (blocking). Consumes from all registered queues. Reconnects on connection loss."""
    while not shutdown_event.is_set():
        bindings = list(_QUEUE_BINDINGS)
        if not bindings:
            logger.warning("No queue bindings registered, consumer will not receive messages")

        conn = None
        try:
            params = pika.URLParameters(RABBITMQ_URL)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.exchange_declare(
                exchange=RABBITMQ_EXCHANGE,
                exchange_type=RPC_EXCHANGE_TYPE,
                durable=True,
            )

            image_edit_actions = ImageEditActions()

            def on_message(_ch: Any, _method: Any, _props: Any, body: bytes) -> None:
                data = _parse_message_body(body)
                if data is None:
                    return
                _dispatch_message(data, context)

            def on_image_edit_message(_ch: Any, _method: Any, props: Any, body: bytes) -> None:
                request = _parse_message_body_lenient(body) or {}
                action = request.get(KEY_ACTION)
                data = request.get(KEY_DATA)
                if not isinstance(data, dict):
                    data = {}

                if action == ACTION_IMAGE_CROP:
                    response_dict = image_edit_actions.image_crop(data)
                elif action == ACTION_PRODUCT_CROP:
                    response_dict = image_edit_actions.product_crop(data)
                    if response_dict is None:
                        response_dict = {"success": False, "errors": ["product_crop not implemented"]}
                    response_dict["status"] = "OK" if bool(response_dict.get("success")) else "FAIL"
                else:
                    response_dict = {"success": False, "errors": [f"Unknown action: {action}"], "status": "FAIL"}

                if props is None or not getattr(props, "reply_to", None):
                    logger.warning("image_edit: missing reply_to, cannot respond. action=%s", action)
                    return

                try:
                    payload = json.dumps(response_dict, ensure_ascii=False).encode(RPC_ENCODING)
                except Exception as e:
                    logger.exception("image_edit: failed to serialize response: %s", e)
                    payload = json.dumps(
                        {"success": False, "errors": [f"Failed to serialize response: {e}"], "status": "FAIL"},
                        ensure_ascii=False,
                    ).encode(RPC_ENCODING)

                _ch.basic_publish(
                    exchange="",
                    routing_key=props.reply_to,
                    properties=pika.BasicProperties(correlation_id=getattr(props, "correlation_id", None)),
                    body=payload,
                )

            for queue_name, routing_key in bindings:
                ch.queue_declare(queue=queue_name, durable=True)
                ch.queue_bind(
                    exchange=RABBITMQ_EXCHANGE,
                    queue=queue_name,
                    routing_key=routing_key,
                )
                ch.basic_consume(
                    queue=queue_name,
                    on_message_callback=on_image_edit_message if queue_name == RABBITMQ_QUEUE_IMAGE_EDIT else on_message,
                    auto_ack=True,
                )

            logger.info(
                "RabbitMQ consumer started with %d queue(s): %s",
                len(bindings),
                [q for q, _ in bindings],
            )
            while not shutdown_event.is_set():
                conn.process_data_events(time_limit=1.0)
        except pika.exceptions.AMQPConnectionError as e:
            if shutdown_event.is_set():
                break
            logger.warning("RabbitMQ connection lost, reconnecting: %s", e)
            shutdown_event.wait(timeout=5.0)
        except Exception as e:
            if shutdown_event.is_set():
                break
            logger.exception("RabbitMQ consumer error: %s", e)
            shutdown_event.wait(timeout=5.0)
        finally:
            if conn and conn.is_open:
                try:
                    conn.close()
                except Exception:
                    pass


def start_consumer(
    context: dict,
    shutdown_event: Optional[threading.Event] = None,
) -> threading.Event:
    """
    Start the universal RabbitMQ consumer in a daemon thread.
    Consumes from all queues added via add_queue_binding() and dispatches
    to handlers registered via register_action().

    Args:
        context: Dict passed to every handler (e.g. image_processor, unzipper).
        shutdown_event: Optional event to signal shutdown; one is created if not provided.

    Returns:
        The shutdown event. Set it to stop the consumer.
    """
    global _consumer_shutdown_event, _consumer_started
    if shutdown_event is None:
        shutdown_event = threading.Event()
    with _consumer_started_lock:
        if _consumer_started:
            logger.debug("Consumer already started, returning existing shutdown event")
            if _consumer_shutdown_event is None:
                _consumer_shutdown_event = shutdown_event
            return _consumer_shutdown_event
        _consumer_started = True
        _consumer_shutdown_event = shutdown_event
    thread = threading.Thread(
        target=_run_consumer_loop,
        args=(context, shutdown_event),
        name="rabbitmq-consumer",
        daemon=True,
    )
    thread.start()
    return shutdown_event


def register_image_delete_action() -> None:
    """
    Register the built-in image_delete action and its queue binding.
    Call this before start_consumer() when you want image_delete plus other actions.
    The handler uses context['image_processor'] at runtime.
    """
    if COMMAND_IMAGE_DELETE not in _ACTION_HANDLERS:
        register_action(COMMAND_IMAGE_DELETE, _handle_image_delete_message)
    add_queue_binding(RABBITMQ_QUEUE_IMAGE_DELETE, RABBITMQ_ROUTING_KEY_IMAGE_DELETE)


def register_image_copy_action() -> None:
    """
    Register the built-in image_copy action and its queue binding.
    Call this before start_consumer() when you want image_copy.
    The handler uses context['image_processor'] and supports:
    - single copy: {"action":"image_copy","from":"source/path","to":"dest/path","list_copy":false}
    - listed copy: {"action":"image_copy","list_copy":true,"image_list":[...]}
    """
    if COMMAND_IMAGE_COPY not in _ACTION_HANDLERS:
        register_action(COMMAND_IMAGE_COPY, _handle_image_copy_message)
    add_queue_binding(RABBITMQ_QUEUE_IMAGE_COPY, RABBITMQ_ROUTING_KEY_IMAGE_COPY)


def register_image_edit_listener() -> None:
    """
    Register queue binding for imagelab.image_edit (RPC listener).

    Note: обработка делается отдельным callback'ом внутри consumer loop,
    потому что этому listener'у нужно публиковать ответ в reply_to.
    """
    add_queue_binding(RABBITMQ_QUEUE_IMAGE_EDIT, RABBITMQ_ROUTING_KEY_IMAGE_EDIT)


def start_image_delete_consumer(
    image_processor: Any,
    shutdown_event: Optional[threading.Event] = None,
) -> threading.Event:
    """
    Start the consumer with the image_delete action registered (backward compatible).
    Use this when you only need image_delete. To add more actions, call
    register_action() and add_queue_binding() before this, and pass a richer
    context to start_consumer() instead.

    Args:
        image_processor: ImageProcessor instance (stored in context for the handler).
        shutdown_event: Optional event to signal shutdown.

    Returns:
        The shutdown event. Set it to stop the consumer.
    """
    register_image_delete_action()
    context: dict = {"image_processor": image_processor}
    return start_consumer(context, shutdown_event)
