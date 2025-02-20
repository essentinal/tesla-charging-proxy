from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from . import CarChargingProxy
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    entities = list(hass.data[DOMAIN].values())
    async_add_entities(entities, True)
