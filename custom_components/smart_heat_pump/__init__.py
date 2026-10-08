"""Smart Varmepumpe Styring – Home Assistant custom integration."""
from __future__ import annotations

import logging
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]

CARD_JS  = "smart-heat-pump-card.js"
CARD_URL = f"/smart_heat_pump_card/{CARD_JS}"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register the Lovelace card JS as a static resource."""
    www_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "www", CARD_JS)
    )
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, www_path, cache_headers=False)]
    )
    add_extra_js_url(hass, CARD_URL)
    _LOGGER.debug("Registered Lovelace card at %s", CARD_URL)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
