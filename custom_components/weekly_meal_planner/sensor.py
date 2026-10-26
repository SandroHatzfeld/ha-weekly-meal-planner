"""Sensoren: offene Einträge je Einkaufsliste, heutiges und morgiges Gericht."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import MealPlannerConfigEntry, MealPlannerCoordinator
from .entity import MealPlannerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MealPlannerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([DishSensor(coordinator, 0, "dish_today"), DishSensor(coordinator, 1, "dish_tomorrow")])
    known: set[str] = set()

    @callback
    def add_new_lists() -> None:
        new = [entry for entry in coordinator.data.lists if entry["id"] not in known]
        known.update(entry["id"] for entry in new)
        if new:
            async_add_entities(OpenItemsSensor(coordinator, entry["id"], entry["name"]) for entry in new)

    add_new_lists()
    entry.async_on_unload(coordinator.async_add_listener(add_new_lists))


class OpenItemsSensor(MealPlannerEntity, SensorEntity):
    """Anzahl noch nicht abgehakter Einträge einer Liste."""

    _attr_translation_key = "open_items"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cart-outline"

    def __init__(self, coordinator: MealPlannerCoordinator, list_id: str, list_name: str) -> None:
        super().__init__(coordinator)
        self._list_id = list_id
        self._attr_unique_id = f"{coordinator.plan_id}_{list_id}_open_items"
        self._attr_translation_placeholders = {"list": list_name}

    @property
    def available(self) -> bool:
        return super().available and self._list_id in self.coordinator.data.items

    @property
    def native_value(self) -> int | None:
        items = self.coordinator.data.items.get(self._list_id)
        return None if items is None else sum(1 for item in items if not item["checked"])

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        items = self.coordinator.data.items.get(self._list_id) or []
        return {"items": [item["name"] for item in items if not item["checked"]]}


class DishSensor(MealPlannerEntity, SensorEntity):
    """Gericht(e) eines Tages (heute + offset), mehrere mit Komma getrennt."""

    _attr_icon = "mdi:silverware-fork-knife"

    def __init__(self, coordinator: MealPlannerCoordinator, offset: int, key: str) -> None:
        super().__init__(coordinator)
        self._offset = offset
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.plan_id}_{key}"

    def _dishes(self) -> list[dict]:
        day = (dt_util.now().date() + timedelta(days=self._offset)).isoformat()
        return [dish for dish in self.coordinator.data.dishes if dish["date"] == day]

    @property
    def native_value(self) -> str | None:
        return ", ".join(dish["name"] for dish in self._dishes()) or None

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, str | None]]]:
        return {"dishes": [{"name": dish["name"], "description": dish.get("description"), "url": dish.get("url")} for dish in self._dishes()]}
