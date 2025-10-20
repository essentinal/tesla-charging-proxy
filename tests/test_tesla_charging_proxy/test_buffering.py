"""Tests for Tesla Charging Proxy buffering behavior."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

import pytest
from homeassistant.const import STATE_ON, STATE_OFF

from custom_components.tesla_charging_proxy import (
    CarChargingProxy,
    CarChargingSwitchProxy
)
from custom_components.tesla_charging_proxy.const import DOMAIN


async def test_switch_buffering(hass, setup_integration):
    """Test that switch commands are properly buffered."""
    entity_id = "switch.tessy_charging_switch_proxy"
    
    # Mock time to control buffering behavior
    original_datetime = datetime
    
    class MockDatetime(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls._mock_now
    
    MockDatetime._mock_now = original_datetime.now()
    
    with patch('custom_components.tesla_charging_proxy.datetime', MockDatetime):
        # Get the proxy entity
        entity_registry = hass.helpers.entity_registry.async_get(hass)
        entry = entity_registry.async_get(entity_id)
        proxy = hass.data["tesla_charging_proxy"][setup_integration.entry_id]["switches"][0]
        
        # Set the minimum update interval
        proxy._min_update_interval = timedelta(seconds=60)
        
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
            assert len(service_calls) == 1
            domain, service, service_data = service_calls[0]
            assert domain == "switch"
            assert service == "turn_off"
            assert service_data.get("entity_id") == "switch.tessy_charging_switch"
            
            # Clear service calls
            service_calls.clear()
            
            # Try to turn on the switch immediately (should be buffered)
            await hass.services.async_call(
                "switch", "turn_on",
                {"entity_id": entity_id},
                blocking=True,
            )
            await hass.async_block_till_done()
            
            # Check that state was updated immediately
            state = hass.states.get(entity_id)
            assert state.state == STATE_ON
            
            # But service call should be buffered (not sent yet)
            assert len(service_calls) == 0
            
            # Advance time by 30 seconds (still within buffer period)
            MockDatetime._mock_now += timedelta(seconds=30)
            await asyncio.sleep(0.1)
            
            # Service call should still be buffered
            assert len(service_calls) == 0
            
            # Advance time by another 30 seconds (buffer period expired)
            MockDatetime._mock_now += timedelta(seconds=30)
            
            # Run the event loop to allow the buffered task to complete
            for _ in range(5):
                await asyncio.sleep(0.1)
            
            # Now the service call should have been made
            assert len(service_calls) == 1
            domain, service, service_data = service_calls[0]
            assert domain == "switch"
            assert service == "turn_on"
            assert service_data.get("entity_id") == "switch.tessy_charging_switch"


async def test_current_buffering(hass, setup_integration):
    """Test that current commands are properly buffered."""
    entity_id = "number.tessy_charging_current_proxy"
    
    # Mock time to control buffering behavior
    original_datetime = datetime
    
    class MockDatetime(datetime):
        @classmethod
        def now(cls, *args, **kwargs):
            return cls._mock_now
    
    MockDatetime._mock_now = original_datetime.now()
    
    with patch('custom_components.tesla_charging_proxy.datetime', MockDatetime):
        # Get the proxy entity
        entity_registry = hass.helpers.entity_registry.async_get(hass)
        entry = entity_registry.async_get(entity_id)
        proxy = hass.data["tesla_charging_proxy"][setup_integration.entry_id]["numbers"][0]
        
        # Set the minimum update interval
        proxy._min_update_interval = timedelta(seconds=60)
        
        # Mock service call
        service_calls = []
        
        async def mock_service_call(domain, service, service_data):
            service_calls.append((domain, service, service_data))
            return True
        
        with patch('homeassistant.core.ServiceRegistry.async_call', 
                   side_effect=mock_service_call):
            # Set current to 12A
            await hass.services.async_call(
                "number", "set_value",
                {"entity_id": entity_id, "value": 12},
                blocking=True,
            )
            await hass.async_block_till_done()
            
            # Check that state was updated immediately
            state = hass.states.get(entity_id)
            assert state.state == "12"
            
            # Check that service call was made to update the original entity
            assert len(service_calls) == 1
            domain, service, service_data = service_calls[0]
            assert domain == "number"
            assert service == "set_value"
            assert service_data.get("entity_id") == "number.tessy_charging_current"
            assert service_data.get("value") == 12
            
            # Clear service calls
            service_calls.clear()
            
            # Try to set current to 8A immediately (should be buffered)
            await hass.services.async_call(
                "number", "set_value",
                {"entity_id": entity_id, "value": 8},
                blocking=True,
            )
            await hass.async_block_till_done()
            
            # Check that state was updated immediately
            state = hass.states.get(entity_id)
            assert state.state == "8"
            
            # But service call should be buffered (not sent yet)
            assert len(service_calls) == 0
            
            # Advance time by 30 seconds (still within buffer period)
            MockDatetime._mock_now += timedelta(seconds=30)
            await asyncio.sleep(0.1)
            
            # Service call should still be buffered
            assert len(service_calls) == 0
            
            # Advance time by another 30 seconds (buffer period expired)
            MockDatetime._mock_now += timedelta(seconds=30)
            
            # Run the event loop to allow the buffered task to complete
            for _ in range(5):
                await asyncio.sleep(0.1)
            
            # Now the service call should have been made
            assert len(service_calls) == 1
            domain, service, service_data = service_calls[0]
            assert domain == "number"
            assert service == "set_value"
            assert service_data.get("entity_id") == "number.tessy_charging_current"
            assert service_data.get("value") == 8


async def test_switch_resets_current(hass, setup_integration):
    """Test that turning off the switch resets the current."""
    switch_entity_id = "switch.tessy_charging_switch_proxy"
    current_entity_id = "number.tessy_charging_current_proxy"
    
    # Set current to a higher value first
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": current_entity_id, "value": 16},
        blocking=True,
    )
    await hass.async_block_till_done()
    
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
            {"entity_id": switch_entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
    
    # Check that current was reset to 1A
    assert any(
        domain == "number" and service == "set_value" and 
        service_data.get("entity_id") == current_entity_id and
        service_data.get("value") == 1
        for domain, service, service_data in service_calls
    )
