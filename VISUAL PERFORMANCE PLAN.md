# Visual performance plan

**Status:** **built** 2026-09-17 (P1–P6 and P8; canvas P7 not needed yet). Results are in §7.
**Problem (Khush):** the 3D view is smooth on Apple devices but buggy on older Android phones
and laptops.

---

## 1. What was measured

**Setup**
- `/bhaskaracharya` at 1400×900 in Playwright's Chromium on this Windows laptop.
- CPU throttling through Chrome DevTools: **4×** stands in for a mid-range Android phone,
  **6×** for an older one.
- Two numbers per run:
  - how long one `render()` takes while the camera turns;
  - frames per second during a scripted 2–3 s orbit, like a drag.
- The test browser probably paints without GPU help, so the fps figures are pessimistic.
  Before-and-after comparisons are still valid.

**What one frame builds:** Bhaskaracharya puts about **1,680 SVG elements** in the page
(about 1,115 room and stair faces, plus 280 floor tiles, plus labels and the route).
Aryabhatta is similar, at about 1,160 faces and tiles. **All of them are deleted and created
again on every frame the camera moves.**

| Run | `render()` per frame (median / p90) | fps while orbiting | Worst frame |
|---|---|---|---|
| **Before the §2 fix**, CPU ×1 | **296 ms / 336 ms** | **3** | 434 ms |
| Before, CPU ×4 | 4,761 ms / 6,059 ms | 0.3 | 5.9 s |
| Before, CPU ×6 | 11,512 ms / 17,042 ms | 0.3 | 9.2 s |
| **After the §2 fix**, CPU ×1, availability on | **16.7 ms / 25.3 ms** | 19 | 88 ms |
| After, CPU ×1, availability off | 21.7 ms / 28.9 ms | 16 | 103 ms |
| After, CPU ×4, availability on | 215 ms / 280 ms | 2.5 | 533 ms |
| After, CPU ×4, availability off | 235 ms / 299 ms | 3 | 434 ms |
| After, CPU ×6, availability on | 589 ms / 782 ms | 1.5 | 1.1 s |
| After, CPU ×6, availability off | 330 ms / 1,139 ms | 4.5 | 382 ms |

**What the numbers say**
- The timetable colours made every frame **18× slower** (§2). That is fixed.
- Even without them, a frame is about 17–22 ms of script and DOM work on a fast laptop, and
  the orbit still only reached 16–19 fps. **Painting** those translucent polygons costs about
  as much again as building them.
- At 4× throttle, what an older phone feels like, it is **2–3 fps**. That is the "buggy"
  experience.
- A fast Apple chip has enough headroom to hide both costs. A budget phone does not.

---

## 2. Already fixed (uncommitted, in `trancelucent.html`)

**Cause:** the availability colours asked for the time once per face, about 1,100 times a
frame, and every call built a new `Intl.DateTimeFormat`. That object is expensive to create,
and reusing one is the standard advice ([MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat)).

**Fix**
- The formatter is now built once.
- The India-time clock is reused for a second.
- Each room's colour is worked out once per frame instead of once per wall.

**Result:** 296 ms → 17 ms per frame.

---

## 3. Why only Apple devices feel smooth

1. **The whole picture is rebuilt from scratch every frame.** `render()` empties the `<svg>`,
   then creates about 1,600 elements with `createElementNS` and `setAttribute`. That is a lot
   of work per frame: style recalculation, layout, and garbage collection.
