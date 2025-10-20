import asyncio
import logging
from datetime import timedelta, datetime
from homeassistant.components.number import NumberEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import slugify

try:
  from homeassistant.helpers.entity_registry import async_entity_id_to_device
except ImportError:  # pragma: no cover - compatibility with HA < 2025.10
  async_entity_id_to_device = None
  from homeassistant.helpers.device import async_device_info_to_link_from_entity
else:
  async_device_info_to_link_from_entity = None
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Set up Tesla Charging Proxy from a config entry."""
  hass.data.setdefault(DOMAIN, {})

  entry_data = {
    "numbers": [],
    "switches": [],
  }

  hass.data[DOMAIN][entry.entry_id] = entry_data

  vehicles_config = entry.data.get("vehicles")

  if not vehicles_config:
    vehicle_title = entry.data.get("vehicle_name") or entry.title
    current_entity = entry.data.get("charging_current_entity")
    switch_entity = entry.data.get("charging_switch_entity")
    inferred_slug_source = None
    if current_entity and "." in current_entity:
      inferred_slug_source = current_entity.split(".")[1].split("_")[0]
    vehicle_slug = entry.data.get("vehicle_slug") or slugify(vehicle_title or inferred_slug_source or "tesla")

    vehicles_config = [{
      "vehicle_title": vehicle_title or vehicle_slug.capitalize(),
      "vehicle_slug": vehicle_slug,
      "charging_current_entity": current_entity,
      "charging_switch_entity": switch_entity,
    }]

  for vehicle in vehicles_config:
    vehicle_title = vehicle.get("vehicle_title") or entry.title
    vehicle_slug = vehicle.get("vehicle_slug") or slugify(vehicle_title or "tesla")
    charging_current_entity = vehicle.get("charging_current_entity")
    charging_switch_entity = vehicle.get("charging_switch_entity")

    if not charging_current_entity or not charging_switch_entity:
      _LOGGER.error("Missing entity configuration for vehicle %s", vehicle_title)
      continue

    current_proxy = CarChargingProxy(
      hass,
      vehicle_title,
      vehicle_slug,
      charging_current_entity,
    )
    switch_proxy = CarChargingSwitchProxy(
      hass,
      vehicle_title,
      vehicle_slug,
      charging_switch_entity,
    )

    entry_data["numbers"].append(current_proxy)
    entry_data["switches"].append(switch_proxy)

  await hass.config_entries.async_forward_entry_setups(entry, ["number", "switch"])
  return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Unload a config entry."""
  unload_ok = await hass.config_entries.async_unload_platforms(entry, ["number", "switch"])
  if unload_ok:
    entry_store = hass.data.get(DOMAIN)
    if entry_store:
      entry_store.pop(entry.entry_id, None)
      if not entry_store:
        hass.data.pop(DOMAIN)
  return unload_ok

class CarChargingProxy(NumberEntity):
  def __init__(self, hass, vehicle_title, vehicle_slug, source_entity):
    self.hass = hass
    self._vehicle_title = vehicle_title
    self._vehicle_slug = vehicle_slug
    self._source_entity = source_entity
    self._attr_native_min_value = 1
    self._attr_native_max_value = 16
    self._attr_native_step = 1
    self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    self._attr_mode = "slider"
    self._state = None
    self._desired_current = None
    self._last_update = None
    self._update_task = None
    self._min_update_interval = timedelta(minutes=1)
    self._fast_update_interval = timedelta(seconds=10)
    self._min_current_delta = 1
    self._fast_update_delta = 4
    # find the device id of the source entity
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(source_entity)
    if async_entity_id_to_device:
      self.device_entry = async_entity_id_to_device(hass, source_entity)
    elif async_device_info_to_link_from_entity:
      self._attr_device_info = async_device_info_to_link_from_entity(
        hass,
        source_entity,
      )
    if entity_entry and entity_entry.device_id:
      self._device_id = entity_entry.device_id
    else:
      self._device_id = None
      _LOGGER.debug("Device ID for %s charging current proxy not found", self._vehicle_title)

  @property
  def name(self):
    return f"{self._vehicle_title} Charging Current Proxy"

  @property
  def native_value(self):
    return self._state

  @property
  def unique_id(self):
    if self._device_id:
      return f"{self._device_id}_{self._vehicle_slug}_charging_current_proxy"
    else:
      return f"{self._source_entity}_{self._vehicle_slug}_charging_current_proxy"

  async def async_set_native_value(self, value: float) -> None:
    # Ensure value is within allowed range
    value = max(self._attr_native_min_value, min(self._attr_native_max_value, int(value)))
    # Update state immediately so external systems see the change
    self._state = value
    self._desired_current = value
    self.async_write_ha_state()
    # Schedule the actual API update with buffering
    await self._schedule_update()

  async def async_added_to_hass(self):
    self._update_task = self.hass.loop.create_task(self._update_loop())

    @callback
    async def _async_update_from_original(event):
      if self.hass is None:  # Check if entity is still valid
        _LOGGER.debug("Entity %s charging current proxy is no longer valid, skipping state update.", self._vehicle_title)
        return

      new_state = event.data.get("new_state")
      if new_state:
        try:
          # Ensure the state is an integer
          self._state = int(float(new_state.state)) # Convert to float first in case the original is a string
          self._state = max(self._attr_native_min_value, min(self._attr_native_max_value, self._state))
          self.async_write_ha_state()
        except Exception as e:
          _LOGGER.exception("Error updating state for %s charging current proxy: %s", self._vehicle_title, e)

    self.async_on_remove(
      async_track_state_change_event(
        self.hass, [self._source_entity], _async_update_from_original
      )
    )
    # Initialize state from the original entity
    self._state = await self._get_original_state()

  async def async_will_remove_from_hass(self):
    if self._update_task:
      self._update_task.cancel()


  async def _schedule_update(self):
    if self._update_task:
      self._update_task.cancel()
    self._update_task = self.hass.loop.create_task(self._update_loop())

  async def _update_loop(self):
    while True:
      now = datetime.now()
      # Get the original entity's state to compare with desired state
      original_state = await self._get_original_state()
      if self._desired_current is not None and self._desired_current != original_state:
        current_delta = abs(float(self._desired_current) - float(original_state or 0))
        if current_delta >= self._fast_update_delta:
          await asyncio.sleep(self._fast_update_interval.total_seconds())
        elif self._last_update is None or (now - self._last_update) >= self._min_update_interval:
          if current_delta >= self._min_current_delta:
            await self._update_car_api()
          else:
            await asyncio.sleep(self._min_update_interval.total_seconds())
        else:
          await asyncio.sleep((self._last_update + self._min_update_interval - now).total_seconds())
      else:
        break

  async def _update_car_api(self):
    # We already checked that desired_current != original_state in _update_loop
    await self.hass.services.async_call(
      "number", "set_value",
      {"entity_id": self._source_entity, "value": self._desired_current}
    )
    self._last_update = datetime.now()

  async def _get_original_state(self):
    state = self.hass.states.get(self._source_entity)
    if state and state.state not in ['unavailable', 'unknown']:
      try:
        return int(float(state.state)) #Also ensure original state is an integer
      except ValueError:
        _LOGGER.warning(f"Invalid state value: {state.state}")
        return None
    return None

