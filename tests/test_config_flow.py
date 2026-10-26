"""Einrichtung über die Oberfläche."""

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.weekly_meal_planner.const import CONF_PLAN_ID, DOMAIN

from .conftest import TOKEN, URL


async def _start(hass, url=URL + "/", token=TOKEN):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: url, CONF_API_TOKEN: token})


async def test_single_plan_creates_entry(hass, fake_api):
    result = await _start(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WG"
    assert result["data"] == {CONF_URL: URL, CONF_API_TOKEN: TOKEN, CONF_PLAN_ID: "plan1", "plan_name": "WG"}
    assert result["result"].unique_id == "plan1"


async def test_choose_plan(hass, fake_api):
    fake_api.plans.append({"id": "plan2", "name": "Zuhause"})
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "plan"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PLAN_ID: "plan2"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Zuhause"


async def test_invalid_token(hass, fake_api):
    fake_api.token_valid = False
    result = await _start(hass)
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass, fake_api):
    fake_api.reachable = False
    result = await _start(hass)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_no_plans(hass, fake_api):
    fake_api.plans.clear()
    result = await _start(hass)
    assert result["errors"] == {"base": "no_plans"}


async def test_already_configured(hass, fake_api, config_entry):
    config_entry.add_to_hass(hass)
    result = await _start(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass, fake_api, setup_integration):
    entry = setup_integration
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    fake_api.token_valid = False
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_TOKEN: "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}
    fake_api.token_valid = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_API_TOKEN: "new-token"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_TOKEN] == "new-token"
