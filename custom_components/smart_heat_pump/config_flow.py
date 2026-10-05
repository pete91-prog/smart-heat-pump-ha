"""Config flow for Smart Varmepumpe Styring."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er, selector

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


def _entity_selector(domain: str) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain=domain, multiple=False)
    )


STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="Smart Varmepumpe"): str,
        vol.Required(CONF_SENSOR_ENTITY): _entity_selector(SENSOR_DOMAIN),
        vol.Required(CONF_HEAT_PUMP_ENTITY): _entity_selector(CLIMATE_DOMAIN),
        vol.Optional(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=15, max=25, step=0.5, unit_of_measurement="°C")
        ),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=15, max=25, step=0.5, unit_of_measurement="°C", mode="slider")
        ),
        vol.Optional(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.2, max=3.0, step=0.1, unit_of_measurement="°C", mode="slider")
        ),
        vol.Optional(CONF_MIN_TIME_BETWEEN_CHANGES, default=DEFAULT_MIN_TIME): selector.NumberSelector(
            selector.NumberSelectorConfig(min=5, max=180, step=5, unit_of_measurement="min", mode="slider")
        ),
        vol.Optional(CONF_OVERSHOOT, default=DEFAULT_OVERSHOOT): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.5, max=4.0, step=0.5, unit_of_measurement="°C", mode="slider")
        ),
        vol.Optional(CONF_ECO_OFFSET, default=DEFAULT_ECO_OFFSET): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.5, max=5.0, step=0.5, unit_of_measurement="°C", mode="slider")
        ),
        vol.Optional(CONF_AWAY_TEMP, default=DEFAULT_AWAY_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=14, max=20, step=0.5, unit_of_measurement="°C", mode="slider")
        ),
        vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): selector.NumberSelector(
            selector.NumberSelectorConfig(min=20, max=28, step=0.5, unit_of_measurement="°C", mode="slider")
        ),
    }
)


class SmartHeatPumpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Smart Varmepumpe Styring."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            sensor = user_input[CONF_SENSOR_ENTITY]
            heat_pump = user_input[CONF_HEAT_PUMP_ENTITY]

            if sensor == heat_pump:
                errors["base"] = "same_entity"
            else:
                # Unique entry per heat pump entity
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
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "SmartHeatPumpOptionsFlow":
        """Return the options flow handler."""
        return SmartHeatPumpOptionsFlow(config_entry)


class SmartHeatPumpOptionsFlow(config_entries.OptionsFlow):
    """Handle options (settings after initial setup)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options form."""
        merged = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TARGET_TEMP,
                    default=merged.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=15, max=25, step=0.5, unit_of_measurement="°C", mode="slider")
                ),
                vol.Optional(
                    CONF_HYSTERESIS,
                    default=merged.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.2, max=3.0, step=0.1, unit_of_measurement="°C", mode="slider")
                ),
                vol.Optional(
                    CONF_MIN_TIME_BETWEEN_CHANGES,
                    default=merged.get(CONF_MIN_TIME_BETWEEN_CHANGES, DEFAULT_MIN_TIME),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=180, step=5, unit_of_measurement="min", mode="slider")
                ),
                vol.Optional(
                    CONF_OVERSHOOT,
                    default=merged.get(CONF_OVERSHOOT, DEFAULT_OVERSHOOT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.5, max=4.0, step=0.5, unit_of_measurement="°C", mode="slider")
                ),
                vol.Optional(
                    CONF_ECO_OFFSET,
                    default=merged.get(CONF_ECO_OFFSET, DEFAULT_ECO_OFFSET),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0.5, max=5.0, step=0.5, unit_of_measurement="°C", mode="slider")
                ),
                vol.Optional(
                    CONF_AWAY_TEMP,
                    default=merged.get(CONF_AWAY_TEMP, DEFAULT_AWAY_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=14, max=20, step=0.5, unit_of_measurement="°C", mode="slider")
                ),
                vol.Optional(
                    CONF_BOOST_TEMP,
                    default=merged.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=20, max=28, step=0.5, unit_of_measurement="°C", mode="slider")
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
