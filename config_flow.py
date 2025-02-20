"""Config flow for Tesla Charging Proxy integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
  """Handle a config flow for Tesla Charging Proxy."""

  VERSION = 1
  CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

  async def async_step_user(self, user_input=None):
    """Handle the initial step."""
    return await self.async_step_vehicle_select()

  async def async_step_vehicle_select(self, user_input=None):
    """Select the Tesla vehicle."""
    errors = {}
    if user_input is not None:
      self.vehicle_id = user_input["vehicle_id"]
      return await self.async_step_entity_select()

    # Get available Teslemetry devices (using a more robust approach)
    teslemetry_devices = self.hass.config_entries.async_entries("teslemetry")
    if not teslemetry_devices:
      return self.async_abort(reason="no_teslemetry_devices")

    vehicle_options = {}
    for device in teslemetry_devices:
      vehicle_options[device.entry_id] = device.title

    if not vehicle_options:
      return self.async_abort(reason="no_teslemetry_vehicles")

    data_schema = vol.Schema({
      vol.Required("vehicle_id"): vol.In(vehicle_options)
    })

    return self.async_show_form(
      step_id="vehicle_select", data_schema=data_schema, errors=errors
    )

  async def async_step_entity_select(self, user_input=None):
    """Select the entities for the selected vehicle."""
    errors = {}
    if user_input is not None:
      # Get the vehicle name from the selected ID
      vehicle_options = {}
      teslemetry_devices = self.hass.config_entries.async_entries("teslemetry")
      for device in teslemetry_devices:
        vehicle_options[device.entry_id] = device.title
      vehicle_name = vehicle_options.get(self.vehicle_id, "Tesla Charging Proxy")

      user_input["vehicle_name"] = vehicle_name
      user_input["vehicle_id"] = self.vehicle_id  # Save the vehicle ID
      return self.async_create_entry(title=vehicle_name, data=user_input)

    # Get entities related to the selected vehicle
    number_entity_selector = selector.EntitySelector(
      selector.EntitySelectorConfig(domain="number", integration="teslemetry")
    )
    switch_entity_selector = selector.EntitySelector(
      selector.EntitySelectorConfig(domain="switch", integration="teslemetry")
    )

    data_schema = vol.Schema(
      {
        vol.Required("charging_current_entity"): number_entity_selector,
        vol.Required("charging_switch_entity"): switch_entity_selector,
      }
    )

    return self.async_show_form(
      step_id="entity_select", data_schema=data_schema, errors=errors
    )
