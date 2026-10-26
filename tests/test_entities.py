"""To-do-Listen, Kalender und Sensoren."""

from datetime import timedelta

import pytest

from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

TODO = "todo.wg_supermarkt"


async def test_todo_state_and_items(hass, setup_integration):
    assert hass.states.get(TODO).state == "1"  # ein offener Eintrag
    assert hass.states.get("todo.wg_drogerie").state == "0"
    result = await hass.services.async_call(TODO_DOMAIN, "get_items", {}, target={"entity_id": TODO}, blocking=True, return_response=True)
    items = result[TODO]["items"]
    assert [(item["summary"], item["status"], item.get("description")) for item in items] == [
        ("Milch", "needs_action", "2 L"),
        ("Brot", "completed", None),
    ]


async def test_todo_add_update_remove(hass, setup_integration, fake_api):
    await hass.services.async_call(TODO_DOMAIN, "add_item", {"item": "Eier", "description": "10 Stück"}, target={"entity_id": TODO}, blocking=True)
    assert ("add", "list1", "Eier", "10 Stück") in fake_api.calls
    assert hass.states.get(TODO).state == "2"

    await hass.services.async_call(TODO_DOMAIN, "update_item", {"item": "Milch", "rename": "Hafermilch", "status": "completed"}, target={"entity_id": TODO}, blocking=True)
    assert ("update", "list1", "i1", {"name": "Hafermilch", "checked": True}) in fake_api.calls
    assert hass.states.get(TODO).state == "1"

    await hass.services.async_call(TODO_DOMAIN, "update_item", {"item": "Hafermilch", "description": ""}, target={"entity_id": TODO}, blocking=True)
    assert ("update", "list1", "i1", {"details": None}) in fake_api.calls

    await hass.services.async_call(TODO_DOMAIN, "remove_item", {"item": ["Brot"]}, target={"entity_id": TODO}, blocking=True)
    assert ("delete", "list1", "i2") in fake_api.calls
    assert [item["name"] for item in fake_api.items["list1"]] == ["Hafermilch", "Eier"]


async def test_changes_from_app_arrive_by_polling(hass, setup_integration, fake_api):
    fake_api.items["list2"].append({"id": "x", "name": "Seife", "details": None, "checked": False})
    fake_api.lists.append({"id": "list3", "name": "Markt"})
    fake_api.items["list3"] = []
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    # die regelmäßige Abfrage läuft als Hintergrund-Task
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get("todo.wg_drogerie").state == "1"
    assert hass.states.get("todo.wg_markt") is not None  # neue Liste ohne Neustart


async def test_calendar(hass, setup_integration, fake_api):
    state = hass.states.get("calendar.wg_dishes")
    assert state.state == "on"  # heute gibt es Lasagne
    assert state.attributes["message"] == "Lasagne"
    start = dt_util.start_of_local_day()
    result = await hass.services.async_call(
        "calendar", "get_events",
        {"start_date_time": start.isoformat(), "end_date_time": (start + timedelta(days=2)).isoformat()},
        target={"entity_id": "calendar.wg_dishes"}, blocking=True, return_response=True,
    )
    events = result["calendar.wg_dishes"]["events"]
    assert [event["summary"] for event in events] == ["Lasagne", "Curry"]
    assert "mit Salat" in events[0]["description"]


async def test_calendar_long_range_is_split(hass, setup_integration, fake_api):
    start = dt_util.start_of_local_day()
    fake_api.calls.clear()
    await hass.services.async_call(
        "calendar", "get_events",
        {"start_date_time": start.isoformat(), "end_date_time": (start + timedelta(days=500)).isoformat()},
        target={"entity_id": "calendar.wg_dishes"}, blocking=True, return_response=True,
    )
    ranges = [call for call in fake_api.calls if call[0] == "dishes"]
    assert len(ranges) == 2 and all((end - begin).days < 366 for _, begin, end in ranges)


async def test_sensors(hass, setup_integration):
    assert hass.states.get("sensor.wg_open_supermarkt").state == "1"
    assert hass.states.get("sensor.wg_open_supermarkt").attributes["items"] == ["Milch"]
    assert hass.states.get("sensor.wg_today_s_dish").state == "Lasagne"
    assert hass.states.get("sensor.wg_tomorrow_s_dish").state == "Curry"


async def test_auth_failure_starts_reauth(hass, setup_integration, fake_api):
    fake_api.token_valid = False
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)
    flows = hass.config_entries.flow.async_progress()
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_unreachable_on_setup_retries(hass, fake_api, config_entry):
    fake_api.reachable = False
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("_", [None])
async def test_unload(hass, setup_integration, _):
    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    assert setup_integration.state is ConfigEntryState.NOT_LOADED
