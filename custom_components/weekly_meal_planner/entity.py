"""Gemeinsame Basis der Entitäten: ein Gerät pro Plan."""

from __future__ import annotations

from homeassistant.const import CONF_URL
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PLAN_NAME, DOMAIN
from .coordinator import MealPlannerCoordinator


class MealPlannerEntity(CoordinatorEntity[MealPlannerCoordinator]):
    """Basis-Entität eines Plans."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MealPlannerCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.plan_id)},
            name=entry.data.get(CONF_PLAN_NAME, entry.title),
            manufacturer="Weekly Meal Planner",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=entry.data[CONF_URL],
        )
