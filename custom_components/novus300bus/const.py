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
CONF_FAN_DEFAULT_PERCENTAGE: Final = "fan_default_percentage"
CONF_FAN_AUTOMATIC_ENTITY: Final = "fan_automatic_entity"
CONF_BOOST_PERCENTAGE: Final = "boost_percentage"
CONF_BOOST_DURATION_MINUTES: Final = "boost_duration_minutes"

DEFAULT_SERIAL_PORT: Final = "/dev/ttyNovus300"
DEFAULT_BAUDRATE: Final = 9600
DEFAULT_PARITY: Final = "none"
DEFAULT_FAN_ENABLED: Final = False
DEFAULT_TINKERFORGE_HOST: Final = "10.0.17.45"
DEFAULT_TINKERFORGE_PORT: Final = 4223
DEFAULT_TINKERFORGE_UID: Final = "Hob"
DEFAULT_FAN_DEFAULT_PERCENTAGE: Final = 60
DEFAULT_FAN_AUTOMATIC_ENTITY: Final = "input_boolean.luftung_automatik"
DEFAULT_BOOST_PERCENTAGE: Final = 75
DEFAULT_BOOST_DURATION_MINUTES: Final = 15

PARITY_OPTIONS: Final = ("none", "mark")
