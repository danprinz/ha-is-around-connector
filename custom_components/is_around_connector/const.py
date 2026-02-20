"""Constants for the Is Around Connector integration."""

DOMAIN = "is_around_connector"

CONF_APP_URL = "app_url"
CONF_PRINTER_ENTITY = (
    "printer_entity"  # Keep for backward compat if needed, or deprecate
)
CONF_PRINTER_DEVICE = "printer_device"

DEFAULT_NAME = "Is Around Connector"

SERVICE_SEND_ATTENDANCE = "send_attendance"
ATTENDANCE_PUSH_INITIATED_COUNT = "attendance_push_initiated_count"
NEXT_OBSERVANCE_DATE = "next_observance_date"

ATTENDANCE_STATS_TOTAL = "total"
ATTENDANCE_STATS_YES = "yes"
ATTENDANCE_STATS_ARVIT_ONLY = "arvitOnly"
ATTENDANCE_STATS_SHAHARIT_ONLY = "shaharitOnly"
ATTENDANCE_STATS_NO = "no"
ATTENDANCE_STATS_ATTENDING = "attending"

# Event types fired by HA integration (requests to server)
EVENT_REQUEST_OBSERVANCES = "is_around_connector_request_observances"
EVENT_REQUEST_PDF = "is_around_connector_request_pdf"
EVENT_REQUEST_ATTENDANCE_PUSH = "is_around_connector_request_attendance_push"
EVENT_REQUEST_ATTENDANCE_STATS = "is_around_connector_request_attendance_stats"
EVENT_REQUEST_RESEND = "is_around_connector_request_resend"

# WebSocket command types received from server (responses)
WS_TYPE_UPDATE_STATE = "is_around/update_state"
WS_TYPE_PDF_CHUNK = "is_around/pdf_chunk"
WS_TYPE_OPERATION_RESULT = "is_around/operation_result"

# Response status constants
RESPONSE_STATUS_SUCCESS = "success"
RESPONSE_STATUS_ERROR = "error"

# New sensor data keys
WEEKLY_SCHEDULE_DATA = "weekly_schedule_data"
LESSONS_DATA = "lessons_data"
MEMORIALS_DATA = "memorials_data"
MESSAGES_DATA = "messages_data"

# Services
SERVICE_REQUEST_RESEND = "request_resend"

# Timeout for waiting for responses (seconds)
RESPONSE_TIMEOUT = 30
