"""Aqara Home Assistant Base Device Model."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from this import d

# from tkinter.messagebox import NO
from types import SimpleNamespace
from typing import Any

from aqara_iot import AqaraDevice, AqaraDeviceManager, AqaraPoint

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity

from . import HomeAssistantAqaraData
from .const import (
    AQARA_HA_SIGNAL_REGISTER_POINT,
    AQARA_HA_SIGNAL_UPDATE_ENTITY,
    AQARA_HA_SIGNAL_UPDATE_POINT_VALUE,
    DOMAIN,
)
from .util import remap_value, string_dot_to_underline, string_underline_to_dot

#

_LOGGER = logging.getLogger(__name__)


@dataclass
class IntegerTypeData:
    """Integer Type Data."""

    min: int
    max: int
    scale: float
    step: float
    unit: str | None = None
    type: str | None = None

    @property
    def max_scaled(self) -> float:
        """Return the max scaled."""
        return self.scale_value(self.max)

    @property
    def min_scaled(self) -> float:
        """Return the min scaled."""
        return self.scale_value(self.min)

    @property
    def step_scaled(self) -> float:
        """Return the step scaled."""
        return self.scale_value(self.step)

    def scale_value(self, value: float | int) -> float:
        """Scale a value."""
        return value * 1.0 / (10**self.scale)

    def scale_value_back(self, value: float | int) -> int:
        """Return raw value for scaled."""
        return int(value * (10**self.scale))

    def remap_value_to(
        self,
        value: float,
        to_min: float | int = 0,
        to_max: float | int = 255,
        reverse: bool = False,
    ) -> float:
        """Remap a value from this range to a new range."""
        return remap_value(value, self.min, self.max, to_min, to_max, reverse)

    def remap_value_from(
        self,
        value: float,
        from_min: float | int = 0,
        from_max: float | int = 255,
        reverse: bool = False,
    ) -> float:
        """Remap a value from its current range to this range."""
        return remap_value(value, from_min, from_max, self.min, self.max, reverse)

    @classmethod
    def from_json(cls, data: str) -> IntegerTypeData:
        """Load JSON string and return a IntegerTypeData object."""
        return cls(**json.loads(data))


class DeviceValueRange(SimpleNamespace):
    """device's value range.

    Attributes:
        type(str): value's type, which may be Boolean, Integer, Enum, Json
        values(dict): value range
    """

    type: str
    values: str


@dataclass
class EnumTypeData:
    """Enum Type Data."""

    range: list[str]

    @classmethod
    def from_json(cls, data: str) -> EnumTypeData:
        """Load JSON string and return a EnumTypeData object."""
        return cls(**json.loads(data))


# @dataclass
# class ElectricityTypeData:
#     """Electricity Type Data."""

#     electriccurrent: str | None = None
#     power: str | None = None
#     voltage: str | None = None

#     @classmethod
#     def from_json(cls, data: str) -> ElectricityTypeData:
#         """Load JSON string and return a ElectricityTypeData object."""
#         return cls(**json.loads(data.lower()))


class AqaraEntity(Entity):
    """Aqara base device."""

    _attr_should_poll = False

    def __init__(self, point: AqaraPoint, device_manager: AqaraDeviceManager) -> None:
        """Init AqaraHaEntity."""
        self._attr_unique_id = f"Aqara.{point.id}"
        self.point = point
        self.device_manager = device_manager
        device = self.get_aqara_device()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, string_dot_to_underline(self.point.did))},
            manufacturer="Aqara",
            name=f"{device.device_name}({self.point.did})",  #               self.point.did,  # self.entity_name(),  # f"{self.point.name}({self.point.did})"
            model=device.model,
            suggested_area=f"{device.position_name}",
        )

    def get_aqara_device(self) -> AqaraDevice:
        """get the device of the point."""
        return self.device_manager.get_device(self.point.did)

    @property
    def name(self) -> str | None:
        """Return Aqara device name."""
        if isinstance(self.point.name, str) and self.point.name != "":
            return f"{self.point.name}({self.point.did})"
        if hasattr(self, "entity_description"):
            if self.entity_description.name is not None and isinstance(
                self.entity_description.name, str
            ):
                return f"{self.entity_description.name}({self.point.did})"
        return f"({self.point.id})"

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        device = self.device_manager.get_device(self.point.did)
        return DeviceInfo(
            identifiers={(DOMAIN, string_dot_to_underline(self.point.did))},
            manufacturer="Aqara",
            name=f"{device.device_name}({self.point.did})",  #               self.point.did,  # self.entity_name(),  # f"{self.point.name}({self.point.did})"
            model=self.device_manager.get_device_model(self.point.did),
            suggested_area=f"{device.position_name}",
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.point.is_online()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{AQARA_HA_SIGNAL_UPDATE_ENTITY}_{string_dot_to_underline(self.point.id)}",
                self.async_write_ha_state,
            )
        )

    def _send_command(self, commands: dict[str, str]) -> None:
        """Send command to the device."""
        _LOGGER.debug("Sending commands for device %s: %s", self.point.did, commands)
        did = string_underline_to_dot(self.point.did)
        self.device_manager.send_commands(did, commands)


def find_aqara_device_points_and_register(
    hass: HomeAssistant,
    entry_id,
    hass_data: HomeAssistantAqaraData,
    device_ids: list[str],
    descriptions_map: dict[str, Any],
    append_entity,
):
    """find the point from device."""
    device_registry = dr.async_get(hass)

    for device_id in device_ids:
        device = hass_data.device_manager.device_map[device_id]
        model = device.model
        descriptions = descriptions_map.get(model)
        # print("device_id:", device_id, model)

        if descriptions is not None:
            for description in descriptions:
                aqara_point = device.point_map.get(
                    hass_data.device_manager.make_point_id(device.did, description.key)
                )
                if aqara_point is not None:
                    device_registry.async_get_or_create(  # create the device.
                        config_entry_id=entry_id,
                        identifiers={
                            (DOMAIN, string_dot_to_underline(aqara_point.did))
                        },  # hass_device_id
                        manufacturer="Aqara",
                        name=aqara_point.did,  # ,
                        model=device.model,
                        suggested_area=f"{device.position_name}",
                    )

                    append_entity(aqara_point, description)  # add entry to list.
                    async_dispatcher_send(
                        hass,
                        AQARA_HA_SIGNAL_REGISTER_POINT,
                        string_dot_to_underline(aqara_point.id),
                    )


def entity_data_update_binding(
    hass: HomeAssistant,
    hass_data: HomeAssistantAqaraData,
    entity: AqaraEntity,
    did: str,
    res_ids: list[str],
):
    """entity_data_update_binding"""
    for res_id in res_ids:
        if res_id is None or res_id == "":
            continue

        point_id = string_dot_to_underline(
            hass_data.device_manager.make_point_id(device_id=did, res_id=res_id)
        )
        entity.async_on_remove(
            async_dispatcher_connect(
                hass,
                f"{AQARA_HA_SIGNAL_UPDATE_ENTITY}_{point_id}",
                entity.async_write_ha_state,
            )
        )
        hass_data.device_listener.async_register_point(point_id)


def entity_point_value_update_binding(
    hass: HomeAssistant,
    hass_data: HomeAssistantAqaraData,
    entity: AqaraEntity,
    did: str,
    res_ids: list[str],
    callback: CALLBACK_TYPE,
):
    """entity_data_update_binding"""
    for res_id in res_ids:
        if res_id is None or res_id == "":
            continue

        point_id = string_dot_to_underline(
            hass_data.device_manager.make_point_id(device_id=did, res_id=res_id)
        )

        entity.async_on_remove(
            async_dispatcher_connect(
                hass,
                f"{AQARA_HA_SIGNAL_UPDATE_POINT_VALUE}_{point_id}",
                callback,
            )
        )
        hass_data.device_listener.async_register_point(point_id)
