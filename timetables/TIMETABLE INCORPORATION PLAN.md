# Timetable incorporation plan

**Status:** **built** 2026-09-14 (Phase 1 and Phase 2) · branch `timetable-incorporation`
Nothing committed, pushed or staged. Differences from the text below are listed in §13.

**Goal:**
1. Students ask the chatbot for an empty room, or for where a professor is at any time.
2. Later (Phase 2), the 3D model colours rooms free / in use / no data.

Everything below comes from a grill-me session with Khush, backed by the data analysis in §3–§5.
Research files and all 114 vision transcriptions are saved in `timetables/_work/` (see §9).

---

## 1. Decisions (locked in the grill)

| # | Question | Decision |
|---|---|---|
| D1 | Which rooms can be called **free**? | **Asymmetric.** Free only for rooms with their own room or lab sheet (or whose base room has one, e.g. A314A). Any other room can only be **in use** (some sheet books it) or **no data**. Never assume free. |
| D2 | Conflicting versions | **Newest file wins, per professor-hour.** Older claims for that professor at that hour are deleted, so the old room becomes free. Placeholders (N1, X2…) on older sheets are replaced by the real name from newer sheets. Every override goes in a report (§4.3). |
| D3 | Hour-wise states | **On disk:** one flat list of sessions (`fixtures/timetable.json`). **In memory:** the server builds the 60 hour-wise states (5 days × 12 hours) at startup. |
| D4 | Who computes "now" for map colours | **The page**, from a weekly schedule shipped with `/state`, using India time. Works offline, costs no extra requests. Chat answers are computed on the server, also in India time. |
| D5 | Phasing | **Phase 1:** data + chat. **Phase 2:** map colours. |
| D6 | Future re-extraction pipeline | **Deferred.** Build for the current timetables only. Khush will raise re-extraction later. |
| D7 | Professor with no lecture at that hour | Show **last + next class**, timetable facts only, then offer to route to the next one. No cabin guesses. |
| D8 | Professor names | Full names from their own sheets. Unknown name → ask for the professor's **initials as printed on the student's timetable**. Two or more matches → list them with initials and ask. |
| D9 | `MAKEUP LEC` slots | **Free, with a note** ("a makeup lecture may be held 15:00–16:00"). |
| D10 | Room halves (B115A/B115B, A314A/B/C…) | Each half has its own state. On the map, the box is **drawn split** into halves along its long side, A→B→C from the west/north end, and labelled as an approximation. |
| D11 | "Find me an empty room" | If no origin was given, **ask where they are**. Then show the **single nearest** free room by walking distance (networkx), draw the route, and ask: *"Is it free when you get there? Tell me if not and I'll find the next."* |
| D12 | Student says "no, there's a class in there" | Offer the **next-nearest** room only. Nothing is remembered, nothing logged. |
| D13 | Room kinds for free search | **Anything free:** classrooms and labs mixed, nearest first. |
| D14 | Off hours (weekend, before 7:00, after 19:00) and lunch | **Chat:** say so and still answer. Lunch is a normal answer, since rooms really are free. Weekend/night: *"No lectures are scheduled then, so by the timetable every room is free, but the building may be closed."* **Map:** plain model plus a banner (D19). |
| D15 | Professor lookup privacy | **Open to everyone, teaching slots only.** Gaps are phrased "no lecture scheduled", never "free" or "absent". No cabins. Worth a quick OK from the department before a wide launch. |
| D16 | Code home | New **`timetable.py`**: no network, no model, importable with no key (like `world.py`). `world.py` is untouched. |
| D17 | Professor or free room in the other building | Say it, then offer the gate: *"…is in A302, Aryabhatta building, until 12:00. Shall I guide you to this building's Main Entrance so you can get to the A building?"* No page switching. Free-room search covers **only the building you are in**. |
| D18 | Palette (Phase 2) | **P1 Violet**, see §7.2. |
| D19 | Map outside timetable hours | No availability colours, plus banner *"No lectures scheduled now · timetable as of 8 Sep 2026"*. |
| D20 | Viewing another time on the map | **Chat only.** "Show free rooms at 3pm Thursday" switches the map to that hour with a *"Showing Thu 15:00 · not live"* banner; tap the banner to go back to now. No time picker. |
| D21 | When colours are painted | **Toggle.** On by default. Desktop: tap the legend's *availability* row. Phones hide the legend, so on phones it's **chat only** ("hide free rooms" / "show free rooms"). |
| D22 | Mapping scope | **Every room code in any timetable**, but only where evidence pins it to a box (§5). No assumptions: an unpinned room is answered in chat by code and floor, with no map colour and no route. |

