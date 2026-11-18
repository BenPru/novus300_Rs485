"""Constants for the Paul Novus 300 bus integration."""

from typing import Final

DOMAIN: Final = "novus300bus"

CONF_SERIAL_PORT: Final = "serial_port"
CONF_BAUDRATE: Final = "baudrate"
CONF_PARITY: Final = "parity"
CONF_FAN_ENABLED: Final = "fan_enabled"
CONF_TINKERFORGE_HOST: Final = "tinkerforge_host"
CONF_TINKERFORGE_PORT: Final = "tinkerforge_port"
CONF_TINKERFORGE_UID: Final = "tinkerforge_uid"
CONF_FAN_AUTOMATIC_ENTITY: Final = "fan_automatic_entity"
CONF_DAILY_TIME_SYNC: Final = "daily_time_sync"
CONF_SHOW_FAN_LEVELS: Final = "show_fan_levels"
DEFAULT_SHOW_FAN_LEVELS: Final = False
CONF_FILTER_INTERVAL_DAYS: Final = "filter_interval_days"
DEFAULT_FILTER_INTERVAL_DAYS: Final = 90
CONF_BOOST_DURATION_MINUTES: Final = "boost_duration_minutes"
CONF_AWAY_DURATION_MINUTES: Final = "away_duration_minutes"
CONF_FAN_LEVEL_1_PERCENTAGE: Final = "fan_level_1_percentage"
CONF_FAN_LEVEL_2_PERCENTAGE: Final = "fan_level_2_percentage"
CONF_FAN_LEVEL_3_PERCENTAGE: Final = "fan_level_3_percentage"

DEFAULT_SERIAL_PORT: Final = "/dev/ttyNovus300"
DEFAULT_BAUDRATE: Final = 9600
DEFAULT_PARITY: Final = "none"
DEFAULT_FAN_ENABLED: Final = False
DEFAULT_TINKERFORGE_HOST: Final = "10.0.17.45"
DEFAULT_TINKERFORGE_PORT: Final = 4223
DEFAULT_TINKERFORGE_UID: Final = "Hob"
DEFAULT_FAN_AUTOMATIC_ENTITY: Final = "input_boolean.luftung_automatik"
DEFAULT_DAILY_TIME_SYNC: Final = True
DEFAULT_BOOST_DURATION_MINUTES: Final = 15
DEFAULT_AWAY_DURATION_MINUTES: Final = 30
DEFAULT_FAN_LEVEL_1_PERCENTAGE: Final = 35
DEFAULT_FAN_LEVEL_2_PERCENTAGE: Final = 60
DEFAULT_FAN_LEVEL_3_PERCENTAGE: Final = 90

DAILY_TIME_SYNC_HOUR: Final = 3

PARITY_OPTIONS: Final = ("none", "mark")
