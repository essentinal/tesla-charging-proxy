"""Tests for Tesla Charging Proxy entities."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

import pytest
from homeassistant.const import STATE_ON, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as get_entity_registry

from custom_components.tesla_charging_proxy import (
    CarChargingProxy,
    CarChargingSwitchProxy
)
from custom_components.tesla_charging_proxy.const import DOMAIN


async def test_charging_current_proxy_creation(hass, setup_integration):
    """Test that the charging current proxy entity is created correctly."""
    entity_id = "number.tessy_charging_current_proxy"
    state = hass.states.get(entity_id)
    
    # Check that entity exists and has correct attributes
    assert state is not None
    assert state.state == "10"  # Should match the original entity's state
    assert state.attributes.get("min") == 1
    assert state.attributes.get("max") == 16
    assert state.attributes.get("step") == 1
    assert state.attributes.get("unit_of_measurement") == "A"
    assert state.attributes.get("mode") == "slider"


async def test_charging_switch_proxy_creation(hass, setup_integration):
    """Test that the charging switch proxy entity is created correctly."""
    entity_id = "switch.tessy_charging_switch_proxy"
    state = hass.states.get(entity_id)
    
    # Check that entity exists and has correct state
    assert state is not None
    assert state.state == STATE_ON  # Should match the original entity's state


async def test_charging_current_proxy_set_value(hass, setup_integration):
    """Test setting a value on the charging current proxy."""
    entity_id = "number.tessy_charging_current_proxy"
    
    # Mock service call
    service_calls = []
    
    async def mock_service_call(domain, service, service_data):
        service_calls.append((domain, service, service_data))
        return True
    
    with patch('homeassistant.core.ServiceRegistry.async_call', 
               side_effect=mock_service_call):
        # Set a new value
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": entity_id, "value": 8},
            blocking=True,
        )
        await hass.async_block_till_done()
    
    # Check that state was updated immediately
    state = hass.states.get(entity_id)
    assert state.state == "8"
    
    # Check that service call was made to update the original entity
    # (This might be delayed due to buffering, so we need to wait)
    await asyncio.sleep(0.1)
    assert any(
        domain == "number" and service == "set_value" and 
        service_data.get("entity_id") == "number.tessy_charging_current" and
        service_data.get("value") == 8
        for domain, service, service_data in service_calls
    )


async def test_charging_switch_proxy_toggle(hass, setup_integration):
    """Test toggling the charging switch proxy."""
    entity_id = "switch.tessy_charging_switch_proxy"
    
    # Mock service call
    service_calls = []
    
    async def mock_service_call(domain, service, service_data):
        service_calls.append((domain, service, service_data))
        return True
    
    with patch('homeassistant.core.ServiceRegistry.async_call', 
               side_effect=mock_service_call):
        # Turn off the switch
        await hass.services.async_call(
            "switch", "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
    
    # Check that state was updated immediately
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    
    # Check that service call was made to update the original entity
    # (This might be delayed due to buffering, so we need to wait)
    await asyncio.sleep(0.1)
    assert any(
        domain == "switch" and service == "turn_off" and 
        service_data.get("entity_id") == "switch.tessy_charging_switch"
        for domain, service, service_data in service_calls
    )
    
    # Check that current was reset to 1A
    assert any(
        domain == "number" and service == "set_value" and 
        service_data.get("entity_id") == "number.tessy_charging_current_proxy" and
        service_data.get("value") == 1
        for domain, service, service_data in service_calls
    )


async def test_buffering_behavior(hass, setup_integration):
    """Test that commands are properly buffered."""
    switch_entity_id = "switch.tessy_charging_switch_proxy"
    current_entity_id = "number.tessy_charging_current_proxy"
    
    # Mock service call
    service_calls = []
    
    async def mock_service_call(domain, service, service_data):
        service_calls.append((domain, service, service_data))
        # Update the original entity state to simulate the API response
        if domain == "switch":
            original_entity_id = "switch.tessy_charging_switch"
            new_state = STATE_ON if service == "turn_on" else STATE_OFF
            hass.states.async_set(original_entity_id, new_state)
        elif domain == "number":
            original_entity_id = "number.tessy_charging_current"
            new_value = service_data.get("value")
            hass.states.async_set(original_entity_id, str(new_value))
        return True
    
    with patch('homeassistant.core.ServiceRegistry.async_call', 
               side_effect=mock_service_call):
        # Turn on the switch
        await hass.services.async_call(
            "switch", "turn_on",
            {"entity_id": switch_entity_id},
            blocking=True,
        )
        
        # Set current to 16A
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": current_entity_id, "value": 16},
            blocking=True,
        )
        
        # Immediately try to set current to 8A (should be buffered)
        await hass.services.async_call(
            "number", "set_value",
            {"entity_id": current_entity_id, "value": 8},
            blocking=True,
        )
        
        # Check that state was updated immediately for both entities
        switch_state = hass.states.get(switch_entity_id)
        current_state = hass.states.get(current_entity_id)
        assert switch_state.state == STATE_ON
        assert current_state.state == "8"  # Should reflect the latest command
        
        # Check service calls - should only have 1 call to turn_on and 1 call to set_value to 16
        # The second set_value (to 8) should be buffered
        switch_calls = [call for domain, service, _ in service_calls if domain == "switch"]
        current_calls = [call for domain, service, _ in service_calls if domain == "number"]
        assert len(switch_calls) == 1  # Only one switch call
        assert len(current_calls) <= 2  # At most 2 current calls (might be 1 if heavily buffered)
        
        # Wait for buffering period to complete
        await asyncio.sleep(1)
        
        # Now the buffered command should be sent
        assert any(
            domain == "number" and service == "set_value" and 
            service_data.get("entity_id") == "number.tessy_charging_current" and
            service_data.get("value") == 8
            for domain, service, service_data in service_calls
        )