---

## 2. What is in `timetables/`

164 files, 20 MB: 162 PDFs and 2 PNGs. All are *Year 2026-2027, Semester ODD*.

| Folder | What | Files | Made | Format |
|---|---|---|---|---|
| `Class SY TY LY/` | Comp dept class timetables (SY/TY/LY A–D, FY M.Tech, LY Honors) | 10 PDF + 2 PNG | **Aug 21** | text PDF; PNGs are low-res screenshots |
| `Classrooms 201-205 301 214/` | Comp classroom sheets | 7 | **Aug 21** | text PDF |
| `Labs/` | Comp lab sheets (A105, B107A … B217B) | 22 | **Aug 21** | text PDF |
| `FACULTIES updated on 03.09.2026/` | 5 Comp professors (GJS, NKS, PJS, PSG, VPV) | 5 | **Sep 3** (PSG **Sep 8**) | text PDF |
| `Regular TT (w.e.f. 31st Aug)/CLASSROOM/` | FY (Science & Humanities) room sheets | 19 | **Aug 29** | outlines* |
| `…/DIVISION/` | FY divisions A–R | 18 | **Aug 29** (DIV H re-issued **Sep 1**) | outlines* (H, R have text) |
| `…/FACULTY/{BE,BEE,EC,ED,EP,Math,PBL,PCS,SPM}/` | S&H professors | 81 | **Aug 29 – Sep 1** | mostly outlines*; 4 Excel-made |

\* Produced with *Microsoft Print to PDF*, which turns text into drawn outlines, so there is no text layer.

**Totals:**
- 48 room/lab sheets (48 distinct rooms).
- 86 professor sheets: 70 named people, 15 placeholders, 1 duplicate.
- 30 class/division sheets.
- 141 distinct room codes.
- 159 professor codes appear somewhere; most Comp professors appear only as initials.

**Recency**, newest first:
1. Comp professor sheets (Sep 3–8)
2. S&H professor sheets (Aug 29 afternoon – Sep 1)
3. FY room/division sheets (Aug 29 morning)
4. Comp room/lab/class sheets (Aug 21)

File age is the PDF's own creation timestamp (PNGs use file mtime).

**How the data was read** (one-off, for this semester):
- **58 text PDFs:** read exactly by table geometry with PyMuPDF `find_tables()`, which handles merged cells and batch sub-columns.
- **104 outline PDFs + 2 PNGs:** transcribed by six Claude vision agents.
- **Accuracy check:** 3 text PDFs were also given to the agents blind. Result **84 of 84 cells exact (100%)**, including merged spans and sub-columns.

---

## 3. How well the sources agree

Checked every hour covered by **both** a room sheet and a professor sheet: 1,519 checks.

| Direction | Agree |
|---|---|
| Professor sheet → the room's own sheet | **718 / 780 = 92.1%** |
| Room sheet → that professor's own sheet | **722 / 739 = 97.7%** |

**What the mismatches are:**
- **56 placeholders:** the older room sheet says "N1"/"N3" (unnamed new faculty). The newer professor sheet names the real person, e.g. RUA. The room is booked either way.
- **~17 real schedule changes (~1%)**, e.g.:
  - The Sep 3 Comp sheets moved LY elective hours out of B112/B111/B110A into A302/A303/A305/B302/B304/B205.
  - FY batches were added into Comp labs the Aug 21 lab sheets don't know about.
  - KDM's Monday 9–11 lab in B207C was dropped.
  - AMG→RUA swap in B501, Monday 4pm.
- **N1 "elsewhere"** hours: N1 is a pool of several new faculty (its sheet claims a load of 104 hours), so N1 appearing in several rooms at once is expected.

**In every mismatch where the files have different dates, the professor sheet is the newer one.** No old professor sheet contradicts a newer room sheet. That is the evidence for D2.

**Blind spots (evidence for D1):**
- Professor sheets show 394 hours of IT/EXTC/Mech/RAI/CSBS classes.
- **384** of those are in rooms with no room sheet (B303, A309, B414…). Other departments' timetables are not in this folder, so those rooms can never honestly be called free.
- The **10** that fall in our rooms are all already on those room sheets.

---

## 4. Cleaning rules (applied at build time, once)

