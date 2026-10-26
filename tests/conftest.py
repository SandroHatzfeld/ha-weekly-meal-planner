"""Gemeinsame Fixtures: nachgebildete API mit Zustand im Speicher."""

from __future__ import annotations

from datetime import date, timedelta
import itertools
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weekly_meal_planner.api import MealPlannerAuthError, MealPlannerConnectionError, MealPlannerNotFoundError
from custom_components.weekly_meal_planner.const import CONF_PLAN_ID, CONF_PLAN_NAME, DOMAIN

URL = "https://mealplanner.example.com"
TOKEN = "secret-token"
PLAN = {"id": "plan1", "name": "WG"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeApi:
    """Verhält sich wie der Server: Listen, Einträge, Gerichte im Speicher."""

    def __init__(self) -> None:
        self.token_valid = True
        self.reachable = True
        self.plans = [dict(PLAN)]
        self.lists = [{"id": "list1", "name": "Supermarkt"}, {"id": "list2", "name": "Drogerie"}]
        self.items: dict[str, list[dict[str, Any]]] = {
            "list1": [
                {"id": "i1", "name": "Milch", "details": "2 L", "checked": False},
                {"id": "i2", "name": "Brot", "details": None, "checked": True},
            ],
            "list2": [],
        }
        today = dt_util.now().date()
        self.dishes = [
            {"id": "d1", "name": "Lasagne", "date": today.isoformat(), "description": "mit Salat", "url": f"{URL}/dishes/d1"},
            {"id": "d2", "name": "Curry", "date": (today + timedelta(days=1)).isoformat(), "description": None, "url": f"{URL}/dishes/d2"},
        ]
        self.calls: list[tuple] = []
        self._ids = itertools.count(100)

    def _check(self) -> None:
        if not self.reachable:
            raise MealPlannerConnectionError("down")
        if not self.token_valid:
            raise MealPlannerAuthError("invalid")

    async def get_plans(self):
        self._check()
        return self.plans

    async def get_lists(self, plan_id):
        self._check()
        return self.lists

    async def get_items(self, list_id):
        self._check()
        return [dict(item) for item in self.items[list_id]]

    async def add_item(self, list_id, name, details=None):
        self._check()
        item = {"id": f"i{next(self._ids)}", "name": name, "details": details or None, "checked": False}
        self.items[list_id].append(item)
        self.calls.append(("add", list_id, name, details))
        return dict(item)

    async def update_item(self, list_id, item_id, **fields):
        self._check()
        item = next((item for item in self.items[list_id] if item["id"] == item_id), None)
        if item is None:
            raise MealPlannerNotFoundError(item_id)
        item.update(fields)
        self.calls.append(("update", list_id, item_id, fields))
        return dict(item)

    async def delete_item(self, list_id, item_id):
        self._check()
        self.items[list_id] = [item for item in self.items[list_id] if item["id"] != item_id]
        self.calls.append(("delete", list_id, item_id))

    async def get_dishes(self, plan_id, start: date, end: date):
        self._check()
        self.calls.append(("dishes", start, end))
        return [dish for dish in self.dishes if start.isoformat() <= dish["date"] <= end.isoformat()]


@pytest.fixture
def fake_api() -> FakeApi:
    api = FakeApi()
    with (
        patch("custom_components.weekly_meal_planner.MealPlannerApi", return_value=api),
        patch("custom_components.weekly_meal_planner.config_flow.MealPlannerApi", return_value=api),
    ):
        yield api


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=PLAN["name"],
        unique_id=PLAN["id"],
        data={CONF_URL: URL, CONF_API_TOKEN: TOKEN, CONF_PLAN_ID: PLAN["id"], CONF_PLAN_NAME: PLAN["name"]},
    )


@pytest.fixture
async def setup_integration(hass, fake_api, config_entry):
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry
