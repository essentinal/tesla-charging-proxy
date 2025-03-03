from homeassistant import config_entries

from .const import DOMAIN


class TeslaChargingProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
  VERSION = 1

  async def async_step_user(self, user_input=None):
    if self._async_current_entries():
      return self.async_abort(reason="single_instance_allowed")
    return self.async_create_entry(title="Tesla Charging Proxy", data={})