### 4.1 Normalise each cell
- Join line-wrapped codes: `NF- 2` → `NF-2`, `ASL- I` → `ASL-I`, `MCE- I_TUT` → `MCE-I_TUT`.
- Strip stray punctuation: `A104.` → `A104`.
- Room code = `[AB]\d{3}[A-Z]?` or `CCF_A` / `CCF_B`. Letter suffix = half of the base room.
- `B210.pdf` is **Room B201** inside; the header wins over the file name.
- `E201`/`E117A`-style reads on the blurry LY COMP PNG → `B`. No E building exists.
- `MDM -- --`, `Minor -- --`, `EL -- --`: no room, no professor. Ignored for rooms; not searchable.
- `LUNCH BREAK` is never a session.
- Placeholders are **not people** but **do occupy rooms**:
  - `X1 X2 X3 X7 X9 N1 N3 NF-1 NF-2 NF-3 BN1 BN2 CN1 CO1 CO2 CO3 EN1 MN1 PN1 PN2`
  - cells reading `..-`, `--`, `<->`, and headers like "pqrs", "xyz", "NEW FACULTY", "EC FACULTY 1".

### 4.2 Resolve
1. Every cell becomes an hourly claim: `(day, hour, room, professors, class/batch, subject, file, file time)`.
2. A professor with **two sheets** (SRJ: `SPM/SRJ.pdf` Aug 29 vs `BEE/SRJ.pdf` Aug 30, same person, same load): the newest sheet wins.
3. **Newest wins per professor-hour.** A claim from a room/class sheet is dropped when **every** real professor it names has a *newer* own sheet that doesn't place them in that room (or its half) at that hour.
4. Placeholder on an older sheet + a real professor on a newer sheet in the same room-hour → one session carrying the real name.
5. Everything else is kept and merged. The same event from room, class and professor sheets collapses to one session with all sources listed.
6. Result from the prototype: 4,197 hourly claims → 4,157 kept, 40 dropped. 1,918 occupied room-hours.

### 4.3 Override report: all drops, for Khush to eyeball

| When | Old claim (file, date) | Newest professor sheet says |
|---|---|---|
| Tue 11–13 | B110A · PSG (`Labs/B110A`, Aug 21) | A302 |
| Fri 10 | B111 · NKS (`Labs/B111`, Aug 21) | A305 |
| Thu 10 | B112 · NKS (`Labs/B112`, Aug 21) | A302 |
| Fri 10 | B112 · GJS (`Labs/B112`, Aug 21) | A303 |
| Tue 12 | B112 · VPV (`Labs/B112`, Aug 21) | A302 |
| Wed 12 | B112 · VPV (`Labs/B112`, Aug 21) | B302 |
| Thu 12 | B112 · VPV (`Labs/B112`, Aug 21) | B205 |
| Tue 16 | B112 · GJS (`Labs/B112`, Aug 21) | B304 |
| Mon 9–11 | B207C · KDM (`Labs/B207C`, Aug 21) | not teaching then (KDM sheet Aug 29) |
| Tue 11–13 | CCF_B · PVK (`DIV R`, Aug 29 09:19) | not teaching then (PVK sheet Aug 29 12:39) ⚠ same-day files, check this one |
| Mon 16 | B501 · AMG (`CLASSROOM/B501`, Aug 29) | not teaching then; RUA's Sep 1 sheet has B501 |
| all | `SPM/SRJ.pdf` (Aug 29) | superseded by `BEE/SRJ.pdf` (Aug 30) |

The same drops also remove the matching lines from the Aug 21 class sheets, 23 hourly records in total.

---

## 5. Room code → 3D model node

Rule (D22): a code gets a node only when evidence pins it to one box. There are 141 codes:

| | Mapped | Unmapped (chat by code + floor only) |
|---|---|---|
| Can be free (own sheet) | **47** | **9**: A102, A103, A104, A105, A116, A116A, A116B, A308, B119 |
| In use only | **53** | **32**: A013 A106 A120 A120A A122 A203 A204 A205 A206 A209 A210 A213 A216 A218 A223B A302 A303 A304 A305 A309 A313 A402 A403 A406B A407 A409A A410A A411A A412A A412B B014 B307C |

**Floor codes:** first digit + 1 = the model's `floor`. A0xx/B0xx = ground (floor 1); B1xx = L1 (floor 2); and so on.

