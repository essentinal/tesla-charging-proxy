import asyncio
import logging
from datetime import timedelta, datetime

from homeassistant.components.number import NumberEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device import async_device_info_to_link_from_entity
from homeassistant.helpers.event import async_track_state_change_event

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  hass.data[DOMAIN] = {}
  # TODO add dynamic configuration of source entities
  hass.data[DOMAIN]["blacky_current"] = CarChargingProxy(hass, "blacky", "number.blacky_maximaler_ac_ladestrom")
  hass.data[DOMAIN]["tessy_current"] = CarChargingProxy(hass, "tessy", "number.tessy_maximaler_ac_ladestrom")
  hass.data[DOMAIN]["blacky_switch"] = CarChargingSwitchProxy(hass, "blacky", "switch.blacky_laden")
  hass.data[DOMAIN]["tessy_switch"] = CarChargingSwitchProxy(hass, "tessy", "switch.tessy_laden")

  await hass.config_entries.async_forward_entry_setups(entry, ["number", "switch"])
  return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
  """Unload a config entry."""
  unload_ok = await hass.config_entries.async_unload_platforms(entry, ["number", "switch"])

  if unload_ok:
    hass.data[DOMAIN] = {}

  return unload_ok


class CarChargingProxy(NumberEntity):
  def __init__(self, hass, name, source_entity):
    self.hass = hass
    self._name = name
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
    if entity_entry and entity_entry.device_id:
      self._device_id = entity_entry.device_id
      self._attr_device_info = async_device_info_to_link_from_entity(
        hass,
        source_entity,
      )
    else:
      self._device_id = None
      _LOGGER.debug(f"Device ID for {self._name} not found")

  @property
  def name(self):
    return f"{self._name.capitalize()} Charging Current Proxy"

  @property
  def native_value(self):
    return self._state

  @property
  def unique_id(self):
    if self._device_id:
      return f"{self._device_id}_{self._name}_charging_current_proxy"
    else:
      return f"{self._source_entity}_{self._name}_charging_current_proxy"

  async def async_set_native_value(self, value: float) -> None:
    await self.async_set_value(value)

  async def async_added_to_hass(self):
    self._update_task = self.hass.loop.create_task(self._update_loop())

    @callback
    def _async_update_from_original(event):
      new_state = event.data.get("new_state")
      if new_state:
        self._state = float(new_state.state)
        self._state = max(self._attr_native_min_value, min(self._attr_native_max_value, self._state))
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

  async def async_set_native_value(self, value):
    value = max(self._attr_native_min_value, min(self._attr_native_max_value, value))
    if value != self._desired_current:
      self._desired_current = value
      await self._schedule_update()

  async def _schedule_update(self):
    if self._update_task:
      self._update_task.cancel()
    self._update_task = self.hass.loop.create_task(self._update_loop())

  async def _update_loop(self):
    while True:
      now = datetime.now()
      if self._desired_current is not None and self._desired_current != self._state:
        current_delta = abs(float(self._desired_current) - float(self._state or 0))
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
    current_state = await self._get_original_state()
    if self._desired_current != current_state:
      await self.hass.services.async_call(
        "number", "set_value",
        {"entity_id": self._source_entity, "value": self._desired_current}
      )
      self._state = self._desired_current
      self._last_update = datetime.now()
      await self.async_write_ha_state()

  async def _get_original_state(self):
    state = self.hass.states.get(self._source_entity)
    return float(state.state) if state else None


class CarChargingSwitchProxy(SwitchEntity):
  def __init__(self, hass, name, source_entity):
    self.hass = hass
    self._name = name
    self._source_entity = source_entity
    self._state = None
    self._desired_state = None
    self._last_update = None
    self._update_task = None
    self._min_update_interval = timedelta(minutes=1)
    self._fast_update_interval = timedelta(seconds=10)

    # Find the device id of the source entity
    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get(source_entity)
    if entity_entry and entity_entry.device_id:
      self._device_id = entity_entry.device_id
      self._attr_device_info = async_device_info_to_link_from_entity(
        hass,
        source_entity,
      )
    else:
      self._device_id = None
      _LOGGER.debug(f"Device ID for {self._name} charging switch not found")

  @property
  def name(self):
    return f"{self._name.capitalize()} Charging Switch Proxy"

  @property
  def is_on(self):
    return self._state

  @property
  def unique_id(self):
    if self._device_id:
      return f"{self._device_id}_{self._name}_charging_switch_proxy"
    else:
      return f"{self._source_entity}_{self._name}_charging_switch_proxy"

  async def async_added_to_hass(self):
    self._update_task = self.hass.loop.create_task(self._update_loop())

    @callback
    def _async_update_from_original(event):
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
      self._desired_state = state
      await self._schedule_update()

  async def _schedule_update(self):
    if self._update_task:
      self._update_task.cancel()
    self._update_task = self.hass.loop.create_task(self._update_loop())

  async def _update_loop(self):
    while True:
      now = datetime.now()
      if self._desired_state is not None and self._desired_state != self._state:
        if self._last_update is None or (now - self._last_update) >= self._min_update_interval:
          await self._update_car_api()
        else:
          await asyncio.sleep(self._fast_update_interval.total_seconds())
      else:
        break

  async def _update_car_api(self):
    current_state = await self._get_original_state()
    if self._desired_state != current_state:
      service = "turn_on" if self._desired_state else "turn_off"
      await self.hass.services.async_call(
        "switch", service,
        {"entity_id": self._source_entity}
      )
      self._state = self._desired_state
      self._last_update = datetime.now()
      await self.async_write_ha_state()

  async def _get_original_state(self):
    state = self.hass.states.get(self._source_entity)
    return state.state == "on" if state else None
