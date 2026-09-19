"""Constants for the Is Around Connector integration."""

from . import contract

DOMAIN = "is_around_connector"

CONF_APP_URL = "app_url"
CONF_PRINTER_ENTITY = (
    "printer_entity"  # Keep for backward compat if needed, or deprecate
)
CONF_PRINTER_DEVICE = "printer_device"

DEFAULT_NAME = "Is Around Connector"

SERVICE_SEND_ATTENDANCE = "send_attendance"
SERVICE_PRINT_WEEKLY_SCHEDULE = "print_weekly_schedule"
ATTENDANCE_PUSH_INITIATED_COUNT = "attendance_push_initiated_count"
NEXT_OBSERVANCE_DATE = "next_observance_date"

ATTENDANCE_STATS_TOTAL = "total"
ATTENDANCE_STATS_YES = "yes"
ATTENDANCE_STATS_ARVIT_ONLY = "arvitOnly"
ATTENDANCE_STATS_SHAHARIT_ONLY = "shaharitOnly"
ATTENDANCE_STATS_NO = "no"
ATTENDANCE_STATS_ATTENDING = "attending"

# Event types fired by HA integration (requests to server) - wire protocol,
# shared with is-around (IA) via packages/contract. See contract.py.
EVENT_REQUEST_OBSERVANCES = contract.HA_EVENTS["REQUEST_OBSERVANCES"]
EVENT_REQUEST_PDF = contract.HA_EVENTS["REQUEST_PDF"]
EVENT_REQUEST_ATTENDANCE_PUSH = contract.HA_EVENTS["REQUEST_ATTENDANCE_PUSH"]
EVENT_REQUEST_ATTENDANCE_STATS = contract.HA_EVENTS["REQUEST_ATTENDANCE_STATS"]
EVENT_REQUEST_RESEND = contract.HA_EVENTS["REQUEST_RESEND"]
EVENT_REQUEST_SCHEDULE_PDF = contract.HA_EVENTS["REQUEST_SCHEDULE_PDF"]

# WebSocket command types received from server (responses) - wire protocol.
WS_TYPE_UPDATE_STATE = contract.WS_MESSAGE_TYPES["UPDATE_STATE"]
WS_TYPE_PDF_CHUNK = contract.WS_MESSAGE_TYPES["PDF_CHUNK"]
WS_TYPE_OPERATION_RESULT = contract.WS_MESSAGE_TYPES["OPERATION_RESULT"]

# Response status constants
RESPONSE_STATUS_SUCCESS = "success"
RESPONSE_STATUS_ERROR = "error"

# New sensor data keys - wire protocol, shared with is-around (IA) via
# packages/contract. See contract.py.
WEEKLY_SCHEDULE_DATA = contract.CONNECTOR_DATA_KEYS["WEEKLY_SCHEDULE_DATA"]
LESSONS_DATA = contract.CONNECTOR_DATA_KEYS["LESSONS_DATA"]
MEMORIALS_DATA = contract.CONNECTOR_DATA_KEYS["MEMORIALS_DATA"]
MESSAGES_DATA = contract.CONNECTOR_DATA_KEYS["MESSAGES_DATA"]
LESSON_PROGRAMS_DATA = contract.CONNECTOR_DATA_KEYS["LESSON_PROGRAMS_DATA"]
SEATING_DATA = contract.CONNECTOR_DATA_KEYS["SEATING_DATA"]
SERVICE_TYPES_DATA = contract.CONNECTOR_DATA_KEYS["SERVICE_TYPES_DATA"]

# Services
SERVICE_REQUEST_RESEND = "request_resend"

# Timeout for waiting for responses (seconds)
RESPONSE_TIMEOUT = 30
