"""Common fixtures for Tesla Charging Proxy tests."""
import pytest
from unittest.mock import patch, MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.helpers.entity_registry import async_get as get_entity_registry
from homeassistant.const import CONF_PLATFORM

from custom_components.tesla_charging_proxy.const import DOMAIN


@pytest.fixture
async def hass(tmp_path):
    """Return Home Assistant instance with Tesla Charging Proxy component loaded."""
    hass = HomeAssistant(str(tmp_path))
    await hass.async_start()
    hass.config.components.add("teslemetry")  # Mock teslemetry as loaded
    
    # Create mock states for original entities
    hass.states.async_set("number.tessy_charging_current", "10", {
        "friendly_name": "Tessy Charging Current",
        "min": 1,
        "max": 16,
        "step": 1,
        "unit_of_measurement": "A"
    })
    
    hass.states.async_set("switch.tessy_charging_switch", "on", {
        "friendly_name": "Tessy Charging Switch"
    })
    
    return hass


@pytest.fixture
async def mock_config_entry(hass):
    """Create a mock config entry for testing."""
    from homeassistant.config_entries import ConfigEntry
    
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Tesla Charging Proxy",
        data={
            "vehicles": [{
                "vehicle_title": "Tessy",
                "vehicle_slug": "tessy",
                "charging_current_entity": "number.tessy_charging_current",
                "charging_switch_entity": "switch.tessy_charging_switch"
            }]
        },
        source="user",
        entry_id="test_entry_id",
        options={},
        unique_id="test_unique_id",
        # Required for Home Assistant 2025.10.3
        discovery_keys=[],
        minor_version=1,
        subentries_data={},
    )


@pytest.fixture
async def setup_integration(hass, mock_config_entry):
    """Set up the Tesla Charging Proxy integration."""
    from custom_components.tesla_charging_proxy import async_setup_entry
    
    # Mock service calls
    async def async_mock_service_call(domain, service, service_data):
        return True
    
    with patch('homeassistant.core.ServiceRegistry.async_call', 
               side_effect=async_mock_service_call):
        assert await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()
    
    return mock_config_entry
