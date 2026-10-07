# Trancelucent: context for coding agents

This is the **only** agent file in the repo. `README.md` is for humans; this is for agents.

## Keep this file current (required)

- Any change that alters behaviour, a rule, a file, an endpoint or a gotcha described here
  **updates this file in the same commit**. Stale context is worse than none.
- Do **not** add other agent files to the repo: no `*PLAN.md`, notes, briefs, scratch files,
  screenshots or agent config. Put lasting knowledge here; delete throwaway files before committing.
- Never write a person's name or a log of who asked for what in code comments, docs or commit
  messages. A comment states what and why: `// kept blue intentionally: red means blocked`,
  never `// X said via grill-me to keep this blue`.

## Working rules

- Commits: Conventional Commits (`type(scope): subject`), no AI attribution trailer. Work on a
  feature branch; `main` only changes through pull requests. Commit or push only when asked.
- Ask before decisions that change what the product is: a new endpoint, file, dependency, data
  shape, or a visible UI/interaction change. Routine commands need no permission.
- Paste real output before calling anything done. "It should work" is not a result.
- The repo is public. Secrets live only in `.env` (gitignored) and fly secrets.

## What it is

Indoor wayfinding for two KJSSE buildings, served at `/aryabhatta` (A building, 188 spaces,
5 levels) and `/bhaskaracharya` (B building, 223 spaces, 7 levels). A hand-written 3D view,
Dijkstra routing over a `networkx` graph, a plain-English chat that parses intent with Gemini,
and room availability from the semester timetable. It runs as a PWA and is deployed on fly.io.

**The model parses intent. Deterministic code does geometry.** The model is never asked for a
route, a distance or a coordinate.

## Run and verify

```bash
set -a; source .env; set +a && python -m uvicorn main:app --port 8000          # desktop
python -m uvicorn main:app --host 0.0.0.0 --port 8000                          # reachable from a phone on the LAN
```

Neither runs with `--reload`: a change to `main.py`, `gemini.py`, `world.py`, `timetable.py` or
`fixtures/` needs a restart. `trancelucent.html` and `index.html` are served `no-store` from disk,
so they are live on a page reload. Don't report backend behaviour checked against an old process.

```bash
python -c "import world; w=world.load('fixtures/building.example.json'); print(w.route('entrance','lab_302'))"
python -c "import gemini"            # must not touch the network at import
python timetable.py                  # self-check, prints ok: ...
# a broken inline <script> fails silently (the page just stops painting), so parse it:
python -c "import re;s=open('trancelucent.html',encoding='utf-8').read();open('_t.js','w',encoding='utf-8').write(re.findall(r'<script>(.*?)</script>',s,re.S)[-1])" && node --check _t.js && rm _t.js
```

## Files

| file | what |
|---|---|
| `main.py` | FastAPI wiring and every chat reply, written from `world` and `timetable`. `mount_building()` registers `/x`, `/x/state`, `/x/route`, `/x/block`, `/x/chat` per building. Also `/`, `/buildings`, `/health`, `/robots.txt`, `/sitemap.xml`, `/analytics.js`, the PWA assets. |
| `world.py` | Graph, Dijkstra, passable/accessible state, per-visitor blockages. No network, no model. |
| `timetable.py` | Hour-wise room states, free rooms, where a professor is. No network, no model. |
| `gemini.py` | The chat prompt and Pydantic schema. `MODEL = "gemini-robotics-er-2-preview"`, never the `-streaming-` variant (no structured output). Falls back through `GEMINI_API_KEY_2`, `_3` on a 429. |
| `trancelucent.html` | The 3D view: projection, rendering, routing UI, chat, availability, phone shell. One file serves every building. |
| `index.html` | Landing page: pick a building. |
| `sw.js`, `manifest.webmanifest`, `icon-*.png` | PWA. |
| `fixtures/building.*.json` | The world models. `fixtures/timetable.json`: the semester timetable. |
| `photos/plans/` | The emergency escape-route boards the models were built from. |
| `timetables/` | Gitignored. Raw timetable PDFs and `_work/` (the one-off extraction; `_work/build.py` rebuilds `fixtures/timetable.json`, `_work/mapping.json` maps room codes to nodes). |

## Invariants that still hold

- No database: all state is the fixture files loaded into memory at startup. No build step, no
  npm, no bundler. Python dependencies are exactly `requirements.txt`; adding one needs asking.
