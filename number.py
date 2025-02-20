from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import CarChargingProxy, DOMAIN
import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Set up the number platform."""
    entities = [
        entity
        for entity in hass.data[DOMAIN].values()
        if isinstance(entity, CarChargingProxy)
    ]
    _LOGGER.debug(f"Adding charging current entities: {entities}")
    async_add_entities(entities)