### 5.1 Bhaskaracharya: number printed on the escape board (auto)
| Codes | Node |
|---|---|
| B101–B105 (+ B103A, B105A as halves) | `lecture_hall_101…105_f2` |
| B112 | `pg_seminar_hall_112_f2` |
| B115A/B · B116A/B · B117A/B | `web_technology_lab_115_f2` · `database_management_system_lab_116_f2` · `multimedia_system_lab_117_f2` |
| B201–B205 | `lecture_hall_201…205_f3` |
| B214 · B215A · B216A · B217A/B | `modeling_simulation_lab_214_f3` · `analysis_algorithms_lab_215_f3` · `artificial_intelligence_robotics_lab_216_f3` · `computer_comm_networking_lab_217_f3` |
| B301–B305 | `lecture_hall_301…305_f4` |
| B310 · B311 · B312 · B313 · B314 | `project_laboratory_department_store_310_f4` · `tutorial_room_1_311_f4` · `pg_seminar_hall_312_f4` · `high_performance_computer_lab_313_f4` · `advance_database_management_system_314_f4` |
| B315A/B · B316A/B · B317A | `analysis_design_lab_315_f4` · `image_processing_lab_316_f4` · `operating_system_lab_317_f4` |
| B501 B502 B504 B505 | `lecture_hall_501/502/504/505_f6` |
| B510A/B · B511 B512 · B513 · B514 · B515 | `circuit_laboratory_510_f6` · `research_centre_511_512_f6` · `ni_academy_513_f6` · `basic_communication_lab_514_f6` · `robotics_lab_515_f6` |
| B010 B010A | `fluid_mechanics_fluid_machinery_lab_10_f1` ("10" printed on the ground-floor board) |

### 5.2 Bhaskaracharya: same layout on every floor, **confirmed by Khush**

The boards leave the west wing unnumbered, so these follow the per-floor layout pattern. **Worth a walk past the doors;** each is a one-line fix in `mapping.json`.

| Codes | Node |
|---|---|
| B110A/B/C (118 hrs FY programming labs) | `comp_programming_lab_f2` |
| B109 | `object_oriented_analysis_design_lab_f2` |
| B107A/B | `devices_communication_lab_f2` |
| B111 | `tutorial_room_f2` |
| B210A/B · B209 · B207A/B/C · B212 | `pg_computer_centre_f3` · `project_laboratory_f3` · `microprocessor_lab_f3` · `embedded_system_lab_f3` |
| B309 | `information_security_lab_f4` |
| B403 · B404 · B405 | `lecture_hall_4f_3_f5` · `lecture_hall_4f_4_f5` · `lecture_hall_4f_5_f5` |
| B407 B407B B407C B407L · B409 · B410A · B411 · B413 | `power_electronics_lab_f5` · `project_lab_f5` · `digital_design_lab_f5` · `tutorial_room_f5` · `pg_seminar_hall_f5` |
| B414 · B416A/B · B417A/B | `dept_computer_centre_design_development_lab_f5` · `image_processing_lab_f5` · `signal_processing_lab_f5` |
| B507 B507A B507B (125 hrs FY MS-I) | `ug_seminar_hall_f6` |
| B007 · B009 · B011 | `machine_room_f1` · `dynamics_of_machinery_lab_f1` · `metrology_measurement_lab_f1` |

### 5.3 Aryabhatta: pinned by the timetables themselves
None of the five Aryabhatta boards print room numbers (only "Room No. 115" and "Room No. 123", neither in any timetable). So a code is mapped only when **who teaches there** leaves exactly one candidate box:

| Codes | Evidence | Node |
|---|---|---|
| A009A/B | 162 hrs, all Chemistry (EC) faculty | `applied_chemistry_lab_f1` |
| A016A/B | 162 hrs, all Physics (EP) faculty | `applied_physics_lab_f1` |
| A010 | BEE LAB, BEE faculty | `basic_electronics_lab_f1` |
| CCF_A / CCF_B | "CCF", FY programming labs | `common_computer_facility_f1` (halves) |
| A314 + A314A/B/C | ED LAB, Drawing faculty; the only drawing hall | `drawing_hall_f4` (thirds) |

**Everything else in Aryabhatta stays unmapped:** A102–A105, A116, A308, A2xx, A3xx lecture rooms, A4xx labs. Chat still answers for them, e.g. *"A103 (Aryabhatta L1) is free until 14:00 by the timetable. I can't place it on the model yet."* To fill one in later, add a line to `mapping.json` and rebuild. No code change.

---

## 6. Phase 1: data + chat

### 6.1 `fixtures/timetable.json` (generated once; the only thing the app reads)
```json
{
  "semester": "2026-27 ODD", "effective": "2026-08-31", "as_of": "2026-09-08",
  "sources": [{"id": 17, "file": "Labs/B112.pdf", "kind": "room", "header": "Room: B112",
               "created": "2026-08-21T07:23", "sha256": "…"}],
  "rooms":  {"B110A": {"building": "bhaskaracharya", "node": "comp_programming_lab_f2", "floor": 2, "own_sheet": true},
             "A103":  {"building": "aryabhatta", "node": null, "floor": 2, "own_sheet": true}},
  "profs":  {"PSG": {"name": "Dr Pradnya Gotmare"}, "SNJ": {"name": null}},
  "sessions": [{"day": "Tue", "from": 11, "to": 13, "room": "A302", "profs": ["PSG"],
                "who": "LY B. Tech COMP", "subject": "SDT", "note": "", "src": [4, 23]}],
  "overrides": [{"day": "Fri", "hour": 10, "room": "B112", "prof": "GJS", "src": 17, "now": "A303", "by": 19}]
}
```
- Hours are integers 7–19; a 2-hour lab is **one** row (D3).
- `note` is set for `MAKEUP LEC`.
- `sources` keeps provenance without committing the PDFs (§9).
- Expected size: roughly 200–300 KB.