- Every model response is validated twice: Pydantic schema, then every returned id checked with
  `world.has()` (timetable codes against the timetable). Anything unknown becomes `"unknown"`.
  A professor is never an id from the model: the name is copied as typed and
  `timetable.find_prof` matches it.
- Prompts are built from the world model at call time; no id is hardcoded in a prompt.
- Building files are data. Change them only when asked, and keep: `xy` equals the rect centre,
  no rect overlaps, nothing outside the viewbox.
- Chat replies never contain em dashes, en dashes or `--` (they read as machine-written).
  `main.py`'s `plain()` is the single exit every reply passes through; write replies without them anyway.
- The robots.txt credit line and the `credits` chat reply are intentional product content.

## trancelucent.html: regions and conventions

Splice by the `/* ---- name ---- */` banner comments, never by line number.

| region | holds |
|---|---|
| top of `<script>` | `BASE`/`API` (derived from `location.pathname`, so never hardcode a building), `HGT`, `ISO`, `LEVEL`, module state `ST BY ROUTE LASTR show HOVER FROM TO PICK cam aim` |
| `project()` `fitView()` `resetView()` | yaw then pitch projection returning `[x,y,depth]`; `fitView` frames the visible decks |
| damped camera | `tick()`: `cam` chases `aim` at `SNAP=0.18`; renders only when something moved or `dirty` |
| timetable | clock, availability tones and text, `AT AVAIL HERE PENDING` |
| paint | element pool, `tone()`, `render()` |
| view cube | `buildCells()` `flyTo()` `drawCube()` |
| readout, data, camera input, chat, phone | sidebar route list; `loadState()` `trace()`; pointer handlers and `pickNode()`; `say()` `ask()`; the phone bar and `applyMode()` |

- **Floors are 1-based decks: ground is 1.** Every human-facing label goes through
  `LEVEL_NAME(f)` (`1 -> 'GROUND'`, `7 -> 'LEVEL 6'`) or `LVL(f)` (`'G'`, `'L6'`). Never inline
  `'L'+f`. Backend pair: `gemini.level_name()` / `gemini.deck()`. The wire format stays the raw deck index.
- **Chat timestamps** come from `say()`, in India time like every clock here: `stamp()` gives
  `14:05` today, `Mon 14:05` within the week, else `6 Oct 14:05`, with the full date in the
  tooltip. A building-chat message passes CometChat's `getSentAt()` (seconds, x1000), never the
  time it was drawn, because the room's history can be days old. `wait` status lines get none.
- **`dirty=true` after any state change.** `tick()` skips `render()` when the camera rests.
- **Input writes `aim`, never `cam`** (writing `cam` stutters). Only the boot line copies `cam={...aim}`.
- Four writers of `aim.yaw`/`aim.pitch`, kept independent: the drag (the only one the invert flags
  apply to), `#rotL`/`#rotR` quarter turns, `flyTo()` (absolute, via `nearYaw()`), `resetView()`.
  The drag line must keep both sign factors: `aim.yaw+=(INVX?-1:1)*dx*0.007` and
  `aim.pitch-(INVY?-1:1)*dy*0.006`. Pitch is clamped `[-1.45, 1.52]`; `render()` reverses deck
  stacking below 0, so never unclamp it.
- The view cube is a plain cube with an invisible 3x3 hit grid per face. A region's `dir` is
  both its key and its fly-to direction, so the 26 regions and 26 views can't drift apart. Cube
  shading is opaque on purpose (alpha doubles up along shared edges).
- Clicking: `drag.moved < 5` on `pointerup` picks, not a `click` listener. `pointerdown` bails on
  `.hud` and `#tog` or their buttons go dead. `pointermove` with `buttons===0` cancels a stuck drag.
- **Reset is two-step**: a tapped space still waiting for its pair (`PICK==='to'`) is deselected
  first; pressed again, or with nothing tapped, it resets the view. The demo From/To seeded at
  boot never sets `PICK`, so a fresh page resets in one press. Escape (desktop) and the phone's
  Clear remove a drawn route.
- Fixed world-space light `LIGHT=[-0.55,-0.84]`, or the eye flips the solid inside out.
- Painting is deck-grouped (`deck N`, everything on it, `deck N+1`), reversed below the floor;
  anything on a hidden deck goes to `orphan` and paints last, which keeps a route continuous
  across a hidden floor.
