"""Config flow for Smart Varmepumpe Styring."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
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
    DEFAULT_MIN_TIME,
    DEFAULT_OVERSHOOT,
    DEFAULT_TARGET_TEMP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _climate_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=CLIMATE_DOMAIN, multiple=False)
    )


def _sensor_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=SENSOR_DOMAIN, multiple=False)
    )


def _num(min_v, max_v, step, unit, mode="box") -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_v, max=max_v, step=step, unit_of_measurement=unit, mode=mode
        )
    )


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Smart Varmepumpe"): str,
        vol.Required(CONF_SENSOR_ENTITY): _sensor_selector(),
        vol.Required(CONF_HEAT_PUMP_ENTITY): _climate_selector(),
        vol.Optional(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP): _num(
            15, 25, 0.5, "°C"
        ),
    }
)


class SmartHeatPumpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Varmepumpe Styring."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            sensor    = user_input[CONF_SENSOR_ENTITY]
            heat_pump = user_input[CONF_HEAT_PUMP_ENTITY]

            if sensor == heat_pump:
                errors["base"] = "same_entity"
            else:
                await self.async_set_unique_id(heat_pump)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=user_input["name"],
                    data={
                        "name": user_input["name"],
                        CONF_SENSOR_ENTITY: sensor,
                        CONF_HEAT_PUMP_ENTITY: heat_pump,
                        CONF_TARGET_TEMP: user_input.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP),
                        CONF_HYSTERESIS: DEFAULT_HYSTERESIS,
                        CONF_MIN_TIME_BETWEEN_CHANGES: DEFAULT_MIN_TIME,
                        CONF_OVERSHOOT: DEFAULT_OVERSHOOT,
                        CONF_ECO_OFFSET: DEFAULT_ECO_OFFSET,
                        CONF_AWAY_TEMP: DEFAULT_AWAY_TEMP,
                        CONF_BOOST_TEMP: DEFAULT_BOOST_TEMP,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SmartHeatPumpOptionsFlow":
        return SmartHeatPumpOptionsFlow(config_entry)


class SmartHeatPumpOptionsFlow(config_entries.OptionsFlow):
    """Options flow – change all settings including connected entities."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        merged = {**self._config_entry.data, **self._config_entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            if user_input[CONF_SENSOR_ENTITY] == user_input[CONF_HEAT_PUMP_ENTITY]:
                errors["base"] = "same_entity"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HEAT_PUMP_ENTITY,
                    default=merged.get(CONF_HEAT_PUMP_ENTITY, ""),
                ): _climate_selector(),
                vol.Required(
                    CONF_SENSOR_ENTITY,
                    default=merged.get(CONF_SENSOR_ENTITY, ""),
                ): _sensor_selector(),
                vol.Optional(
                    CONF_TARGET_TEMP,
                    default=merged.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP),
                ): _num(15, 25, 0.5, "°C", "slider"),
                vol.Optional(
                    CONF_AWAY_TEMP,
                    default=merged.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP),
                ): _num(14, 20, 0.5, "°C", "slider"),
                vol.Optional(
                    CONF_BOOST_TEMP,
                    default=merged.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP),
                ): _num(20, 28, 0.5, "°C", "slider"),
                vol.Optional(
                    CONF_HYSTERESIS,
                    default=merged.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS),
                ): _num(0.2, 3.0, 0.1, "°C", "slider"),
                vol.Optional(
                    CONF_MIN_TIME_BETWEEN_CHANGES,
                    default=merged.get(CONF_MIN_TIME_BETWEEN_CHANGES, DEFAULT_MIN_TIME),
                ): _num(5, 180, 5, "min", "slider"),
                vol.Optional(
                    CONF_OVERSHOOT,
                    default=merged.get(CONF_OVERSHOOT, DEFAULT_OVERSHOOT),
                ): _num(0.5, 4.0, 0.5, "°C", "slider"),
                vol.Optional(
                    CONF_ECO_OFFSET,
                    default=merged.get(CONF_ECO_OFFSET, DEFAULT_ECO_OFFSET),
                ): _num(0.5, 5.0, 0.5, "°C", "slider"),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
