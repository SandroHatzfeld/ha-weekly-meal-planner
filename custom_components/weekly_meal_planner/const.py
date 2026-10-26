"""Konstanten der Weekly-Meal-Planner-Integration."""

from datetime import timedelta

DOMAIN = "weekly_meal_planner"

CONF_PLAN_ID = "plan_id"
CONF_PLAN_NAME = "plan_name"

# Abfrage-Intervall: Änderungen aus der App erscheinen spätestens nach dieser Zeit in Home Assistant
UPDATE_INTERVAL = timedelta(seconds=30)

# Zeitraum der Gerichte, die regelmäßig geladen werden (Sensoren, nächster Termin im Kalender)
DISHES_PAST_DAYS = 7
DISHES_FUTURE_DAYS = 60

# die API liefert höchstens so viele Tage auf einmal
MAX_RANGE_DAYS = 366
