"""Config flow for Tesla Charging Proxy integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector, entity_registry as er, device_registry as dr
from homeassistant.util import slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
  """Handle a config flow for Tesla Charging Proxy."""

  VERSION = 1

  def __init__(self):
    self._vehicles = []

  async def async_step_user(self, user_input=None):
    """Handle the initial step."""
    return await self.async_step_vehicle()

  async def async_step_vehicle(self, user_input=None):
    """Select the entities for a vehicle."""
    errors = {}

    if user_input is not None:
      if self._is_entity_already_configured(user_input):
        errors["base"] = "already_configured"
      else:
        vehicle_title, vehicle_slug = self._derive_vehicle_details(user_input)
        self._vehicles.append({
          "vehicle_title": vehicle_title,
          "vehicle_slug": vehicle_slug,
          "charging_current_entity": user_input["charging_current_entity"],
          "charging_switch_entity": user_input["charging_switch_entity"],
        })
        return await self.async_step_add_another()

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
      step_id="vehicle", data_schema=data_schema, errors=errors
    )

  async def async_step_add_another(self, user_input=None):
    """Ask if another vehicle should be configured."""
    if user_input is not None:
      if user_input["add_another"]:
        return await self.async_step_vehicle()

      if not self._vehicles:
        return self.async_abort(reason="no_tesla_configured")

      title = ", ".join(vehicle["vehicle_title"] for vehicle in self._vehicles)
      return self.async_create_entry(
        title=title,
        data={"vehicles": self._vehicles},
      )

    data_schema = vol.Schema({
      vol.Required("add_another", default=False): bool
    })

    return self.async_show_form(
      step_id="add_another", data_schema=data_schema
    )

  def _is_entity_already_configured(self, user_input: dict[str, str]) -> bool:
    selected_entities = {
      vehicle["charging_current_entity"]
      for vehicle in self._vehicles
    }
    selected_entities.update(
      vehicle["charging_switch_entity"] for vehicle in self._vehicles
    )

    return (
      user_input["charging_current_entity"] in selected_entities
      or user_input["charging_switch_entity"] in selected_entities
    )

  def _derive_vehicle_details(self, user_input: dict[str, str]) -> tuple[str, str]:
    entity_registry = er.async_get(self.hass)
    device_registry = dr.async_get(self.hass)

    def device_title_from_entity(entity_id: str) -> str | None:
      entity_entry = entity_registry.async_get(entity_id)
      if not entity_entry or not entity_entry.device_id:
        return None
      device_entry = device_registry.async_get(entity_entry.device_id)
      if not device_entry:
        return None
      return device_entry.name_by_user or device_entry.name

    candidate_titles = [
      device_title_from_entity(user_input["charging_current_entity"]),
      device_title_from_entity(user_input["charging_switch_entity"]),
    ]

    title = next((candidate for candidate in candidate_titles if candidate), None)

    current_entity_id = user_input["charging_current_entity"].split(".")[1]
    default_slug_source = current_entity_id.split("_")[0]

    if not title:
      title = default_slug_source.title()

    slug = slugify(title)
    if not slug:
      slug = slugify(default_slug_source)

    return title, slug
