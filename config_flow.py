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
    errors = {}
    if user_input is not None:
      # Data validation and save configuration
      return self.async_create_entry(title=user_input["name"], data=user_input)

    data_schema = vol.Schema(
      {
        vol.Required("name"): str,
        vol.Required("charging_current_entity"): selector.EntitySelector(
          selector.EntitySelectorConfig(domain="number")
        ),
        vol.Required("charging_switch_entity"): selector.EntitySelector(
          selector.EntitySelectorConfig(domain="switch")
        ),
      }
    )

    return self.async_show_form(
      step_id="user", data_schema=data_schema, errors=errors
    )

  @staticmethod
  @callback
  def async_get_options_flow(config_entry):
    """Get the options flow for this handler."""
    return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
  """Handle options flow for Tesla Charging Proxy."""

  def __init__(self, config_entry):
    """Initialize options flow."""
    self.config_entry = config_entry

  async def async_step_init(self, user_input=None):
    """Manage the options."""
    if user_input is not None:
      return self.async_create_entry(title="", data=user_input)

    options_schema = vol.Schema(
      {
        vol.Required(
          "charging_current_entity",
          default=self.config_entry.options.get("charging_current_entity"),
        ): selector.EntitySelector(
          selector.EntitySelectorConfig(domain="number")
        ),
        vol.Required(
          "charging_switch_entity",
          default=self.config_entry.options.get("charging_switch_entity"),
        ): selector.EntitySelector(
          selector.EntitySelectorConfig(domain="switch")
        ),
      }
    )

    return self.async_show_form(
      step_id="init",
      data_schema=options_schema,
    )