### 6.2 `timetable.py` (new, ~110 lines, no network, no model)
- `load(path)` → object with `rooms`, `profs`, `sessions` and **`states[(day, hour)] = {"rooms": {code: [session]}, "profs": {code: [session]}}`**, the 60 hour-wise states built in one pass.
- `status(code, day, hour)` → `"in_use" | "free" | "no_data"`, plus `until` and `note`. Free only if `own_sheet` (the code or its base room); makeup = free with note (D1, D9).
- `free(building, day, hour, skip=())` → free codes in that building.
- `where(prof, day, hour)` → current session, plus last and next the same day (falling back to next weekday).
- `find_prof(text)` → matching codes: exact initials first, then name tokens, then `difflib.get_close_matches` (stdlib, as `world.py` already uses). Deterministic, so the model never invents a professor.
- `weekly(building)` → per node: parts + weekly busy spans (Phase 2 only).
- `if __name__ == "__main__":` self-check with asserts, e.g.:
  - B112 is free Fri 10:00 (override applied)
  - `where("PSG","Tue",11)` is in A302
  - B115A in use while B115B free at a known hour
  - A103 free/in-use has `node is None`
  - a MAKEUP hour is free with a note

### 6.3 `gemini.py` (+~35 lines)
- `CHAT_ACTIONS` gains `free_room`, `find_prof`, `availability`.
- `ChatCommand` gains:
  - `prof_query: str`: the name or initials exactly as the student said them
  - `day: str`: `Mon`…`Sun` | `today` | `tomorrow` | `""`
  - `time: str`: `HH:MM` 24h, or `""` for now
  - `skip_rooms: list[str]`: room codes already offered in the conversation that the student said were not free
  - `on: bool`: for `availability`
- Prompt lines:
  - "find/any empty/free room or lab" → `free_room` (from_id = where they are, if said)
  - "where is / find prof X / is X free" → `find_prof`
  - "no, there's a class" after a suggestion → `free_room` with that room in `skip_rooms`
  - "hide/show free rooms" → `availability`
  - "show me what's free at 3pm Thursday" → `free_room` with day/time
- **Validation, twice (CLAUDE.md):**
  - `day`/`time` must parse, otherwise now.
  - Every `skip_rooms` code must exist in `timetable.rooms`, otherwise dropped.
  - `prof_query` is plain text, resolved deterministically by `find_prof`. No professor id ever comes from the model.

### 6.4 `main.py` (+~80 lines)
- Load `fixtures/timetable.json` once, if present (same pattern as the building fixtures).
- IST clock: `datetime.now(timezone(timedelta(hours=5, minutes=30)))`. Stdlib, and India has no DST. `zoneinfo` would need the `tzdata` package on Windows, so the fixed offset is used on purpose.
- **`free_room`:**
  - No origin → `need_origin` (existing flow).
  - Candidates = `tt.free(this building, day, hour, skip)`.
  - Mapped ones are ranked by `w.route(origin, node)["distance_m"]` (networkx; ~50 Dijkstras on ~200 nodes is trivial).
  - Take the nearest, draw its route, reply *"Lecture Hall 203 (B203) is free until 14:00 — drawn on the model. Is it free when you get there? Tell me if not and I'll find the next."*
  - A half names its code: *"B115B (Web Technology Lab 115) is free; B115A is in use."*
  - No mapped free room → name unmapped free codes by floor.
  - None at all → say so.
  - Off hours → D14 sentence, then answer.
  - Returns `at: {day, hour}` when the time was not now (for Phase 2).
- **`find_prof`:**
  - `find_prof` returns 0 matches → *"I don't recognise 'Joshi ma'am'. What are their initials on your timetable (e.g. SRJ)?"*
  - 2+ matches → list with initials.
  - 1 match → the forms below.

