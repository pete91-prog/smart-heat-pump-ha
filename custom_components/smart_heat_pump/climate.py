"""Climate platform – Smart Varmepumpe Styring.

Wraps an existing heat pump climate entity and controls it using an
external temperature sensor (e.g. a Zigbee thermometer) with:

  • Configurable hysteresis / dead band – setpoint only changes when the
    measured room temperature is outside target ± hysteresis.
  • Minimum cooldown between changes – prevents rapid back-and-forth.
  • Emergency override – if deviation exceeds 2 × hysteresis the cooldown
    is skipped so the room is not left uncomfortably cold/hot.
  • Preset modes: Komfort, Økonomi, Borte, Boost, Manuell.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    ALL_PRESETS,
    CONF_AWAY_TEMP,
    CONF_BOOST_TEMP,
    CONF_ECO_OFFSET,
    CONF_HEAT_PUMP_ENTITY,
    CONF_HYSTERESIS,
    CONF_MIN_TIME_BETWEEN_CHANGES,
    CONF_OVERSHOOT,
    CONF_SENSOR_ENTITY,
    CONF_TARGET_TEMP,
    DEFAULT_AWAY_TEMP,
    DEFAULT_BOOST_TEMP,
    DEFAULT_ECO_OFFSET,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_SETPOINT,
    DEFAULT_MIN_SETPOINT,
    DEFAULT_MIN_TIME,
    DEFAULT_OVERSHOOT,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate entity from a config entry."""
    merged = {**entry.data, **entry.options}

    entity = SmartHeatPump(
        hass=hass,
        name=entry.data.get("name", "Smart Varmepumpe"),
        unique_id=entry.entry_id,
        sensor_entity_id=merged[CONF_SENSOR_ENTITY],
        heat_pump_entity_id=merged[CONF_HEAT_PUMP_ENTITY],
        target_temp=merged.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP),
        hysteresis=merged.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS),
        min_time_minutes=merged.get(CONF_MIN_TIME_BETWEEN_CHANGES, DEFAULT_MIN_TIME),
        overshoot=merged.get(CONF_OVERSHOOT, DEFAULT_OVERSHOOT),
        eco_offset=merged.get(CONF_ECO_OFFSET, DEFAULT_ECO_OFFSET),
        away_temp=merged.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP),
        boost_temp=merged.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP),
    )
    async_add_entities([entity])


