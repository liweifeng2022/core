"""Tests for the Aqara siren device."""
from unittest.mock import patch
import aqara_iot.openmq
from .common import mock_start

from homeassistant.components.siren import DOMAIN as SIREN_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from .common import setup_platform
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)

DEVICE_ID = "siren.bao_jing_zhuang_tai_lumi1_54ef4426f6b9"
DEVICE_UID = "Aqara.lumi1.54ef4426f6b9__14.1.111"


async def test_entity_registry(hass: HomeAssistant) -> None:
    """Tests that the devices are registered in the entity registry."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):

        await setup_platform(hass, SIREN_DOMAIN)
        entity_registry = er.async_get(hass)

        entry = entity_registry.async_get(DEVICE_ID)
        print(entry)
        assert entry.unique_id == DEVICE_UID


async def test_attributes(hass: HomeAssistant) -> None:
    """Test the siren attributes are correct."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):
        await setup_platform(hass, SIREN_DOMAIN)

        state = hass.states.get(DEVICE_ID)
        print("===========================================")
        print(state)
        assert state.state == STATE_OFF


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test the siren can be turned off."""
    with patch.object(aqara_iot.openmq.AqaraOpenMQ, "start", mock_start):
        await setup_platform(hass, SIREN_DOMAIN)

        with patch("aqara_iot.AqaraDeviceManager.send_commands") as mock_siren_off:
            assert await hass.services.async_call(
                SIREN_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: DEVICE_ID},
                blocking=True,
            )
            await hass.async_block_till_done()
            mock_siren_off.assert_called_once()