| Case | Reply |
|---|---|
| teaching, mapped room, this building | *"Dr Pradnya Gotmare (PSG) has SY COMP A1 DSM in Database Management System Lab 116 (B116A) until 13:00, per the timetable. Shall I take you there?"* |
| teaching, other building | *"… is in A302, Aryabhatta building, until 12:00. Shall I guide you to this building's Main Entrance so you can get to the A building?"* |
| teaching, unmapped room, this building | *"… is in A302 (Aryabhatta, L3) until 12:00. I can't place A302 on the model yet."* |
| no lecture that hour | *"No lecture scheduled for Dr Pradnya Gotmare (PSG) at 11:00. Last: 9:00–11:00 in B116A; next: 12:00 in B203. Shall I take you to B203?"* |
| weekend / after hours | *"No lectures are scheduled on Saturdays. Dr …'s next lecture: Mon 9:00 in B116A."* |
| initials-only professor (no own sheet) | same forms, using the initials |

- A "yes" to any offer needs **no pending state**: the offer names the place and sits in the history, so the model returns an ordinary `route`, exactly like the existing gate offer.
- **`availability`:** returns `{"availability": on}`; the page flips the layer (phones, D21).
- The model's prose is still never trusted. Every sentence above is written from `timetable.py` and `world.py`.

### 6.5 Verify Phase 1 (paste real output before calling it done)
```bash
python timetable.py                    # self-check asserts
python -c "import gemini"              # no network at import
python -c "import world; w=world.load('fixtures/building.example.json'); print(w.route('entrance','lab_302'))"
```
Then Khush restarts uvicorn (backend is not `--reload`) and runs ~8 chat probes: free room with/without origin, "no there's a class", PSG now / at 11:00 / Saturday, "Joshi ma'am", a professor in the other building, an unmapped A room.

---

## 7. Phase 2: map colours

### 7.1 Data to the page
- `/<bldg>/state` gains `timetable: {as_of, nodes: {node_id: {parts: [{code, own_sheet, busy: {"Mon": [[9, 11, "SY COMP A1 DSM · PSG", note]]}}]}}}` from `tt.weekly()`.
- `main.py` merges it in; `world.py` is not touched.
- `sw.js`: bump `trancelucent-state-v1` → `v2` so the old cached `/state` is dropped.

### 7.2 Palette: P1 Violet (D18)
State is carried by the **outline**. Low-alpha fills barely register (research: a 7% fill is 1.06–1.11:1 against the background).