class SmartHeatPump(ClimateEntity, RestoreEntity):
    """Smart thermostat that controls a heat pump via an external sensor."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_target_temperature_min = 15.0
    _attr_target_temperature_max = 25.0
    _attr_preset_modes = ALL_PRESETS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        sensor_entity_id: str,
        heat_pump_entity_id: str,
        target_temp: float,
        hysteresis: float,
        min_time_minutes: int,
        overshoot: float,
        eco_offset: float,
        away_temp: float,
        boost_temp: float,
    ) -> None:
        self.hass = hass
        self._attr_unique_id = unique_id
        self._attr_device_info = None

        # Friendly name shown in the UI
        self._display_name = name

        self._sensor_entity_id = sensor_entity_id
        self._heat_pump_entity_id = heat_pump_entity_id

        # User-facing target temperature (for PRESET_COMFORT / PRESET_ECO)
        self._comfort_temp: float = float(target_temp)

        # Control parameters
        self._hysteresis: float = float(hysteresis)
        self._min_time: timedelta = timedelta(minutes=int(min_time_minutes))
        self._overshoot: float = float(overshoot)
        self._eco_offset: float = float(eco_offset)
        self._away_temp: float = float(away_temp)
        self._boost_temp: float = float(boost_temp)

        # Runtime state
        self._current_temperature: float | None = None
        self._hvac_mode: HVACMode = HVACMode.HEAT
        self._preset_mode: str = PRESET_COMFORT
        self._last_change: datetime | None = None

    # ──────────────────────────────────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._display_name

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        hp_state = self.hass.states.get(self._heat_pump_entity_id)
        if hp_state and hp_state.attributes.get("hvac_action"):
            return hp_state.attributes["hvac_action"]
        current = self._current_temperature
        if current is None:
            return HVACAction.IDLE
        return HVACAction.HEATING if current < self._effective_target() else HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        return self._current_temperature

    @property
    def target_temperature(self) -> float:
        return self._effective_target()

    @property
    def preset_mode(self) -> str:
        return self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        minutes_since = None
        if self._last_change is not None:
            delta = dt_util.now() - self._last_change
            minutes_since = round(delta.total_seconds() / 60, 1)
        return {
            "hysteresis": self._hysteresis,
            "min_time_between_changes_min": self._min_time.total_seconds() / 60,
            "overshoot": self._overshoot,
            "comfort_target": self._comfort_temp,
            "sensor_entity": self._sensor_entity_id,
            "heat_pump_entity": self._heat_pump_entity_id,
            "minutes_since_last_change": minutes_since,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Setup and teardown
    # ──────────────────────────────────────────────────────────────────────

    async def async_added_to_hass(self) -> None:
        """Restore previous state and register event listeners."""
        await super().async_added_to_hass()

        # Restore persisted state
        if (last := await self.async_get_last_state()) is not None:
            self._hvac_mode = HVACMode(last.state) if last.state in (HVACMode.HEAT, HVACMode.OFF) else HVACMode.HEAT
            attrs = last.attributes
            if preset := attrs.get("preset_mode"):
                self._preset_mode = preset
            if comfort := attrs.get("comfort_target"):
                self._comfort_temp = float(comfort)
            if last_change := attrs.get("last_change_iso"):
                try:
                    self._last_change = datetime.fromisoformat(last_change)
                except ValueError:
                    pass

        # Track sensor changes
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._sensor_entity_id], self._async_sensor_changed
            )
        )

        # Periodic fallback poll (every 5 minutes)
        self.async_on_remove(
            async_track_time_interval(self.hass, self._async_periodic_check, POLL_INTERVAL)
        )

        # Run once after HA has fully started
        @callback
        def _on_start(event: Event) -> None:
            self.hass.async_create_task(self._async_control())

        if self.hass.is_running:
            await self._async_control()
        else:
            self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _on_start)

    # ──────────────────────────────────────────────────────────────────────
    # Callbacks
    # ──────────────────────────────────────────────────────────────────────

    @callback
    def _async_sensor_changed(self, event: Event) -> None:
        """Handle temperature sensor state updates."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            _LOGGER.debug("Sensor %s unavailable – skipping control cycle", self._sensor_entity_id)
            return
        try:
            self._current_temperature = float(new_state.state)
        except ValueError:
            return
        self.async_write_ha_state()
        self.hass.async_create_task(self._async_control())

    @callback
    def _async_periodic_check(self, _now: datetime) -> None:
        """Periodic check in case sensor events were missed."""
        sensor_state = self.hass.states.get(self._sensor_entity_id)
        if sensor_state and sensor_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            try:
                self._current_temperature = float(sensor_state.state)
            except ValueError:
                pass
        self.hass.async_create_task(self._async_control())

    # ──────────────────────────────────────────────────────────────────────
    # Service calls from HA
    # ──────────────────────────────────────────────────────────────────────

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the virtual thermostat on or off."""
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            await self._async_set_heat_pump_mode(HVACMode.OFF)
        self.async_write_ha_state()
        await self._async_control()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Change operating preset."""
        if preset_mode not in ALL_PRESETS:
            _LOGGER.warning("Unknown preset: %s", preset_mode)
            return
        self._preset_mode = preset_mode
        self.async_write_ha_state()

        if preset_mode == PRESET_NONE:
            # Manual mode: do nothing, user controls the heat pump directly
            return

        # Immediate action for Borte / Boost – bypass cooldown
        if preset_mode in (PRESET_AWAY, PRESET_BOOST):
            await self._async_apply_setpoint(self._effective_target(), bypass_cooldown=True)
        else:
            # Reset cooldown so the normal loop acts immediately
            self._last_change = None
            await self._async_control()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new comfort target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._comfort_temp = float(temp)
        # Reset cooldown so the change takes effect immediately
        self._last_change = None
        self.async_write_ha_state()
        await self._async_control()

    # ──────────────────────────────────────────────────────────────────────
    # Core hysteresis control logic
    # ──────────────────────────────────────────────────────────────────────

    async def _async_control(self) -> None:
        """Evaluate room temperature and decide whether to adjust the heat pump."""
        if self._hvac_mode == HVACMode.OFF or self._preset_mode == PRESET_NONE:
            return

        current = self._current_temperature
        if current is None:
            _LOGGER.debug("No temperature reading yet – skipping control cycle")
            return

        target = self._effective_target()
        deviation = current - target
        abs_dev = abs(deviation)
        emergency = abs_dev > (self._hysteresis * 2)

        # Cooldown check
        cooldown_elapsed = (
            self._last_change is None
            or (dt_util.now() - self._last_change) >= self._min_time
        )

        if not emergency and not cooldown_elapsed:
            _LOGGER.debug(
                "Within cooldown (%.0f min remaining). Temp=%.1f Target=%.1f Dev=%.2f",
                (self._min_time - (dt_util.now() - self._last_change)).total_seconds() / 60,
                current,
                target,
                deviation,
            )
            return

        # Dead-band check
        if abs_dev <= self._hysteresis:
            _LOGGER.debug(
                "Inside dead band (±%.1f°C). Temp=%.1f Target=%.1f – no action",
                self._hysteresis,
                current,
                target,
            )
            return

        if deviation < 0:
            # Room is colder than (target − hysteresis) → heat
            new_setpoint = min(target + self._overshoot, DEFAULT_MAX_SETPOINT)
            _LOGGER.info(
                "Heating: room %.1f°C < target %.1f°C − %.1f. Setting HP to %.1f°C",
                current,
                target,
                self._hysteresis,
                new_setpoint,
            )
            await self._async_apply_setpoint(new_setpoint)
        else:
            # Room is warmer than (target + hysteresis) → pull back
            new_setpoint = max(target - 1.0, DEFAULT_MIN_SETPOINT)
            _LOGGER.info(
                "Pulling back: room %.1f°C > target %.1f°C + %.1f. Setting HP to %.1f°C",
                current,
                target,
                self._hysteresis,
                new_setpoint,
            )
            await self._async_apply_setpoint(new_setpoint)

    async def _async_apply_setpoint(
        self, setpoint: float, bypass_cooldown: bool = False
    ) -> None:
        """Send setpoint to the real heat pump entity."""
        try:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": self._heat_pump_entity_id,
                    "temperature": round(setpoint, 1),
                    "hvac_mode": HVACMode.HEAT,
                },
                blocking=True,
            )
            self._last_change = dt_util.now()
            self.async_write_ha_state()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to set temperature on %s", self._heat_pump_entity_id)

    async def _async_set_heat_pump_mode(self, mode: HVACMode) -> None:
        """Set HVAC mode on the real heat pump."""
        try:
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": self._heat_pump_entity_id, "hvac_mode": mode},
                blocking=True,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to set HVAC mode on %s", self._heat_pump_entity_id)

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _effective_target(self) -> float:
        """Return the actual target temperature for the current preset."""
        if self._preset_mode == PRESET_ECO:
            return round(self._comfort_temp - self._eco_offset, 1)
        if self._preset_mode == PRESET_AWAY:
            return self._away_temp
        if self._preset_mode == PRESET_BOOST:
            return self._boost_temp
        return self._comfort_temp  # PRESET_COMFORT or PRESET_NONE
