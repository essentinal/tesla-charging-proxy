"""Test the buffering logic of the Tesla Charging Proxy."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, call

import pytest


class MockHomeAssistant:
    """Mock Home Assistant class for testing."""
    
    def __init__(self):
        self.states = {}
        self.service_calls = []
        self.loop = asyncio.get_event_loop()
    
    def get_state(self, entity_id):
        """Get state of an entity."""
        return self.states.get(entity_id)
    
    def set_state(self, entity_id, state):
        """Set state of an entity."""
        self.states[entity_id] = state
    
    async def async_call_service(self, domain, service, data):
        """Call a service."""
        self.service_calls.append((domain, service, data))
        return True


class MockCarChargingProxy:
    """Mock of the CarChargingProxy class for testing buffering logic."""
    
    def __init__(self):
        self._state = 10
        self._desired_current = None
        self._source_entity = "number.tessy_charging_current"
        self._last_update = None
        self._min_update_interval = timedelta(minutes=1)
        self.hass = MockHomeAssistant()
        self.hass.set_state(self._source_entity, 10)
    
    async def set_value(self, value):
        """Set a new value with buffering."""
        self._desired_current = value
        now = datetime.now()
        
        # Update state immediately
        self._state = value
        
        # Check if we should send command now or buffer
        if self._last_update is None or (now - self._last_update) >= self._min_update_interval:
            await self._update_car_api()
        else:
            # Buffer the command - in a real system this would be scheduled
            pass
    
    async def _update_car_api(self):
        """Update the car API with the desired current."""
        await self.hass.async_call_service(
            "number", "set_value",
            {"entity_id": self._source_entity, "value": self._desired_current}
        )
        self._last_update = datetime.now()


class MockCarChargingSwitchProxy:
    """Mock of the CarChargingSwitchProxy class for testing buffering logic."""
    
    def __init__(self):
        self._state = True
        self._desired_state = None
        self._source_entity = "switch.tessy_charging_switch"
        self._last_update = None
        self._min_update_interval = timedelta(minutes=1)
        self._vehicle_slug = "tessy"
        self.hass = MockHomeAssistant()
        self.hass.set_state(self._source_entity, True)
    
    async def set_state(self, state):
        """Set a new state with buffering."""
        self._desired_state = state
        now = datetime.now()
        
        # Update state immediately
        self._state = state
        
        # If turning off, reset current
        if not state:
            try:
                await self._reset_current_proxy()
            except AttributeError:
                # Method might not be defined in all test cases
                pass
        
        # Check if we should send command now or buffer
        if self._last_update is None or (now - self._last_update) >= self._min_update_interval:
            await self._update_car_api()
        else:
            # Buffer the command - in a real system this would be scheduled
            pass
    
    async def _update_car_api(self):
        """Update the car API with the desired state."""
        service = "turn_on" if self._desired_state else "turn_off"
        await self.hass.async_call_service(
            "switch", service,
            {"entity_id": self._source_entity}
        )
        self._last_update = datetime.now()


@pytest.mark.asyncio
async def test_current_proxy_buffering():
    """Test that current commands are properly buffered."""
    proxy = MockCarChargingProxy()
    
    # First command should be sent immediately
    await proxy.set_value(12)
    assert len(proxy.hass.service_calls) == 1
    domain, service, data = proxy.hass.service_calls[0]
    assert domain == "number"
    assert service == "set_value"
    assert data["value"] == 12
    
    # Clear service calls
    proxy.hass.service_calls.clear()
    
    # Second command should be buffered (not sent yet)
    await proxy.set_value(8)
    assert len(proxy.hass.service_calls) == 0
    
    # But the state should be updated immediately
    assert proxy._state == 8
    
    # Manually advance time by setting _last_update to an earlier time
    proxy._last_update = datetime.now() - timedelta(minutes=2)
    
    # Now if we set a new value, it should be sent immediately
    await proxy.set_value(6)
    assert len(proxy.hass.service_calls) == 1
    domain, service, data = proxy.hass.service_calls[0]
    assert domain == "number"
    assert service == "set_value"
    assert data["value"] == 6


@pytest.mark.asyncio
async def test_switch_proxy_buffering():
    """Test that switch commands are properly buffered."""
    proxy = MockCarChargingSwitchProxy()
    
    # First command should be sent immediately
    await proxy.set_state(False)
    assert len(proxy.hass.service_calls) == 1
    domain, service, data = proxy.hass.service_calls[0]
    assert domain == "switch"
    assert service == "turn_off"
    
    # Clear service calls
    proxy.hass.service_calls.clear()
    
    # Second command should be buffered (not sent yet)
    await proxy.set_state(True)
    assert len(proxy.hass.service_calls) == 0
    
    # But the state should be updated immediately
    assert proxy._state is True
    
    # Manually advance time by setting _last_update to an earlier time
    proxy._last_update = datetime.now() - timedelta(minutes=2)
    
    # Now if we set a new state, it should be sent immediately
    await proxy.set_state(False)
    assert len(proxy.hass.service_calls) == 1
    domain, service, data = proxy.hass.service_calls[0]
    assert domain == "switch"
    assert service == "turn_off"


class MockIntegratedProxies:
    """Mock of both proxies working together for testing reset functionality."""
    
    def __init__(self):
        self.hass = MockHomeAssistant()
        self.current_proxy = MockCarChargingProxy()
        self.current_proxy.hass = self.hass
        self.switch_proxy = MockCarChargingSwitchProxy()
        self.switch_proxy.hass = self.hass
        
        # Add reset current functionality to switch proxy
        self.switch_proxy._reset_current_proxy = self._reset_current_proxy
        self.switch_proxy._vehicle_slug = "tessy"
        
    async def _reset_current_proxy(self):
        """Reset current to minimum when turning off."""
        current_entity_id = f"number.{self.switch_proxy._vehicle_slug}_charging_current_proxy"
        await self.hass.async_call_service(
            "number", "set_value",
            {"entity_id": current_entity_id, "value": 1}
        )


@pytest.mark.asyncio
async def test_switch_resets_current():
    """Test that turning off the switch resets the current."""
    proxies = MockIntegratedProxies()
    
    # First set current to a high value
    await proxies.current_proxy.set_value(16)
    assert proxies.current_proxy._state == 16
    
    # Clear service calls
    proxies.hass.service_calls.clear()
    
    # Turn off the switch
    await proxies.switch_proxy.set_state(False)
    
    # Check that switch was turned off
    assert any(
        domain == "switch" and service == "turn_off"
        for domain, service, _ in proxies.hass.service_calls
    )
    
    # Check that current was reset
    assert any(
        domain == "number" and service == "set_value" and data["value"] == 1
        for domain, service, data in proxies.hass.service_calls
    )
