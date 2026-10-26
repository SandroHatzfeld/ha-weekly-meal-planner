"""Einkaufslisten als To-do-Listen (auch für Assist: „Setze Milch auf die Einkaufsliste“)."""

from __future__ import annotations

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity, TodoListEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import MealPlannerError
from .coordinator import MealPlannerConfigEntry, MealPlannerCoordinator
from .entity import MealPlannerEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: MealPlannerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    # in der App neu angelegte Listen erscheinen ohne Neustart
    @callback
    def add_new_lists() -> None:
        new = [entry for entry in coordinator.data.lists if entry["id"] not in known]
        known.update(entry["id"] for entry in new)
        if new:
            async_add_entities(MealPlannerTodoList(coordinator, entry["id"], entry["name"]) for entry in new)

    add_new_lists()
    entry.async_on_unload(coordinator.async_add_listener(add_new_lists))


class MealPlannerTodoList(MealPlannerEntity, TodoListEntity):
    """Eine Einkaufsliste; Details eines Eintrags = Beschreibung."""

    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: MealPlannerCoordinator, list_id: str, name: str) -> None:
        super().__init__(coordinator)
        self._list_id = list_id
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.plan_id}_{list_id}"

    @property
    def available(self) -> bool:
        # in der App gelöschte Liste: nicht mehr verfügbar
        return super().available and self._list_id in self.coordinator.data.items

    @property
    def todo_items(self) -> list[TodoItem] | None:
        items = self.coordinator.data.items.get(self._list_id)
        if items is None:
            return None
        return [
            TodoItem(
                uid=item["id"],
                summary=item["name"],
                description=item.get("details") or None,
                status=TodoItemStatus.COMPLETED if item["checked"] else TodoItemStatus.NEEDS_ACTION,
            )
            for item in items
        ]

    def _current(self, uid: str) -> dict | None:
        return next((item for item in self.coordinator.data.items.get(self._list_id, []) if item["id"] == uid), None)

    async def async_create_todo_item(self, item: TodoItem) -> None:
        try:
            created = await self.coordinator.api.add_item(self._list_id, item.summary or "", item.description)
            if item.status == TodoItemStatus.COMPLETED:
                await self.coordinator.api.update_item(self._list_id, created["id"], checked=True)
        except MealPlannerError as err:
            raise HomeAssistantError(f"Eintrag konnte nicht angelegt werden: {err}") from err
        await self.coordinator.async_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        current = self._current(item.uid or "") or {}
        changes: dict = {}
        if item.summary is not None and item.summary != current.get("name"):
            changes["name"] = item.summary
        if (item.description or None) != (current.get("details") or None):
            changes["details"] = item.description or None
        checked = item.status == TodoItemStatus.COMPLETED
        if item.status is not None and checked != current.get("checked"):
            changes["checked"] = checked
        if not changes:
            return
        try:
            await self.coordinator.api.update_item(self._list_id, item.uid or "", **changes)
        except MealPlannerError as err:
            raise HomeAssistantError(f"Eintrag konnte nicht geändert werden: {err}") from err
        await self.coordinator.async_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        try:
            for uid in uids:
                await self.coordinator.api.delete_item(self._list_id, uid)
        except MealPlannerError as err:
            raise HomeAssistantError(f"Eintrag konnte nicht gelöscht werden: {err}") from err
        await self.coordinator.async_refresh()
