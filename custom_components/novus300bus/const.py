"""Constants for the Paul Novus 300 bus integration."""

from typing import Final

DOMAIN: Final = "novus300bus"

CONF_SERIAL_PORT: Final = "serial_port"
CONF_BAUDRATE: Final = "baudrate"
CONF_PARITY: Final = "parity"

DEFAULT_SERIAL_PORT: Final = "/dev/ttyNovus300"
DEFAULT_BAUDRATE: Final = 9600
DEFAULT_PARITY: Final = "none"

PARITY_OPTIONS: Final = ("none", "mark")
