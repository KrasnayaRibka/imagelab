# imagelab_rpc.py
import uuid
import json
import threading
import time
import logging
import pika
import config

# Configure logger for RPC client
logger = logging.getLogger(__name__)


class RabbitRpcClient:
    """
    RabbitMQ RPC client for making remote procedure calls.
    
    Provides functionality for sending RPC requests through RabbitMQ exchange
    and receiving responses via callback queue with correlation ID matching.
    
    Author: Vadim Kalinin
    Email: vadimakalin@gmail.com
    """
    def __init__(self, amqp_url: str, exchange: str = config.RABBITMQ_EXCHANGE, routing_key: str = config.RABBITMQ_ROUTING_KEY, queue: str = None):
        self._amqp_url = amqp_url
        self._exchange = exchange
        self._routing_key = routing_key
        self._queue = queue  # Optional: explicit queue name

        logger.info("Initializing RPC client: exchange=%s, routing_key=%s, queue=%s", exchange, routing_key, queue)

        self._connect_to_rabbitmq()
        self._declare_exchange()
        if self._queue:
            self._setup_queue()
        self._setup_callback_queue()
        
        self._response = None
        self._corr_id = None
        self._lock = threading.Lock()
        
        logger.info("RPC client initialized successfully")

    def _connect_to_rabbitmq(self):
        """Establish connection to RabbitMQ and create channel"""
        try:
            params = pika.URLParameters(self._amqp_url)
            self._conn = pika.BlockingConnection(params)
            self._ch = self._conn.channel()
        except Exception as e:
            logger.error("Failed to connect to RabbitMQ: %s", e)
            raise

    def _declare_exchange(self):
        """Declare exchange (idempotent operation)"""
        try:
            self._ch.exchange_declare(exchange=self._exchange, exchange_type=config.RPC_EXCHANGE_TYPE, durable=True)
        except Exception as e:
            logger.error("Failed to declare exchange %s: %s", self._exchange, e)
            raise

    def _setup_queue(self):
        """Check/create queue and bind it to exchange with routing_key"""
        try:
            self._ensure_queue_exists()
            self._bind_queue_to_exchange()
        except Exception as e:
            logger.error("Failed to check/create/bind queue %s: %s", self._queue, e)
            raise

    def _ensure_queue_exists(self):
        """Check if queue exists, create if it doesn't"""
        try:
            self._ch.queue_declare(queue=self._queue, passive=True)
        except pika.exceptions.ChannelClosedByBroker:
            logger.warning("Queue %s does not exist, creating it...", self._queue)
            self._ch.queue_declare(queue=self._queue, durable=True, passive=False)

    def _bind_queue_to_exchange(self):
        """Bind queue to exchange with routing_key (idempotent operation)"""
        try:
            self._ch.queue_bind(
                exchange=self._exchange,
                queue=self._queue,
                routing_key=self._routing_key
            )
        except (pika.exceptions.ChannelClosedByBroker, pika.exceptions.AMQPChannelError, pika.exceptions.AMQPConnectionError) as bind_error:
            # Binding may already exist, this is normal
            logger.debug("Queue binding (may already exist): %s", bind_error)

    def _setup_callback_queue(self):
        """Create exclusive callback queue and register consumer"""
        result = self._ch.queue_declare(queue=config.RPC_CALLBACK_QUEUE_NAME, exclusive=True)
        self._callback_queue = result.method.queue
        
        self._ch.basic_consume(
            queue=self._callback_queue,
            on_message_callback=self._on_response,
            auto_ack=True,
        )

    def _on_response(self, _ch, _method, props, body):
        """Handle incoming response message"""
        if self._corr_id == props.correlation_id:
            self._response = body
            logger.debug("Response received: correlation_id=%s, size=%s bytes", props.correlation_id, len(body))
            self._check_response_for_errors(body)
        else:
            logger.debug("Response correlation_id mismatch: got %s, expected %s", props.correlation_id, self._corr_id)

    def _check_response_for_errors(self, body):
        """Parse response and check for error status"""
        try:
            response_data = json.loads(body.decode(config.RPC_ENCODING))
            if 'status' in response_data and response_data.get('status') == 'error':
                logger.warning("Response contains error status: %s", response_data)
        except:
            pass

    def _ensure_connection(self):
        """Ensure connection and channel are open, reconnect if needed"""
        try:
            if self._conn.is_closed or self._ch.is_closed:
                logger.warning("Connection or channel is closed, reconnecting...")
                self._reconnect()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError, AttributeError, RuntimeError) as e:
            logger.warning("Error checking connection: %s, reconnecting...", e)
            self._reconnect()
    
    def _reconnect(self):
        """Reconnect to RabbitMQ and recreate channel"""
        try:
            self._close_connection()
            logger.info("Reconnecting to RabbitMQ...")
            self._connect_to_rabbitmq()
            self._declare_exchange()
            if self._queue:
                self._setup_queue()
            self._setup_callback_queue()
            logger.info("Successfully reconnected to RabbitMQ")
        except Exception as e:
            logger.error("Failed to reconnect: %s", e)
            raise

    def _close_connection(self):
        """Close existing connection if it exists"""
        try:
            if not self._conn.is_closed:
                self._conn.close()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.AMQPChannelError):
            pass

    def call(self, action: str, payload: dict, timeout: float = config.RPC_DEFAULT_TIMEOUT) -> dict:
        """
        Универсальный RPC-вызов:
        action: "get_user" | "save_image" | ...
        payload: тело запроса
        """
        logger.info("RPC call: action=%s, payload=%s, timeout=%ss", action, payload, timeout)
        with self._lock:
            self._ensure_connection()
            self._prepare_request(action, payload)
            self._publish_request()
            self._wait_for_response(timeout)
            return self._parse_response()
    
    def _prepare_request(self, action: str, payload: dict):
        """Prepare request data and generate correlation ID"""
        self._response = None
        self._corr_id = str(uuid.uuid4())
        logger.debug("Generated correlation_id: %s", self._corr_id)
        
        data = {"action": action, **payload}
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode(config.RPC_ENCODING)
        self._validate_json(body)
        self._request_body = body

    def _validate_json(self, body: bytes):
        """Validate JSON encoding"""
        try:
            json.loads(body.decode(config.RPC_ENCODING))
        except json.JSONDecodeError as e:
            logger.error("JSON validation failed: %s", e)
            raise

    def _publish_request(self):
        """Publish request message to exchange"""
        try:
            props = pika.BasicProperties(
                reply_to=self._callback_queue,
                correlation_id=self._corr_id,
                content_type=config.RPC_CONTENT_TYPE,
                delivery_mode=config.RPC_DELIVERY_MODE,
            )
            
            self._ch.basic_publish(
                exchange=self._exchange,
                routing_key=self._routing_key,
                properties=props,
                body=self._request_body
            )
            
            logger.debug("Message published: exchange=%s, routing_key=%s, queue=%s", 
                       self._exchange, self._routing_key, self._queue)
        except Exception as e:
            logger.error("Failed to publish message: %s", e)
            raise

    def publish_message(self, message: dict, routing_key: str = None):
        """
        Publish a fire-and-forget message without waiting for response.

        Args:
            message: Message payload to publish as JSON.
            routing_key: Optional routing key override.
        """
        if not isinstance(message, dict):
            raise ValueError("message must be a dict")

        rk = routing_key or self._routing_key
        body = json.dumps(message, ensure_ascii=False, separators=(',', ':')).encode(config.RPC_ENCODING)
        self._validate_json(body)

        with self._lock:
            self._ensure_connection()
            props = pika.BasicProperties(
                content_type=config.RPC_CONTENT_TYPE,
                delivery_mode=config.RPC_DELIVERY_MODE,
            )
            self._ch.basic_publish(
                exchange=self._exchange,
                routing_key=rk,
                properties=props,
                body=body,
            )
        logger.debug(
            "Message published (no response expected): exchange=%s, routing_key=%s, queue=%s",
            self._exchange,
            rk,
            self._queue,
        )

    def _wait_for_response(self, timeout: float):
        """Wait for response with event processing"""
        waited = 0.0
        step = config.RPC_RESPONSE_CHECK_STEP
        while self._response is None and waited < timeout:
            self._conn.process_data_events(time_limit=step)
            if self._response is None:
                waited += step
                time.sleep(config.RPC_CPU_DELAY)

        if self._response is None:
            logger.error("RPC timeout after %ss. Exchange: %s, Routing key: %s, Queue: %s", 
                        timeout, self._exchange, self._routing_key, self._queue)
            raise TimeoutError(f"RPC timeout after {timeout}s. Exchange: {self._exchange}, Routing key: {self._routing_key}")

    def _parse_response(self) -> dict:
        """Parse and return response data"""
        try:
            response_data = json.loads(self._response.decode(config.RPC_ENCODING))
            return response_data
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error("Failed to parse RPC response: %s. Response (first 200 chars): %s", 
                        e, self._response[:200] if self._response else 'None')
            raise ValueError(f"Failed to parse RPC response: {e}. Response: {self._response}") from e

    def close(self):
        logger.info("Closing RPC client connection")
        self._conn.close()
