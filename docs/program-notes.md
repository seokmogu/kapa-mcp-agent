# Program Notes

These notes are based on the provided videos and public references. Treat them
as hypotheses until validated on the Windows machine.

## KAPA HUB PLUS

Observed in video:

- Splash/login screen reads `KAPA HUB PLUS`.
- Main interface appears to be GIS/map based.
- Later frames show a map with colored land/property layers and a result table.

Public information:

- KAPA training site lists `KAPA HUB PLUS 사용자교육`.
- KAPA webzine describes KAPA-HUB desktop as a GIS engine based system for map
  creation, map sheet printing/splitting, property big-data comparison,
  related/recommended information, and statistics.

Likely automation targets:

- Login window
- Address/search bar
- Map viewport
- Layer/category buttons
- Result table
- Excel/PDF/report export

## KAIS / 부동산통합업무시스템

Observed in video:

- Update dialog reads `부동산통합업무시스템`.
- Login dialog appears after update.
- Later frames show map and property-related forms.

Likely automation targets:

- Update completion wait
- Login window
- Map/search module
- Side property forms
- Result table or detail panel

## Capture Constraints

The videos indicate that capture or remote-control programs may cause blacked
out output. Prefer structured extraction:

- UI Automation
- Clipboard
- Exported files
- Program logs/cache where available

Avoid depending on screenshots as the primary result channel.