| State | Stroke | Fill | Extra cue | Contrast vs `#07090c` |
|---|---|---|---|---|
| free | `#5ef2a8` (the app's existing unused `--ok`) | 20% | "free till 14:00" label | 13.99:1 |
| free, class starts within 15 min | `#ffb42f` | 12% | "class 14:00" label | 11.22:1 |
| in use | `#9d6bdb` | 7% | "in use till 13:00" label | 5.28:1 |
| no data | `#8fa3ae` (today's room grey) | 4% | **dashed** outline | 7.61:1 |
| blocked | `#ff3b5c` unchanged, wins over availability | | | |
| route / current step | `#00e5ff` unchanged, wins over everything | | | |

- **Colour-blind check:** Machado 2009 simulation, full severity. Under deuteranopia and protanopia, in-use turns blue and stays clearly apart from free (beige); minimum ΔE ≈ 15 across all pairs.
- **Why not red:** red already means blocked. **Why not P3's grey in-use:** it sits too close to free for colour-blind users.
- The preview page is `timetables/_work/palette-preview.html`.

### 7.3 `trancelucent.html` changes (+~90 lines, new `/* ---- timetable ---- */` banner region)
- **Clock:** `Intl.DateTimeFormat('en-GB', {timeZone:'Asia/Kolkata', …})` gives day, hour and minute. `setInterval(()=>{dirty=true}, 60000)` keeps "now" live (convention 2: `dirty=true`).
- **`AT`:** `null` = live; `{day, hour}` = set by a chat reply's `at` (D20).
- **`tone(n, part)`:** new checks slot **after** blocked, STEPNODE, ROUTE and HOVER/FROM/TO, and **before** the default grey. Only applies while the layer is on and inside timetable hours.
- **Split boxes (D10):** in `render()`'s plain-box branch, a node with 2–3 parts pushes one slab per part along the long axis. The part index rides in the slab tuple, and `face()` asks `tone(n, part)`.
- **Legend (desktop):** `.hud.bl` gains *free / in use / no data* rows and an *availability* row that toggles (`aria-pressed`). The choice is remembered in `localStorage` under `twin.avail` (per-viewer convenience, wrapped in try/catch like the existing prefs).
- **Phones:** legend stays hidden; the chat `availability` action flips the same flag (D21).
- **Banner** (small HUD line): *"Showing Thu 15:00 · not live"* or *"No lectures scheduled now · timetable as of 8 Sep 2026"*. Tapping it sets `AT=null`.
- **Hover/tap label** appends the state: `Lecture Hall 203 · free till 14:00`.

### 7.4 Verify Phase 2
- Extract the inline script and `node --check` it (context.md recipe).
- Playwright at 1400×900 and 390×844: screenshots, empty console.
- Check a known in-use hour, a known free hour, a split box, the off-hours banner, and "show free rooms at 3pm Thursday".

---

## 8. File-by-file change list

| File | Phase | Change | ~Lines |
|---|---|---|---|
| `fixtures/timetable.json` | 1 | new, generated from `timetables/_work/` | data |
| `timetable.py` | 1 | new module (§6.2) | 110 |
| `gemini.py` | 1 | 3 actions, 5 fields, prompt lines, validation | 35 |
| `main.py` | 1 (+2) | load, IST clock, 3 handlers; merge `timetable` into `/state` in phase 2 | 80 + 5 |
| `README.md` | 1 | short "Timetables" section; fix the stale "this repo is public" line (`gh` says PRIVATE) | 20 |
| `.gitignore`, `.dockerignore` | 1 | §9 | 4 |
| `.claude/CLAUDE.md`, `.claude/context.md` | 1–2 | ownership row for `timetable.py`; a short note on the timetable region (both gitignored) | 10 |
| `trancelucent.html` | 2 | §7.3 | 90 |
| `sw.js` | 2 | state cache v2 | 1 |

No new dependencies. PyMuPDF/pdfplumber were used only for the one-off extraction, not at runtime, and nothing is added to `requirements.txt`. `world.py` is untouched.

**`SPEC.md`'s out-of-scope list** names "PDF ingestion". The app never parses a PDF: extraction was a one-off offline step, and the runtime only reads JSON. (SPEC is historical intent anyway; README describes the live system.)

---

## 9. Git decision: what gets committed (delegated to me, reasoning below)

**Do NOT commit the raw timetable files. Commit the derived JSON.**

```gitignore
# raw timetable PDFs: this semester only, re-issued often, never read by the app
timetables/*
!timetables/*.md
```
Also add `timetables` to `.dockerignore`, because `COPY . .` would otherwise ship 20 MB into the image.

**Why:**
1. **History bloat that never goes away.** 20 MB of binaries today, and every re-issue adds another full copy. Git keeps every version forever, and private repos still clone all of it. `photos/` (15 MB) was a one-off that never changes; timetables are the opposite.
2. **Stale versions mislead.** The folder already mixes superseded files (Aug 21 room sheets vs Sep 3 professor sheets, two SRJ sheets). Committing them makes "which is current" a question every reader has to re-answer.
3. **The app never reads them.** `fixtures/timetable.json` is the single input and gets committed (the teammate and the deploy need it).
4. **Provenance is kept without the blobs.** `sources[]` in the JSON records file path, creation time and sha256, so any session traces back to a PDF someone holds locally.
5. **Personal data minimised.** The repo is private, but the JSON carries only what the app needs.

**Also kept locally (gitignored with the rest of `timetables/`):**
- `timetables/_work/`: the 114 vision transcriptions, the text extraction, and the prototype scripts (`norm.py`, `merge.py`, `resolve.py`, `mapping.py`, `sync2.py`, …) plus `mapping.json`. This lets `fixtures/timetable.json` be rebuilt after a mapping fix without redoing hours of vision work. Turning this into a proper pipeline is deferred (D6).

**Trade-off accepted:** a teammate who wants to rebuild needs the PDFs from wherever they were shared (WhatsApp/Drive), not from git.

This plan file itself is un-ignored (`!timetables/*.md`), so Khush can choose to commit it. All git actions stay with Khush.

---

## 10. Data problems found (not bugs to fix in code)
- `Classrooms…/B210.pdf` is **Room B201**; the folder name says 201–205.
- `SRJ` has two sheets (SPM Aug 29, BEE Aug 30); newest used.
- 15 placeholder professor sheets. `N1` claims a load of 104 hours but has 34 cells. `N3` is named "pqrs".
- 4 Excel-made sheets (`C_G`, `PHD`, `PMP`, `SKD`): 9:00–18:00 grid, no full names, one reads "FY B. Tech SAII I" (typo for SAH I).
- The two PNGs (`LY B. Tech COMP .png`, `TY B tech COMP Honor.png`) are low-res composites; 15 transcription doubts. Oldest source, and overridden by professor sheets wherever they overlap. `LY … Honors.pdf` has a sliver Monday column (11 sub-cells that may belong to Monday).
- Same session printed in different rooms on different days (X3 CEPDT in B417B Tue / B407 Fri; VAB COMP C DSM in B214 / B204). Kept as printed.
- A116's room sheet vs A116A/A116B on professor sheets, and A314 vs A314A/B/C: halves of the sheet's room.
- Sessions exist at 7:00–9:00 (JRS, DRU, DIV Q), so all hours 7–19 are live. No Saturday sessions anywhere.
- `README.md` still says "this repo is public"; `gh repo view` reports **PRIVATE**. The fly.io URL is still public.

## 11. Deferred / not in this build
- A repeatable re-extraction pipeline for next re-issue (D6; Khush will raise it).
- Semester end date, holidays, exam weeks: no data. Answers say "per the regular timetable".
- Professor cabins / staff rooms: no data (D7).
- Other departments' room sheets (IT, EXTC, Mech…). Their rooms stay "no data" until those PDFs exist.
- Mapping the 41 unpinned codes (§5), one line each in `mapping.json` once someone checks the doors.

## 12. Build order (after review)
1. `.gitignore` / `.dockerignore` (§9). Move nothing else.
2. Generate `fixtures/timetable.json` from `timetables/_work/` (normalise → resolve → map → provenance). Print the counts and the override report and diff them against §4.3.
3. `timetable.py` + self-check → `python timetable.py`.
4. `gemini.py` → `python -c "import gemini"`.
5. `main.py` → Khush restarts uvicorn → chat probes (§6.5).
6. README + `.claude` notes.
7. **Stop for review.** Then Phase 2: `/state` merge, `sw.js`, `trancelucent.html`, then verify (§7.4).

---

### Appendix: UX research sources (from the research pass)
- **Free/soon/busy states and "free till" wording:**
  - Freerooms (UNSW): <https://devsoc.atlassian.net/wiki/spaces/F/pages/1311597/Backend+Server+API>
  - illiniSpots: <https://github.com/plon/illinispots/blob/main/README.md>
  - Teams panels (green available / purple reserved, 15-minute rule): <https://learn.microsoft.com/en-us/microsoftteams/devices/use-teams-panels>
- **WCAG 1.4.1 use of colour:** <https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html>
- **WCAG 1.4.11 non-text contrast:** <https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html>
- **Colour-blindness simulation (Machado 2009):** <https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html>
- **Prevalence in India** (roughly 4–11% of men): <https://pmc.ncbi.nlm.nih.gov/articles/PMC3595632/>
- **Dashed lines for uncertainty:** <https://richardbrath.wordpress.com/2021/05/27/dashed-and-patterned-lines-for-visualization-aka-1d-texture/>
- **Showing absolute "as of" dates:** <https://developers.dhis2.org/design-system/patterns/designing-with-time/>
- **Telling users when missing data calls for their own judgment:** <https://pair.withgoogle.com/chapter/explainability-trust/>
- **Disambiguation with "none of these":** <https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/cux-disambiguate-intent>

---

## 13. Build notes (what differs from the plan above)

**Data shape**
- `rooms` in `fixtures/timetable.json` is keyed by **part** (a half like `B115A`, or a whole room).
  Each part lists the printed `codes` that book it: a booking of `A314` books all three thirds.
- A session carries one `what` string (e.g. "SY COMP A1 DSM") instead of separate who/subject fields.
- **Final counts:** 1,363 sessions, 133 room parts (51 with their own sheet, 94 on a model node),
  138 professor codes (66 with a full name), 40 dropped claims.
  The `overrides[]` list matches §4.3.

**Chat and page fixes beyond the plan** (bugs found while building)
- The existing "Where are you now? … click it on the model" reply was a dead end: a tap never
  reached the chat. The page now sends the tapped space as `here` with each message, and a tap
  right after that question re-asks it.
- Aryabhatta's gate offer and default route start used "West Exit", the first entrance node in
  the file. `main.py` and the page now prefer the entrance named "Main" ("Main Entrance Landing").
- After "Did you mean A or B?", picking one ("the second one") resolves via a prompt rule.

**Phones**
- Availability text sits in the top-left hint line (`#prompt`), not on the room label, where it
  ran off a 390px screen.

**Verified** (outputs pasted in the build session)
- `python timetable.py` self-check.
- Offline probes of every chat branch: `timetables/_work/probe_chat.py`.
- Live Gemini conversations: `timetables/_work/probe_live.py`.
- `node --check` on the page script and `sw.js`.
- Playwright at 1400×900 and 390×844 with an empty console: live colours, split halves, the
  "not live" and off-hours banners, the legend toggle, and the tap-to-answer flow.