- A route shows only the decks it crosses, on desktop and phone; the floor pills still override.
- `roof()` is not named `top` (that shadows `window.top`).

## Rendering performance

- `render()` never empties the `<svg>`. Every shape goes through `put(key, tag, attrs, text)`
  (stable key, reused element, only changed attributes written) and `commit(list)` reorders with
  the fewest moves. A new kind of shape needs a **unique key prefix**; an attribute no longer set
  is removed automatically.
- **Never do expensive work per face.** `project()` caches sin/cos per camera change, `pts()`
  rounds instead of `toFixed`, `istNow()` reuses its answer for a second (building an
  `Intl.DateTimeFormat` per face once made frames 18x slower), `AV_CACHE` holds one tone per part
  per frame, `tone()` runs once per slab.
- **Lite mode** (`LITE`, `body.lite`): on at boot only when the browser reports under 4 GB RAM
  **and** at most 4 cores (iPhones always report 2 cores and Safari/Firefox report no RAM, so
  both hints are required), otherwise after 20 frames slower than 24 ms. `LITEAT` records how many
  floors were shown when it switched; showing fewer retries full detail (`unLite()`, called from
  `markSeg()`, which every change to `show` goes through). Boot lite (`LITEAT=0`) stays.
- `LOW` = lite and moving (owned by `tick()`, mirrored as `#stage.low`): room tops only, batched
  per floor and colour, plate outlines, no cube redraw, half-resolution svg. `LOWDRAWN` forces one
  full render when the camera settles; the settled picture must be pixel-identical.
- Route dashes pause while moving (`#stage.moving`) and are static in lite.
- Easing stops at per-axis `EPS`, not 1e-4.
- Measure main-thread ms per frame back to back (DevTools CPU throttling is unreliable here).

## Phone and PWA

- **Nothing scrolls on a phone. Everything fits the viewport.**
- Chat is an overlay over the model, opened by the bottom button (**Chat**, then **Close chat**).
  Not tabs: they would hide the map while the answer draws the route.
- Directions page one step at a time (prev/next, rail dots); the camera centres on the step.
- The cube is display-only on a phone (a tap target fights the orbit gesture). Manual
  From/To/Block is desktop-only; origin comes from chat or a tapped space.
- A tapped room's label shows its timetable status on a second line under the name (one line runs
  off a 390px screen). Desktop keeps it on one line.
- **`MOBILE` is live, never a boot-time constant.** A Fold changes size without reloading.
  `applyMode()` is the single reactor (media query `change`, `resize`, `orientationchange`); every
  DOM move it makes is reversible (`#tog` goes into the stage on a phone and back into `#ctrl` on
  desktop). Handlers are wired once and check `MOBILE` at call time.
- Portrait phones use a `780x1400` frame (`VW`/`VH`), landscape and desktop `1400x780`.
- **iOS home-screen app:** `black-translucent` + `viewport-fit=cover` draw the page under the
  clock, where iOS blurs whatever sits there, and `100dvh` can disagree with the real screen. So on
  phones `body` is `position:fixed; inset:0` with `padding-top: var(--top)`, the inset plus 16px
  because the blur fades past it. The inset is 0 in a browser tab, so nothing changes there.
- Breakpoints: `max-width:900px` phone; `max-width:380px` Fold covers (floor strip gets a fade
  mask); `max-width:900px and max-height:560px` landscape phones (cube, Reset and hint hidden).
- Offline: `sw.js` caches the shell network-first and `/state` stale-while-revalidate
  (`trancelucent-state-v3`; bump it when node ids change). Chat, route and block are never cached
  and fail honestly. Porting Dijkstra to JS was ruled out: a second source of truth.
- `netmark(ok)` is fed by what requests actually did; `navigator.onLine` alone lies.
- Testing on a phone: `--host 0.0.0.0`, firewall allowance. Plain LAN http is not a secure context,
  so the service worker and install don't work there; use `adb reverse tcp:8000 tcp:8000`
  (Android, `localhost` counts as secure) or Chrome's insecure-origin flag.

## Timetable and availability

- `fixtures/timetable.json` is built once from the semester's 164 sheets; the app never reads a
  PDF. `sources[]` records each file's creation time and sha256; `overrides[]` lists dropped claims.
