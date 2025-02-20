import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CarChargingSwitchProxy, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
  """Set up the switch platform."""
  entities = [
    entity
    for entity in hass.data[DOMAIN].values()
    if isinstance(entity, CarChargingSwitchProxy)
  ]
  _LOGGER.debug(f"Adding switch entities: {entities}")
  async_add_entities(entities)
