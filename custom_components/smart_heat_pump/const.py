"""Constants for Smart Varmepumpe Styring."""

DOMAIN = "smart_heat_pump"

# Config / options keys
CONF_SENSOR_ENTITY = "sensor_entity"
CONF_HEAT_PUMP_ENTITY = "heat_pump_entity"
CONF_TARGET_TEMP = "target_temp"
CONF_HYSTERESIS = "hysteresis"
CONF_MIN_TIME_BETWEEN_CHANGES = "min_time_between_changes"
CONF_OVERSHOOT = "overshoot"
CONF_ECO_OFFSET = "eco_offset"
CONF_AWAY_TEMP = "away_temp"
CONF_BOOST_TEMP = "boost_temp"

# Defaults
DEFAULT_TARGET_TEMP = 20.0
DEFAULT_HYSTERESIS = 0.5
DEFAULT_MIN_TIME = 30       # minutes
DEFAULT_OVERSHOOT = 2.0     # degrees above target when heating
DEFAULT_ECO_OFFSET = 2.0    # degrees below comfort in eco mode
DEFAULT_AWAY_TEMP = 17.0
DEFAULT_BOOST_TEMP = 24.0
DEFAULT_MAX_SETPOINT = 28.0
DEFAULT_MIN_SETPOINT = 16.0

# Preset names (must match strings.json)
PRESET_COMFORT = "Komfort"
PRESET_ECO = "Økonomi"
PRESET_AWAY = "Borte"
PRESET_BOOST = "Boost"
PRESET_NONE = "Manuell"

ALL_PRESETS = [PRESET_COMFORT, PRESET_ECO, PRESET_AWAY, PRESET_BOOST, PRESET_NONE]
