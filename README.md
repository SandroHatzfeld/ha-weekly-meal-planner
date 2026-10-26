# Weekly Meal Planner für Home Assistant

Bindet einen Plan aus dem [Weekly Meal Planner](https://github.com/SandroHatzfeld/weekly-meal-planner) in Home Assistant ein:

- **Einkaufslisten als To-do-Listen** – Einträge sehen, hinzufügen, umbenennen, Details (Beschreibung) setzen, abhaken, löschen.
  Funktioniert auch mit Assist: „Setze Milch auf die Einkaufsliste Supermarkt“.
- **Kalender „Gerichte“** – geplante Gerichte als ganztägige Termine.
- **Sensoren** – offene Einträge je Liste (mit Liste der Namen als Attribut), heutiges und morgiges Gericht.

Änderungen in der App erscheinen spätestens nach 30 Sekunden in Home Assistant, Änderungen in Home Assistant sofort in der App.

## Installation (HACS)

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/SandroHatzfeld/ha-weekly-meal-planner`, Typ **Integration**.
2. „Weekly Meal Planner“ installieren und Home Assistant neu starten.
3. In der App unter **Einstellungen → API-Tokens** ein Token erstellen.
4. Home Assistant → Einstellungen → Geräte & Dienste → **Integration hinzufügen** → „Weekly Meal Planner“:
   Adresse der App (z.B. `https://mealplanner.example.com`) und das Token eingeben, dann den Plan wählen.
   Für weitere Pläne die Integration erneut hinzufügen.

Wird das Token in der App gelöscht, fragt Home Assistant nach einem neuen.

## Entitäten (Beispiel Plan „WG“)

| Entität | Inhalt |
|---|---|
| `todo.wg_supermarkt` | Einkaufsliste „Supermarkt“ (Zustand = offene Einträge) |
| `calendar.wg_gerichte` | geplante Gerichte |
| `sensor.wg_offen_supermarkt` | Anzahl offener Einträge, Attribut `items` |
| `sensor.wg_heutiges_gericht`, `sensor.wg_morgiges_gericht` | Gericht(e) des Tages, Attribut `dishes` |

## Entwicklung

```bash
pip install pytest-homeassistant-custom-component
pytest
```
