"""Geplante Gerichte als Kalender (ganztägige Termine)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import MealPlannerError, MealPlannerNotFoundError
from .const import MAX_RANGE_DAYS
from .coordinator import MealPlannerConfigEntry
from .entity import MealPlannerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MealPlannerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([MealPlannerCalendar(entry.runtime_data)])


def _event(dish: dict[str, Any]) -> CalendarEvent:
    day = date.fromisoformat(dish["date"])
    return CalendarEvent(
        start=day,
        end=day + timedelta(days=1),
        summary=dish["name"],
        description="\n\n".join(part for part in (dish.get("description"), dish.get("url")) if part) or None,
        uid=dish["id"],
    )


class MealPlannerCalendar(MealPlannerEntity, CalendarEntity):
    """Kalender „Gerichte“ eines Plans."""

    _attr_translation_key = "dishes"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.plan_id}_dishes"

    @property
    def event(self) -> CalendarEvent | None:
        """Heutiges oder nächstes Gericht."""
        today = dt_util.now().date().isoformat()
        upcoming = [dish for dish in self.coordinator.data.dishes if dish["date"] >= today]
        return _event(min(upcoming, key=lambda dish: (dish["date"], dish["name"]))) if upcoming else None

    async def async_get_events(self, hass: HomeAssistant, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        # Zeitraum ggf. in Blöcke teilen, die API liefert höchstens ein Jahr am Stück
        start = dt_util.as_local(start_date).date()
        last = dt_util.as_local(end_date - timedelta(microseconds=1)).date()
        events: list[CalendarEvent] = []
        try:
            while start <= last:
                chunk_end = min(last, start + timedelta(days=MAX_RANGE_DAYS - 1))
                dishes = await self.coordinator.api.get_dishes(self.coordinator.plan_id, start, chunk_end)
                events.extend(_event(dish) for dish in dishes)
                start = chunk_end + timedelta(days=1)
        except MealPlannerNotFoundError:
            return []  # ältere App-Version ohne Gerichte-Endpunkt
        except MealPlannerError as err:
            raise HomeAssistantError(f"Gerichte konnten nicht geladen werden: {err}") from err
        return events
