# Target Research Dossier

This document captures what can be learned before touching the real Windows
machine. It is based on public sources and the two local videos previously
inspected by the operator.

## Research Goal

The practical goal is not to reverse engineer the system internals first. The
goal is to narrow the Windows field test:

- Which windows and workflows should be probed first
- Which result channels are likely to work
- Which data shapes should the Agent expect
- Which UI labels and program names should be searched in UIA dumps

## Observed Programs

### KAPA HUB PLUS

Observed in local videos:

- Splash/login screen reads `KAPA HUB PLUS`.
- Splash text includes `Korea Association of Property Appraisers`.
- Main window is GIS/map heavy.
- A lower result grid appears after map/search interaction.
- The screen resembles a valuation information, map, and comparable-data
  retrieval workflow.

Public-source confirmation:

- KAPA training site has a `KAPA HUB PLUS 사용자교육` course.
- KAPA webzine describes KAPA-HUB desktop as a GIS-engine-based desktop system
  for visualizing nearby data.
- Public appraisal reports cite `감정평가정보센터(KAPA HUB PLUS)` or
  `감정평가정보(KAPA HUB PLUS)` as the source for comparable appraisal data.

### KAIS / 부동산통합업무시스템

Observed in local videos:

- Update/login dialogs read `부동산통합업무시스템`.
- Later frames show a map/property workflow.

Public-source confirmation:

- KAPA-HUB and 표준지 공시지가 app descriptions mention KAIS as the destination
  for uploaded app photos through KAIS input screens and attachment upload.
- Public appraisal reports distinguish data sources such as KAPA HUB PLUS and
  KAIS/감정평가정보체계.

## Likely Functional Areas

From public sources and video evidence, the important functional areas are:

- Login/session handling
- Program update wait screen
- GIS map window
- Address/parcel search
- Land/property layer display
- Comparable appraisal cases
- Comparable transaction cases
- Standard land/public land price workflow
- Photo/field-survey attachment linkage
- Excel/PDF/print/export paths

## Data Shapes To Expect

Public appraisal-report examples show KAPA HUB PLUS output being used as
structured comparable-data tables. Expect table-like outputs with fields such as:

- 소재지
- 용도지역
- 지목
- 이용상황
- 면적
- 평가액
- 사례가격
- 사례단가
- 기준시점
- 평가목적
- 비고
- 건물명 / 동 / 층 / 호
- 전유면적
- 사용승인일

This matters for the Agent because clipboard/export parsing should assume
tabular Korean text, not free-form OCR text.

## Automation Hypotheses

Prioritize these extraction paths in order:

1. Export file collection
   - Public appraisal usage implies the tool can produce or support structured
     case tables that may be copied into reports.
   - Look for Excel, CSV, PDF, print, report, or copy functions.

2. Clipboard table extraction
   - If the result grid is a standard Windows/grid control, `Ctrl+A`, `Ctrl+C`
     may yield tab-delimited or HTML table data.

3. UI Automation tree
   - Login fields and buttons may be accessible even if map content is not.
   - Result grids may or may not expose cell values.

4. Diagnostic screenshots
   - Use only to inspect black-screen behavior and rough state.
   - Do not depend on screenshots as the primary result path.

5. Network metadata
   - Useful for host/process timing and troubleshooting.
   - Do not assume HTTPS content will be visible because certificate pinning or
     security modules may exist.

## First UIA Search Terms

Search these strings in `/uia/dump` output and visible window titles:

- `KAPA`
- `HUB`
- `KAPA HUB PLUS`
- `KAPA-HUB`
- `부동산통합업무시스템`
- `KAIS`
- `검색`
- `주소`
- `지번`
- `소재지`
- `거래사례`
- `평가사례`
- `감정평가사례`
- `엑셀`
- `저장`
- `출력`
- `인쇄`
- `첨부파일`
- `앱사진`
- `일괄업로드`

## First Field-Test Workflow

On the real Windows machine:

1. Launch KAPA HUB PLUS.
2. Run `GET /windows` and confirm exact process/window title.
3. Run `/programs/kapa_hub_plus/probe`.
4. Dump the UIA tree for the main window.
5. Search UIA output for search/export/table terms.
6. Run a simple address/parcel search manually.
7. Click the result grid.
8. Send `Ctrl+A`, `Ctrl+C`.
9. Read `/clipboard`.
10. Try Excel/PDF/print/report export.
11. Run `/files/recent` and `/files/collect`.
12. Build the first `kapa_hub_plus.search_address` recipe from whatever worked.

Repeat the same for KAIS after identifying the exact window title and workflow.

## Known Public Sources

- KAPA-HUB desktop and mobile description:
  https://www.kapanet.or.kr/kapawebzine/data/136/sub/sub1_01_14.html
- KAPA HUB PLUS training page:
  https://edu.kapanet.or.kr/lecture.php?action=view&code=01&no=550
- KAPA related program/manual training list:
  https://edu.kapanet.or.kr/lecture.php?action=view&code=04&no=696
- KAPA-HUB iOS app:
  https://apps.apple.com/kr/app/kapa-hub/id1484598045
- 표준지 공시지가 iOS app:
  https://apps.apple.com/us/app/%ED%91%9C%EC%A4%80%EC%A7%80-%EA%B3%B5%EC%8B%9C%EC%A7%80%EA%B0%80/id1529579685?l=ko
- KAPA HUB 공시지가 Google Play listing:
  https://play.google.com/store/apps/details?hl=ko&id=com.kapahub.gongsi
- KAPA webzine mentioning ACAP and KAPA HUB PLUS demonstration:
  https://www.kapanet.or.kr/kapawebzine/data/156/sub/01.html

## Caveats

- Public pages do not reveal real Windows UI Automation IDs.
- App Store / Google Play screenshots are mobile app references, not the desktop
  Windows interface.
- Public appraisal reports show output data shapes, not internal APIs.
- Any final recipe must be validated on the authorized Windows desktop session.

