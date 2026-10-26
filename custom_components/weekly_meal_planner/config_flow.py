"""Einrichtung: Server-Adresse und API-Token, dann den Plan wählen."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import MealPlannerApi, MealPlannerAuthError, MealPlannerError, MealPlannerNotFoundError, normalize_url
from .const import CONF_PLAN_ID, CONF_PLAN_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        vol.Required(CONF_API_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
    }
)


class MealPlannerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ein Eintrag pro Plan."""

    VERSION = 1

    def __init__(self) -> None:
        self._url = ""
        self._token = ""
        self._plans: list[dict[str, Any]] = []
        # Grund des letzten Verbindungsfehlers, wird im Dialog angezeigt
        self._error_detail = ""

    async def _fetch_plans(self, url: str, token: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
        api = MealPlannerApi(async_get_clientsession(self.hass), url, token)
        try:
            plans = await api.get_plans()
        except MealPlannerAuthError:
            return [], {"base": "invalid_auth"}
        except MealPlannerNotFoundError:
            # Server antwortet, aber unter dieser Adresse gibt es keine Mealplanner-API
            return [], {"base": "wrong_url"}
        except MealPlannerError as err:
            self._error_detail = str(err)
            _LOGGER.warning("Weekly Meal Planner unter %s nicht erreichbar: %s", url, err)
            return [], {"base": "cannot_connect"}
        if not plans:
            return [], {"base": "no_plans"}
        return plans, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._url = normalize_url(user_input[CONF_URL])
            self._token = user_input[CONF_API_TOKEN].strip()
            self._plans, errors = await self._fetch_plans(self._url, self._token)
            if not errors:
                return await self.async_step_plan()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
            description_placeholders={"error": self._error_detail},
        )

    async def async_step_plan(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        # nur ein Plan: ohne Nachfrage nehmen
        if user_input is None and len(self._plans) == 1:
            user_input = {CONF_PLAN_ID: self._plans[0]["id"]}
        if user_input is not None:
            plan = next(plan for plan in self._plans if plan["id"] == user_input[CONF_PLAN_ID])
            await self.async_set_unique_id(plan["id"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=plan["name"],
                data={CONF_URL: self._url, CONF_API_TOKEN: self._token, CONF_PLAN_ID: plan["id"], CONF_PLAN_NAME: plan["name"]},
            )
        options = [SelectOptionDict(value=plan["id"], label=plan["name"]) for plan in self._plans]
        return self.async_show_form(
            step_id="plan", data_schema=vol.Schema({vol.Required(CONF_PLAN_ID): SelectSelector(SelectSelectorConfig(options=options))})
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Token wurde widerrufen: neues Token eingeben."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_API_TOKEN].strip()
            plans, errors = await self._fetch_plans(entry.data[CONF_URL], token)
            if not errors and not any(plan["id"] == entry.data[CONF_PLAN_ID] for plan in plans):
                errors = {"base": "plan_missing"}
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_API_TOKEN: token})
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"error": self._error_detail},
            data_schema=vol.Schema(
                {vol.Required(CONF_API_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
            ),
            errors=errors,
        )
