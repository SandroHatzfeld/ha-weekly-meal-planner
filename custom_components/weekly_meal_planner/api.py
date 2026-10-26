"""Client für die externe API des Weekly Meal Planners (/api/external/...)."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

import aiohttp


class MealPlannerError(Exception):
    """Allgemeiner Fehler bei der Kommunikation mit dem Server."""


class MealPlannerConnectionError(MealPlannerError):
    """Server nicht erreichbar oder unerwartete Antwort."""


class MealPlannerAuthError(MealPlannerError):
    """API-Token ungültig oder widerrufen."""


class MealPlannerNotFoundError(MealPlannerError):
    """Plan, Liste oder Eintrag existiert nicht (mehr) oder gehört nicht zum Token."""


class MealPlannerApi:
    """Dünner Wrapper um die REST-Endpunkte, authentifiziert per API-Token."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._base = url.rstrip("/") + "/api/external"
        self._token = token

    async def _request(self, method: str, path: str, *, json: Any = None, params: dict[str, str] | None = None) -> Any:
        try:
            async with asyncio.timeout(15):
                response = await self._session.request(
                    method,
                    f"{self._base}{path}",
                    json=json,
                    params=params,
                    headers={"Authorization": f"Bearer {self._token}"},
                )
                if response.status == 401:
                    raise MealPlannerAuthError("Ungültiges API-Token")
                if response.status == 404:
                    raise MealPlannerNotFoundError(path)
                if response.status >= 400:
                    raise MealPlannerConnectionError(f"HTTP {response.status}: {await response.text()}")
                if response.status == 204:
                    return None
                return await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise MealPlannerConnectionError(str(err)) from err

    async def get_plans(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/plans")

    async def get_lists(self, plan_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/plans/{plan_id}/lists")

    async def get_items(self, list_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/lists/{list_id}/grocery-items")

    async def add_item(self, list_id: str, name: str, details: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if details:
            body["details"] = details
        return await self._request("POST", f"/lists/{list_id}/grocery-items", json=body)

    async def update_item(self, list_id: str, item_id: str, **fields: Any) -> dict[str, Any]:
        """Felder: name, details (None = leeren), checked."""
        return await self._request("PATCH", f"/lists/{list_id}/grocery-items/{item_id}", json=fields)

    async def delete_item(self, list_id: str, item_id: str) -> None:
        await self._request("DELETE", f"/lists/{list_id}/grocery-items/{item_id}")

    async def get_dishes(self, plan_id: str, start: date, end: date) -> list[dict[str, Any]]:
        """Gerichte von start bis end (beide inklusive)."""
        return await self._request(
            "GET", f"/plans/{plan_id}/dishes", params={"from": start.isoformat(), "to": end.isoformat()}
        )
