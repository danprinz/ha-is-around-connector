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