- **Free is never assumed.** A room is free only if it has its own room/lab sheet (or its base room
  does). Any other room is in use (some sheet books it) or has no timetable.
- Conflicts: the newest file wins per professor-hour. Placeholders (N1, X2, ...) occupy rooms but
  are not people.
- **The page computes "now"** from weekly busy spans shipped in `/state`, in India time (fixed
  +05:30 via `Intl`, never the device zone), so colours work offline. Chat answers are computed on
  the server, also in India time.
- `MAKEUP LEC` slots count as free, with a note. Room halves (B115A/B115B) each have a state and
  are drawn as split boxes along the long side.
- Free-room search: no origin means ask where they are; then the single nearest free room by
  walking distance, route drawn, "is it free when you get there?". "Not free" offers the next one,
  nothing remembered. Only the building you are in. "Empty lab" filters to names with Lab/Laboratory.
- Off hours (weekend, before 7:00, after 19:00): chat says no lectures are scheduled and the
  building may be closed; the map shows no colours plus a banner.
- Professor lookup: teaching slots only, gaps phrased "no lecture scheduled"; no cabins. Unknown
  name: ask for the initials printed on the student's timetable.
- **Room codes map to nodes only where evidence pins them** (a board number, the floor layout, or
  who teaches there). Unpinned codes are answered by code and floor, with no colour and no route.
  Never guess a mapping.
- Palette (state is carried by the outline): free `#5ef2a8`, class within 15 min `#ffb42f`, in use
  `#9d6bdb`, no timetable grey with a dashed roof. Not red: red means blocked. `tone()` priority:
  blocked, current step, route, hover/from/to, then availability.
- `AT` (null = live; set by a chat reply's `at` for "free at 3pm Thursday"), `AVAIL` (legend
  toggle, `localStorage` `twin.avail`; phones flip it through chat), `HERE` (last tapped space,
  sent as `here` with chat), `PENDING` (a question waiting for "where are you"; a tap re-asks it).
  `markWhen()` owns the `#when` banner; a 60 s interval repaints so "now" moves.

## Chat assistant behaviour

- `gemini.chat` only parses the sentence into one action; every route, distance and blockage is
  computed in `main.py` against networkx, every free room and professor in `timetable.py`.
- The model's own prose is trusted only for `not_found`. A destination nobody can place gets one
  reply: "I can't find that in <building>. It may not be in this building. Shall I guide you to
  the <entrance>?" `offer_gate()` is its single writer; a "yes" comes back as an ordinary route
  request, so there is no pending state. Switching the visitor to the other building is not wanted.
- `need_origin`: asking for the entrance with no origin asks where they are instead of answering
  "0 m, 1 steps".
- The main entrance is the entrance named "Main" (Aryabhatta's first entrance node is West Exit).
- Blockages are per visitor (`X-Visitor-Id`, an anonymous id in `localStorage`): one visitor's
  "the corridor is blocked" is not everyone's reality.
- **A building = Aryabhatta, B building = Bhaskaracharya.** Neither letter is in the code or the
  fixtures, so the model has no mapping for "B building". Students also say "L1" for floor 2.

## Building data facts

- Bhaskaracharya corridors are split at x=600: `corr_n_fX`/`corr_s_fX` are the west halves,
  `corr_n_east_fX`/`corr_s_east_fX` the east halves, linked at 12 m. East-end rooms (x01-x03,
  x15-x17) reach other floors through the east corridor and Staircase-2; the main entrance joins
  the east half.
- Bhaskaracharya washrooms stack identically on every floor (`[230,700,65,65]` ladies,
  `[345,700,65,65]` gents). Those rects are estimates, not measurements.
- Aryabhatta's geometry was extracted from photos of its escape-route boards by Gemini Robotics
  ER 2, swept as a 3x3 grid of overlapping tiles (a whole board returned too few labels); dedupe,
  corridors, adjacency and distances are deterministic.
- Known data problems, not code bugs: `lecture_hall_301..305_f4` carry floor 4 but say "third
  floor" and their signatures are identical.

## Deployment

fly.io app `spatial-twin`, region `bom`, exactly one always-on machine: blockages live in memory,
so scaling to zero or across machines would lose them. `force_https` (the service worker needs a
secure context). `/robots.txt` and `/sitemap.xml` build absolute URLs from the proxy headers.
`/analytics.js` loads Vercel analytics and Microsoft Clarity from env vars, never on localhost.
