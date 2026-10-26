"""Optionaler Test gegen einen echten Server: LIVE_URL und LIVE_TOKEN setzen (sonst übersprungen)."""

import os

import pytest

from homeassistant import config_entries
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.weekly_meal_planner.const import CONF_PLAN_ID, DOMAIN

LIVE_URL = os.environ.get("LIVE_URL")
LIVE_TOKEN = os.environ.get("LIVE_TOKEN")
LIVE_PLAN = os.environ.get("LIVE_PLAN")

pytestmark = [pytest.mark.skipif(not LIVE_URL or not LIVE_TOKEN, reason="kein Live-Server angegeben"), pytest.mark.enable_socket]


async def test_live_roundtrip(hass, socket_enabled):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: LIVE_URL, CONF_API_TOKEN: LIVE_TOKEN})
    if result["type"] is FlowResultType.FORM and result["step_id"] == "plan":
        options = result["data_schema"].schema[CONF_PLAN_ID].config["options"]
        plan = next(option["value"] for option in options if option["label"] == LIVE_PLAN) if LIVE_PLAN else options[0]["value"]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PLAN_ID: plan})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    todos = [state.entity_id for state in hass.states.async_all("todo")]
    assert todos, "keine Einkaufslisten gefunden"
    todo = todos[0]
    entry = result["result"]
    api = entry.runtime_data.api
    list_id = entry.runtime_data.data.lists[0]["id"]

    await hass.services.async_call(TODO_DOMAIN, "add_item", {"item": "Live-Test Apfel", "description": "3 Stück"}, target={"entity_id": todo}, blocking=True)
    on_server = [item for item in await api.get_items(list_id) if item["name"] == "Live-Test Apfel"]
    assert on_server and on_server[0]["details"] == "3 Stück"

    await hass.services.async_call(TODO_DOMAIN, "update_item", {"item": "Live-Test Apfel", "rename": "Live-Test Birne", "status": "completed"}, target={"entity_id": todo}, blocking=True)
    on_server = [item for item in await api.get_items(list_id) if item["id"] == on_server[0]["id"]]
    assert on_server[0]["name"] == "Live-Test Birne" and on_server[0]["checked"] is True

    await hass.services.async_call(TODO_DOMAIN, "remove_item", {"item": ["Live-Test Birne"]}, target={"entity_id": todo}, blocking=True)
    assert not [item for item in await api.get_items(list_id) if item["id"] == on_server[0]["id"]]

    assert hass.states.get(f"calendar.{entry.title.lower()}_dishes") is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
