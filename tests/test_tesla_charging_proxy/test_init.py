"""Tests for Tesla Charging Proxy initialization."""
from unittest.mock import patch, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers.entity_registry import async_get as get_entity_registry

from custom_components.tesla_charging_proxy import (
    async_setup_entry,
    async_unload_entry
)
from custom_components.tesla_charging_proxy.const import DOMAIN


async def test_setup_and_unload_entry(hass, mock_config_entry):
    """Test setting up and unloading the integration."""
    # Mock service calls
    async def async_mock_service_call(domain, service, service_data):
        return True
    
    with patch('homeassistant.core.ServiceRegistry.async_call', 
               side_effect=async_mock_service_call):
        # Setup the integration
        assert await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()
        
        # Check that config entry is loaded
        assert mock_config_entry.state == ConfigEntryState.LOADED
        
        # Check that entities were created
        entity_registry = get_entity_registry(hass)
        current_entity = entity_registry.async_get("number.tessy_charging_current_proxy")
        switch_entity = entity_registry.async_get("switch.tessy_charging_switch_proxy")
        
        assert current_entity is not None
        assert switch_entity is not None
        
        # Unload the integration
        assert await async_unload_entry(hass, mock_config_entry)
        await hass.async_block_till_done()
        
        # Check that config entry is unloaded
        assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


async def test_multiple_vehicles(hass):
    """Test setting up the integration with multiple vehicles."""
    from homeassistant.config_entries import ConfigEntry
    
    # Create mock states for original entities
    hass.states.async_set("number.tessy_charging_current", "10", {
        "friendly_name": "Tessy Charging Current"
    })
    hass.states.async_set("switch.tessy_charging_switch", "on", {
        "friendly_name": "Tessy Charging Switch"
    })
    hass.states.async_set("number.blacky_charging_current", "8", {
        "friendly_name": "Blacky Charging Current"
    })
    hass.states.async_set("switch.blacky_charging_switch", "off", {
        "friendly_name": "Blacky Charging Switch"
    })
    
    # Create config entry with multiple vehicles
    mock_config_entry = ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Tesla Charging Proxy",
        data={
            "vehicles": [
                {
                    "vehicle_title": "Tessy",
                    "vehicle_slug": "tessy",
                    "charging_current_entity": "number.tessy_charging_current",
                    "charging_switch_entity": "switch.tessy_charging_switch"
                },
                {
                    "vehicle_title": "Blacky",
                    "vehicle_slug": "blacky",
                    "charging_current_entity": "number.blacky_charging_current",
                    "charging_switch_entity": "switch.blacky_charging_switch"
                }
            ]
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
    
    # Mock service calls
    async def async_mock_service_call(domain, service, service_data):
        return True
    
    with patch('homeassistant.core.ServiceRegistry.async_call', 
               side_effect=async_mock_service_call):
        # Setup the integration
        assert await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()
        
        # Check that entities were created for both vehicles
        tessy_current = hass.states.get("number.tessy_charging_current_proxy")
        tessy_switch = hass.states.get("switch.tessy_charging_switch_proxy")
        blacky_current = hass.states.get("number.blacky_charging_current_proxy")
        blacky_switch = hass.states.get("switch.blacky_charging_switch_proxy")
        
        assert tessy_current is not None
        assert tessy_switch is not None
        assert blacky_current is not None
        assert blacky_switch is not None
        
        # Check that states match the original entities
        assert tessy_current.state == "10"
        assert tessy_switch.state == "on"
        assert blacky_current.state == "8"
        assert blacky_switch.state == "off"