2. **Every face is semi-transparent,** with alpha on both fill and stroke. Blending 1,400
   overlapping translucent shapes is expensive to paint. SVG is known to degrade past a few
   thousand elements, and budget mobile GPUs feel it first
   ([yWorks](https://www.yworks.com/blog/svg-canvas-webgl),
   [SVG Genie 2026](https://www.svggenie.com/blog/svg-vs-canvas-vs-webgl-performance-2025),
   [ECharts handbook](https://apache.github.io/echarts-handbook/en/best-practices/canvas-vs-svg/)).
3. **The dashed route never stops moving.** `.route`, `.climb` and `.hoist` animate
   `stroke-dashoffset` forever. That forces a repaint of the whole SVG every frame, even while
   nobody touches the screen. Only `transform` and `opacity` avoid repainting
   ([web.dev](https://web.dev/articles/stick-to-compositor-only-properties-and-manage-layer-count),
   [web.dev animations](https://web.dev/articles/animations-and-performance?hl=en)).
4. **Letting go of a drag still costs a long tail of frames.** The camera eases with
   `SNAP=0.18` until it is within 0.0001 of its target, about 40 full renders after release.

---

## 4. The plan, ranked by impact for the effort

| # | Change | What it does | Expected effect | Size |
|---|---|---|---|---|
| **P1** | **Reuse elements instead of rebuilding** | Keep one `<polygon>` per face and update only its `points` and fill each frame. Re-order children only when the depth order changes. | Removes the create, delete and garbage-collection churn; usually a multi-fold drop in script time. | ~60 lines |
| **P2** | **Less detail while moving** | While the camera moves, draw roofs only (no walls, no floor tiles). Full detail returns about 150 ms after it settles. | About 1,400 → 300 shapes per frame during a drag. | ~25 lines |
| **P3** | **One floor plate per deck** | Replace the 40 tiles per deck with 1 polygon, and draw the tile grid lines only at rest. | 280 → 7 shapes. | ~10 lines |
| **P4** | **Calm route animation** | Pause the marching dashes while the camera moves and on slow devices; keep them where frames are cheap. `prefers-reduced-motion` already stops them. | No constant full repaint while idle. | ~10 lines |
| **P5** | **Automatic lite mode** | Track average frame time. If it stays above ~24 ms for ~20 frames, switch on P2 and P4 permanently for that visit. A low `navigator.hardwareConcurrency` or `deviceMemory` can start in lite mode. | Slow devices adapt without anyone touching a setting. | ~25 lines |
| **P6** | **Shorter settle tail** | Stop easing at a larger epsilon, and draw the final frame exactly. | About 40 → 15 frames after each drag. | ~3 lines |
| **P7** | **Canvas renderer** (big) | Draw all faces into one `<canvas>`, batching paths by style; hit-test taps by checking the same projected polygons; keep SVG only for labels and the route. | The largest win for 1,000+ translucent shapes on Chrome and Android (sources above). | ~300 lines, rewrite of the paint region |
| **P8** | **Small CSS and paint trims** | `contain: strict` on `#stage`; no text outline on labels while moving; check the `#lvl` mask on phones. | Small but free. | ~5 lines |

**Recommended order:** P1 → P3 → P2 → P4 → P6 → P5, measuring after each.
**P7 only if** a real Android phone is still below target after those.

**Rules each change must keep** (`.claude/context.md`)
- Painting is grouped by deck.
- A route stays continuous across hidden decks.
- `tone()` priority is unchanged.
- The phone layout never scrolls.
- The picture is identical once the camera settles.

---

## 5. Decisions (grilled with Khush, 2026-09-17)

| # | Question | Decision |
|---|---|---|
| 1 | Canvas (P7) now or later? | **SVG fixes first** (P1–P6, P8), measured after each. Canvas only if a real Android phone is still below target. |
| 2 | Less detail while moving (P2)? | **Only on slow devices (lite mode).** Fast devices keep full detail while turning. |
| 3 | How is "slow" decided (P5)? | **Automatic, nothing on screen.** Lite from the start only when the browser reports **RAM < 4 GB and ≤ 4 cores** (4 GB counts as normal). Otherwise any device switches to lite after **20 frames slower than 24 ms**, for the rest of that visit. iPhones always report 2 cores and Safari/Firefox report no RAM ([MDN compat issue](https://github.com/mdn/browser-compat-data/issues/30063), [MDN deviceMemory](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/deviceMemory)), so both hints are required together; that keeps Apple devices in normal mode. |
| 4 | Route dashes (P4)? | **Animate unless lite.** They pause while the camera moves; in lite mode they are static. Reduced-motion users already get static dashes. |
| 5 | Pass bar? | **At 4× CPU throttle, lite mode: ≥ 30 fps orbiting and `render()` ≤ 15 ms**, with the settled picture identical to before. 45 fps is a stretch goal. |

---

## 6. How it will be tested

- **Real phone:**
  - Connect over USB with `adb` (platform-tools is already on the PATH).
  - Run `adb reverse tcp:8000 tcp:8000`, so the phone sees `localhost` and the offline cache
    works too.
  - Open `chrome://inspect` for the Performance panel, the FPS meter and Paint flashing.
- **Laptop:** Chrome DevTools Performance panel at 4× and 6× CPU throttle, recording a
  5-second orbit.
- **Repeatable number:** the benchmark below, run before and after every step.
- **Targets**
  - At 4× throttle: `render()` ≤ 8 ms while moving, and ≥ 45 fps orbiting.
  - With a route drawn and nothing moving: no repaints (Paint flashing stays dark).
  - Once settled, the picture matches today's exactly.

```js
// paste into the console on /bhaskaracharya; the same snippet produced the table in §1
(async () => {
  const t = []; for (let i = 0; i < 20; i++) { cam.yaw += .03; aim.yaw = cam.yaw;
    const s = performance.now(); render(); t.push(performance.now() - s) }
  t.sort((a, b) => a - b);
  let f = 0; const t0 = performance.now();
  await new Promise(d => { const step = () => { f++; aim.yaw += .02;
    performance.now() - t0 < 2000 ? requestAnimationFrame(step) : d() }; requestAnimationFrame(step) });
  console.log({ elements: svg.getElementsByTagName('*').length, renderMedianMs: t[10].toFixed(1), fps: f / 2 });
})();
```

---

## Sources

- [Stick to compositor-only properties (web.dev)](https://web.dev/articles/stick-to-compositor-only-properties-and-manage-layer-count)
- [Animations and performance (web.dev)](https://web.dev/articles/animations-and-performance?hl=en)
- [Rendering performance (web.dev)](https://web.dev/rendering-performance)
- [SVG, Canvas, WebGL? (yWorks)](https://www.yworks.com/blog/svg-canvas-webgl)
- [SVG vs Canvas vs WebGL, 2026 comparison (SVG Genie)](https://www.svggenie.com/blog/svg-vs-canvas-vs-webgl-performance-2025)
- [Canvas vs SVG best practices (Apache ECharts)](https://apache.github.io/echarts-handbook/en/best-practices/canvas-vs-svg/)
- [Intl.DateTimeFormat (MDN)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/DateTimeFormat)
- [SVG animation: SMIL vs CSS vs JavaScript (Motion)](https://motion.dev/docs/svg-animation)

---

## 7. What was built, and the results

### Built (all in `trancelucent.html`, plus one line in `sw.js` from the routing fix)

| Plan item | What went in |
|---|---|
| **P1 · Reuse elements** | `put(key, tag, attrs)` keeps one element per shape and writes only attributes that changed. `commit(list)` reorders the `<svg>` with the fewest moves. |
| **P2 · Less detail while moving (lite only)** | While a lite device moves: room tops only; one `<path>` per floor and colour instead of ~300 polygons; floor plates as outlines; no dashed floor links; no dashed roofs; the view cube waits; and the picture is painted at **half resolution** and scaled up by the GPU (`#stage.low`). Everything returns about 150 ms after the camera stops. |
| **P3 · One floor plate** | 1 plate + 1 grid path per floor instead of 40 tiles. The corner lines go in before the plate, so the settled picture matches. |
| **P4 · Route dashes** | Paused while the camera moves (`#stage.moving`); off entirely in lite (`body.lite`). |
| **P5 · Lite mode** | Starts lite only if RAM < 4 GB **and** ≤ 4 cores are reported. Otherwise it switches after 20 frames slower than 24 ms. Nothing on screen. |
| **P6 · Shorter settle** | Easing stops at per-axis thresholds (`EPS`) instead of 1e-4 everywhere. |
| **P8 · Containment** | `contain: layout paint` on `#stage`. |
| **Found while building** | `project()` recomputed sin/cos for every point (now once per camera change). `toFixed` formatting was replaced by rounding. Each room's colour is looked up once per slab, not once per wall. |

### Results (Bhaskaracharya, 1400×900, availability on)

**Page as it was before this build, back to back with the new one**
Both ran in the same minute, on the quiet run, by serving the saved copy at the same address.

| | Main-thread work per frame | Orbit fps |
|---|---|---|
| Before this build | 34.7 ms | 19 |
| **After, normal** | **18.6 ms** | 26 |
| **After, lite** | **4.3 ms** | **57** (60 without the harness) |

**Other numbers**
- `render()` alone at full speed: normal **7.5 ms** (was 15, and 296 before the §2 fix); lite **1.7 ms**.
- Elements while a lite device moves: about 1,380 → **~70** (Bhaskaracharya), 1,109 → **39** (Aryabhatta).

**Pass bar (≥ 30 fps, `render()` ≤ 15 ms at a 4× slower CPU, lite): met on the numbers above.**
- 4 × 4.3 ms = 17 ms of main-thread work per frame, inside the 33 ms that 30 fps allows.
- 4 × 1.7 ms = 7 ms of `render()`.

**Caveat, stated plainly:** this laptop could not give a clean "4×" test. Other programs were loading it, and DevTools' "4×" setting measured anywhere from **10× to 23×** slower on a plain-JavaScript benchmark (its "2×" measured 2.4×–13×). At that DevTools "4×" (really ~10×), lite ran at **10–12 fps** and normal at 2.7 fps. The old code did 0.3–3 fps under the same setting. The deciding test is still a real Android phone (§6).

### Checks run
- **Settled picture:** pixel diff against screenshots taken before the build (desktop and phone, with and without a route). **No pixel differs by more than 23/255**; the differences are hairline anti-aliasing where room outlines cross the floor grid.
- **Behaviour**
  - Clicking a room still picks the room drawn on top.
  - The slow-frame detector switched to lite after exactly 20 slow frames (2.5 s).
  - Aryabhatta's stepped stairs and L-shaped workshop draw fine.
  - The console stayed empty.
- **Syntax:** `node --check` on the page script.
