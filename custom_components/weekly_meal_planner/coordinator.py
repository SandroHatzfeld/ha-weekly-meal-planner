"""Regelmäßiges Laden von Listen, Einträgen und Gerichten eines Plans."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import MealPlannerApi, MealPlannerAuthError, MealPlannerError, MealPlannerNotFoundError
from .const import CONF_PLAN_ID, DISHES_FUTURE_DAYS, DISHES_PAST_DAYS, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class MealPlannerData:
    """Stand eines Plans."""

    lists: list[dict[str, Any]] = field(default_factory=list)
    items: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # listId -> Einträge
    dishes: list[dict[str, Any]] = field(default_factory=list)


type MealPlannerConfigEntry = ConfigEntry[MealPlannerCoordinator]


class MealPlannerCoordinator(DataUpdateCoordinator[MealPlannerData]):
    """Fragt die API alle 30 Sekunden ab."""

    config_entry: MealPlannerConfigEntry

    def __init__(self, hass: HomeAssistant, entry: MealPlannerConfigEntry, api: MealPlannerApi) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = api
        self.plan_id: str = entry.data[CONF_PLAN_ID]
        self._warned_old_server = False

    async def _dishes(self, today) -> list[dict[str, Any]]:
        # ältere App-Versionen kennen den Gerichte-Endpunkt noch nicht: Einkaufslisten trotzdem anbieten
        try:
            return await self.api.get_dishes(
                self.plan_id, today - timedelta(days=DISHES_PAST_DAYS), today + timedelta(days=DISHES_FUTURE_DAYS)
            )
        except MealPlannerNotFoundError:
            if not self._warned_old_server:
                _LOGGER.warning("Der Mealplanner-Server kennt den Gerichte-Endpunkt nicht – bitte die App aktualisieren")
                self._warned_old_server = True
            return []

    async def _async_update_data(self) -> MealPlannerData:
        today = dt_util.now().date()
        try:
            lists = await self.api.get_lists(self.plan_id)
            item_lists, dishes = await asyncio.gather(
                asyncio.gather(*(self.api.get_items(entry["id"]) for entry in lists)),
                self._dishes(today),
            )
        except MealPlannerAuthError as err:
            raise ConfigEntryAuthFailed from err
        except MealPlannerError as err:
            raise UpdateFailed(f"Server nicht erreichbar: {err}") from err
        return MealPlannerData(
            lists=lists,
            items={entry["id"]: items for entry, items in zip(lists, item_lists, strict=True)},
            dishes=dishes,
        )