class CarChargingSwitchProxy(SwitchEntity):
  def __init__(self, hass, vehicle_title, vehicle_slug, source_entity):
    self.hass = hass
    self._vehicle_title = vehicle_title
    self._vehicle_slug = vehicle_slug
    self._source_entity = source_entity
    self._state = None
    self._desired_state = None
    self._last_update = None
    self._update_task = None
    self._min_update_interval = timedelta(minutes=1)
    self._fast_update_interval = timedelta(seconds=10)
    # find the device id of the source entity
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(source_entity)
    if async_entity_id_to_device:
      self.device_entry = async_entity_id_to_device(hass, source_entity)
    elif async_device_info_to_link_from_entity:
      self._attr_device_info = async_device_info_to_link_from_entity(
        hass,
        source_entity,
      )
    if entity_entry and entity_entry.device_id:
      self._device_id = entity_entry.device_id
    else:
      self._device_id = None
      _LOGGER.debug("Device ID for %s charging switch proxy not found", self._vehicle_title)

  @property
  def name(self):
    return f"{self._vehicle_title} Charging Switch Proxy"

  @property
  def is_on(self):
    return self._state

  @property
  def unique_id(self):
    if self._device_id:
      return f"{self._device_id}_{self._vehicle_slug}_charging_switch_proxy"
    else:
      return f"{self._source_entity}_{self._vehicle_slug}_charging_switch_proxy"

  async def async_added_to_hass(self):
    self._update_task = self.hass.loop.create_task(self._update_loop())

    @callback
    async def _async_update_from_original(event):
      if self.hass is None:  # Check if entity is still valid
        _LOGGER.debug(f"Entity {self._name} is no longer valid, skipping state update.")
        return

      new_state = event.data.get("new_state")
      if new_state:
        self._state = new_state.state == "on"
        self.async_write_ha_state()

    self.async_on_remove(
      async_track_state_change_event(
        self.hass, [self._source_entity], _async_update_from_original
      )
    )
    # Initialize state from the original entity
    self._state = await self._get_original_state()

  async def async_will_remove_from_hass(self):
    if self._update_task:
      self._update_task.cancel()

  async def async_turn_on(self, **kwargs):
    await self._set_state(True)

  async def async_turn_off(self, **kwargs):
    await self._set_state(False)

  async def _set_state(self, state):
    if state != self._desired_state:
      # Update state immediately so external systems see the change
      self._desired_state = state
      self._state = state
      self.async_write_ha_state()
      
      # If turning off, check if there's a current proxy we should reset
      if not state:
        await self._reset_current_proxy()
      
      # Schedule the actual API update with buffering
      await self._schedule_update()
      
  async def _reset_current_proxy(self):
    # Find the corresponding current proxy entity
    current_entity_id = f"number.{self._vehicle_slug}_charging_current_proxy"
    current_entity = self.hass.states.get(current_entity_id)
    
    if current_entity is not None:
      # Reset current to minimum (1A) when turning off
      _LOGGER.debug("%s charging switch resetting current to 1A", self._vehicle_title)
      await self.hass.services.async_call(
        "number", "set_value",
        {"entity_id": current_entity_id, "value": 1}
      )

  async def _schedule_update(self):
    if self._update_task:
      self._update_task.cancel()
    self._update_task = self.hass.loop.create_task(self._update_loop())

  async def _update_loop(self):
    while True:
      now = datetime.now()
      # Get the original entity's state to compare with desired state
      original_state = await self._get_original_state()
      if self._desired_state is not None and self._desired_state != original_state:
        if self._last_update is None or (now - self._last_update) >= self._min_update_interval:
          await self._update_car_api()
        else:
          # Wait until the minimum update interval has passed
          await asyncio.sleep((self._last_update + self._min_update_interval - now).total_seconds())
      else:
        break

  async def _update_car_api(self):
    # We already checked that desired_state != original_state in _update_loop
    service = "turn_on" if self._desired_state else "turn_off"
    await self.hass.services.async_call(
      "switch", service,
      {"entity_id": self._source_entity}
    )
    self._last_update = datetime.now()

  async def _get_original_state(self):
    state = self.hass.states.get(self._source_entity)
    return state.state == "on" if state else None
