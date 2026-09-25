"""Trancelucent - FastAPI wiring. No logic here beyond calling world and gemini."""
import json
import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import gemini
import timetable
import world


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# no-store so an edited page never comes back from the browser cache mid-demo
NO_CACHE = {"Cache-Control": "no-store, must-revalidate"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse("index.html", headers=NO_CACHE)


@app.get("/analytics.js")
def analytics():
    clarity_id = (
        os.getenv("MICROSOFT_CLARITY_ID")
        or os.getenv("CLARITY_PROJECT_ID")
        or ""
    ).strip()
    vercel_src = os.getenv("VERCEL_ANALYTICS_SCRIPT_SRC", "/_vercel/insights/script.js").strip()
    js = f"""(() => {{
  const host = location.hostname;
  const local = host === "localhost" || host === "127.0.0.1" || host === "";
  if (local) return;

  const vercelSrc = {json.dumps(vercel_src)};
  if (vercelSrc) {{
    window.va = window.va || function () {{
      (window.vaq = window.vaq || []).push(arguments);
    }};
    const s = document.createElement("script");
    s.defer = true;
    s.src = vercelSrc;
    document.head.appendChild(s);
  }}

  const clarityId = {json.dumps(clarity_id)};
  if (clarityId) {{
    (function(c, l, a, r, i, t, y) {{
      c[a] = c[a] || function() {{ (c[a].q = c[a].q || []).push(arguments); }};
      t = l.createElement(r);
      t.async = 1;
      t.src = "https://www.clarity.ms/tag/" + i;
      y = l.getElementsByTagName(r)[0];
      y.parentNode.insertBefore(t, y);
    }})(window, document, "clarity", "script", clarityId);
  }}
}})();
"""
    return Response(js, media_type="text/javascript", headers=NO_CACHE)


# PWA assets. sw.js must be served from the root or its scope cannot cover /aryabhatta
# and /bhaskaracharya. Icons are cached hard; the worker itself never is, so a new one
# is picked up on the next navigation.
@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse("manifest.webmanifest", media_type="application/manifest+json")


# scheme+host from the proxy headers fly sets, so robots/sitemap emit absolute URLs
# for the live domain without hardcoding it - works on *.fly.dev and any custom domain
def site_base(request: Request):
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{proto}://{request.headers['host']}"


@app.get("/robots.txt")
def robots(request: Request):
    body = ("User-agent: *\nAllow: /\n\n"
            f"Sitemap: {site_base(request)}/sitemap.xml\n\n"
            "# made with love by MnM, Khush Madhwani and Bhoumik Sangle\n")
    return Response(body, media_type="text/plain")


@app.get("/sitemap.xml")
def sitemap(request: Request):
    base = site_base(request)
    paths = ["/"] + [b["prefix"] for b in BUILDINGS]
    urls = "".join(f"<url><loc>{base}{p}</loc><changefreq>weekly</changefreq></url>" for p in paths)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
           f"{urls}</urlset>")
    return Response(xml, media_type="application/xml")


@app.get("/sw.js")
def service_worker():
    return FileResponse("sw.js", media_type="text/javascript", headers=NO_CACHE)


@app.get("/icon-{size}.png")
def icon(size: int):
    if size not in (192, 512):
        raise HTTPException(404)
    return FileResponse(f"icon-{size}.png", media_type="image/png")


class ChatIn(BaseModel):
    message: str
    history: str = ""
    here: str = ""      # the space the visitor last tapped on the model, if any


BUILDINGS = []   # every mounted building, so the page can offer a switcher without guessing

# The semester timetable, loaded once like the building files. Both buildings share it.
LAB = re.compile(r"\blab(s|oratory|oratories)?\b", re.I)   # ponytail: keyword only, add a model field if "computer room" etc. must count
TT = timetable.load("fixtures/timetable.json") if os.path.exists("fixtures/timetable.json") else None
# ponytail: a fixed +05:30 - India has no DST, and zoneinfo would need the tzdata package on Windows
IST = timezone(timedelta(hours=5, minutes=30))
LETTER = {"aryabhatta": "A", "bhaskaracharya": "B"}
TITLE = {"aryabhatta": "Aryabhatta", "bhaskaracharya": "Bhaskaracharya"}


def when(day, time):
    """(day, hour, minute, live) in India time. The model only ever names a day and a time;
    gemini.chat has already validated both."""
    now = datetime.now(IST)
    d = now.weekday()
    if day in timetable.DAYS:
        d = timetable.DAYS.index(day)
    elif day == "tomorrow":
        d = (d + 1) % 7
    h, m = (int(x) for x in time.split(":")) if time else (now.hour, now.minute)
    return timetable.DAYS[d], h, m, not time and day in ("", "today")


def plain(text):
    """Chat replies carry no dashes as punctuation (they read as machine-written): an em/en
    dash, a double dash or the building files' broken dash character becomes a comma, and a
    spaced hyphen ("STAIRCASE - 1") a space. Hyphens inside codes and names (H-DA, Lab-4) stay."""
    text = re.sub(r"(\d)\s*(?:—|–|--)\s*(\d)", r"\1 to \2", text)     # 12:00–13:00 -> 12:00 to 13:00
    text = re.sub(r"\s*(?:—|–|--|�)\s*", ", ", text)
    return re.sub(r"\s+-(?:\s+|$)", " ", text).strip().rstrip(",")


def lecture_hours(day, hour):
    return day in timetable.DAYS[:5] and timetable.FIRST <= hour < timetable.LAST


def mount_building(prefix, w):
    """Serve one building's Trancelucent view under `prefix`. Called once per
    building — the page derives its own API base from the URL it was served at."""
    BUILDINGS.append({"prefix": prefix, "name": w.building})
    building = prefix.strip("/")     # the timetable's name for this building
    # Aryabhatta has four entrance-type nodes and West Exit comes first in the file; the gate
    # offer and the default origin should be the main entrance wherever one is named so
    entrances = [i for i, n in w.nodes.items() if n["type"] == "entrance"]
    entrance = next((i for i in entrances if "main" in w.nodes[i]["name"].lower()),
                    entrances[0] if entrances else next(iter(w.nodes)))

    def node_of(id):
        """A node id stays put; an equipment id resolves to the node it sits at."""
        if id in w.nodes:
            return id
        eq = w.equipment.get(id)
        return eq["node"] if eq else None

    def offer_gate(said=""):
        """The single reply for "that place is not in this world". The visitor may simply be
        standing in the wrong building, and the entrance is the only useful thing left to
        offer. A "yes" comes back as an ordinary route request to the entrance — the offer
        sentence is in the history and names it — so this needs no pending state anywhere."""
        said = (said or f"I can't find that in {w.building}.").strip()
        if said[-1] not in ".!?":
            said += "."
        return said + f" It may not be in this building. Shall I guide you to the {w.nodes[entrance]['name']}?"

    def place(code):
        """How a timetable room is named to someone standing in THIS building: its name on the
        model, or its code plus where it is when the model cannot show it. Returns (label, how)."""
        r = TT.rooms[(TT.part_of.get(code) or [code])[0]]
        if r["building"] != building:
            return f"{code}, {TITLE[r['building']]} building", "elsewhere"
        if r["node"]:
            return f"{w.nodes[r['node']]['name']} ({code})", "here"
        return f"{code} ({gemini.level_name(r['floor'])}, {TITLE[building]})", "unplaced"

    def offer(label, how, code, there=True):
        if how == "here":
            return " Shall I take you there?" if there else f" Shall I take you to {label}?"
        if how == "elsewhere":
            other = TT.rooms[TT.part_of[code][0]]["building"]
            return (f" Shall I guide you to the {w.nodes[entrance]['name']} so you can get to the "
                    f"{LETTER[other]} building?")
        return f" I can't place {code} on the model yet." if there else ""

    def free_room(c, origin, visitor, lab=False):
        """The single nearest free room by walking distance; networkx does the distances.
        lab=True keeps only rooms whose name on the model says Lab or Laboratory."""
        day, h, m, live = when(c.day, c.time)
        out = {"at": None if live else {"day": day, "hour": h}}
        if not origin:
            out["action"] = "need_origin"
            out["reply"] = "Where are you now? Name the space, or tap it on the model, and I'll find the nearest empty room."
            return out
        closed = not lecture_hours(day, h)
        lead = ("No lectures are scheduled then, so by the timetable every room is free, "
                "but the building may be closed. ") if closed else ""
        at = "" if live else f" at {day} {h:02d}:{m:02d}"
        ranked, unplaced = [], []
        for part in TT.free(building, day, h, c.skip_rooms):
            node = TT.rooms[part]["node"]
            if not node:
                if not lab:   # an unplaced room has no name, so we can't tell if it is a lab
                    unplaced.append(part)
                continue
            if lab and not LAB.search(w.nodes[node]["name"]):
                continue
            r = w.route(origin, node, visitor=visitor)
            if r["path"]:
                ranked.append((r["distance_m"], part, node, r))
        if not ranked and lab:
            out["reply"] = lead + f"By the timetable no lab in {TITLE[building]} is free{at}."
            return out
        if not ranked:
            out["reply"] = lead + (
                "Nothing I can show on the model is free" + at + ", but by the timetable "
                + ", ".join(place(p)[0] for p in unplaced[:3]) + " " + ("is" if len(unplaced) == 1 else "are") + " free."
                if unplaced else f"By the timetable no room in {TITLE[building]} is free{at}.")
            return out
        dist, part, node, r = min(ranked, key=lambda x: x[0])
        _, makeup, until = TT.status(part, day, h)
        out["route"], out["req"] = r, {"from": origin, "to": node, "accessible": False}
        label = f"{w.nodes[node]['name']} ({part})"
        reply = lead + f"{label} is free{at}" + ("" if closed else f" until {until}:00") + ", per the timetable"
        reply += ", and you're already there." if dist == 0 else f", {dist} m away. Drawn on the model."
        halves = [p for p, x in TT.rooms.items() if x["node"] == node and p != part and TT.status(p, day, h)[0] == "in_use"]
        if halves:
            reply += f" {', '.join(halves)} {'is' if len(halves) == 1 else 'are'} in use."
        if makeup:
            reply += f" A makeup lecture may be held there from {makeup[0]['from']}:00 to {makeup[0]['to']}:00."
        out["reply"] = reply + (" Is it actually free?" if dist == 0 else " Is it free when you get there?") \
            + " Tell me if not and I'll find the next."
        return out

    def find_prof(c):
        day, h, m, live = when(c.day, c.time)
        hits = TT.find_prof(c.prof_query)
        who = lambda p: f"{TT.profs[p]['name']} ({p})" if TT.profs[p]["name"] else p
        if not hits:
            return {"reply": (f"I don't recognise '{c.prof_query}'. " if c.prof_query.strip() else "Which professor? ")
                    + "What are their initials on your timetable (e.g. PSG)?"}
        if len(hits) > 1:
            return {"reply": "Did you mean " + " or ".join(who(p) for p in hits[:4]) + "?"}
        p = hits[0]
        now, last, nxt = TT.where(p, day, h)
        if now:
            s = now[0]
            label, how = place(s["room"])
            return {"reply": f"{who(p)} has {s['what']} in {label}{',' if how == 'elsewhere' else ''} "
                             f"until {s['to']}:00, per the timetable."
                             + offer(label, how, s["room"])}
        if day in ("Sat", "Sun"):
            reply = f"No lectures are scheduled on {'Saturdays' if day == 'Sat' else 'Sundays'}."
        elif not lecture_hours(day, h):
            reply = "No lectures are scheduled then."
        else:
            reply = f"No lecture scheduled for {who(p)} " + ("right now." if live else f"at {day} {h:02d}:{m:02d}.")
        if not nxt:
            return {"reply": reply + f" I have no lectures for {who(p)} in the timetable."}
        label, how = place(nxt["room"])
        next_at = f"{'' if nxt['day'] == day else nxt['day'] + ' '}{nxt['from']}:00 in {label}"
        if not lecture_hours(day, h):
            reply += f" {who(p)}'s next lecture: {next_at}."
        elif last:
            reply += f" Last: {last['from']}:00 to {last['to']}:00 in {place(last['room'])[0]}. Next: {next_at}."
        else:
            reply += f" Next: {next_at}."
        return {"reply": reply + offer(label, how, nxt["room"], there=False)}

    @app.get(prefix)
    def page():
        return FileResponse("trancelucent.html", headers=NO_CACHE)

    # X-Visitor-Id is an anonymous id the page generates once and keeps in
    # localStorage - never an account. It scopes reported blockages so one
    # visitor's "the corridor is blocked" is not every other visitor's reality.
    # A caller with no header (a bare curl, an old cached page) shares one
    # fallback bucket; the browser client always sends the header.
    def visitor_of(x_visitor_id):
        return x_visitor_id or "anon"

    @app.get(prefix + "/state")
    def page_state(x_visitor_id: str | None = Header(None)):
        state = w.state(visitor=visitor_of(x_visitor_id))
        if TT:   # each room's weekly busy spans; the page picks the hour itself (plan D4)
            state["timetable"] = TT.weekly(building)
        return state

    @app.get(prefix + "/route")
    def page_route(from_id: str = Query(..., alias="from"), to: str = Query(...),
                    accessible: bool = False, x_visitor_id: str | None = Header(None)):
        return w.route(from_id, to, accessible=accessible, visitor=visitor_of(x_visitor_id))

    @app.post(prefix + "/block")
    def page_block(node: str, passable: bool = False, x_visitor_id: str | None = Header(None)):
        if not w.has(node):
            return {"error": f"unknown node id '{node}'"}
        w.block(visitor_of(x_visitor_id), node, passable)
        return {"node": node, "passable": passable}

    @app.post(prefix + "/chat")
    def page_chat(body: ChatIn, x_visitor_id: str | None = Header(None)):
        out = answer(body, visitor_of(x_visitor_id))
        out["reply"] = plain(out["reply"])   # the one exit every reply passes through
        return out

    # gemini.chat only parses the sentence; every route, distance and blockage
    # below is computed here against networkx, never by the model.
    def answer(body, visitor):
        c = gemini.chat(body.message, body.history, w, TT.part_of if TT else ())
        # a space the visitor tapped counts as "where I am" when the sentence does not say
        here = body.here if body.here in w.nodes else None
        # the model's own prose is trusted only for "not_found", where it names the place it
        # could not find. Every other reply is written below from the world model, and "none"
        # falls through to the canned line - otherwise the model happily answers "what is c++".
        out = {"action": c.action, "reply": c.reply if c.action == "not_found" else "",
               "route": None, "level": None, "changed": []}

        if c.action in ("free_room", "find_prof") and not TT:
            out["reply"] = "The timetable is not loaded on this server."

        elif c.action == "free_room":
            # "empty lab" is read from the visitor's own words, not the model. A follow-up
            # ("B115A isn't free") carries skip_rooms, so it keeps the lab ask from the recent turns.
            said = [body.message] + ([l for l in body.history.splitlines() if l.startswith("visitor: ")]
                                     if c.skip_rooms else [])
            lab = any(LAB.search(s) for s in said)
            out.update(free_room(c, node_of(c.from_id) or here, visitor, lab))

        elif c.action == "find_prof":
            out.update(find_prof(c))

        elif c.action == "availability":
            out["availability"] = c.on
            out["reply"] = "Showing which rooms are free and in use." if c.on else "Hiding room availability."

        elif c.action == "route":
            a, b = node_of(c.from_id) or here or entrance, node_of(c.to_id)
            if not b:
                out["action"] = "not_found"
                out["reply"] = offer_gate()
                return out
            if a == b and not node_of(c.from_id) and not here:
                # they gave no origin, so `a` fell back to the entrance - and the entrance is
                # also what they asked for. Routing that answers "0 m, 1 steps", which is the
                # one useless reply. Ask where they actually are instead.
                out["action"] = "need_origin"
                out["reply"] = (f"Where are you now? Name the space, or tap it on the model, "
                                f"and I'll route you to the {w.nodes[b]['name']}.")
                return out
            r = w.route(a, b, accessible=c.accessible, visitor=visitor)
            out["route"] = r
            out["req"] = {"from": a, "to": b, "accessible": c.accessible}   # so the page can replay it after a blockage
            out["reply"] = r["reason"] if not r["path"] else (
                f"{w.nodes[a]['name']} to {w.nodes[b]['name']}"
                + (", step free" if c.accessible else "")
                + f": {r['distance_m']} m, {len(r['steps'])} steps. Drawn on the model."
            )

        elif c.action in ("block", "unblock"):
            passable = c.action == "unblock"
            target = node_of(c.node_id)
            if target:
                targets = [target]
            elif passable:
                targets = list(w.visitor_blocked(visitor))   # "clear everything" - MY reports only
            else:
                targets = []
            for t in targets:
                w.block(visitor, t, passable)
            out["changed"] = targets
            names = ", ".join(w.nodes[t]["name"] for t in targets)
            out["reply"] = (f"{names} is now {'open' if passable else 'blocked'}." if targets
                            else "Nothing to change. Which place did you mean?")

        elif c.action == "show_level":
            # the wire still carries deck indices - the page indexes decks by them -
            # but every word the visitor reads is phrased by gemini.level_name
            decks = sorted({n.get("floor", 1) for n in w.nodes.values()})
            d = gemini.deck(c.level)
            if c.level == "all":
                out["level"], out["reply"] = "all", "Showing every level."
            elif d in decks:
                out["level"] = str(d)
                out["reply"] = f"Showing {'the ground floor' if d == 1 else gemini.level_name(d)}."
            else:
                out["reply"] = ("I only know about "
                                + ", ".join(gemini.level_name(f) for f in decks) + ".")

        elif c.action == "credits":
            out["reply"] = ("Trancelucent was made with love by team MnM: "
                            "Khush Madhwani and Bhoumik Sangle.")

        elif c.action == "reset_view":
            out["reply"] = "View reset."

        elif c.action == "not_found":
            # the model parsed a destination request but nothing in this world is that place
            out["reply"] = offer_gate(c.reply)

        if not out["reply"]:
            out["reply"] = ("Ask me to take you somewhere, find an empty room, find a professor, "
                            "block a space, or switch level.")
        return out


@app.get("/buildings")
def buildings():
    return BUILDINGS



# the Bhaskaracharya block, modelled from its seven Emergency Escape Route boards
if os.path.exists("fixtures/building.bhaskaracharya.json"):
    bhaskar = world.load("fixtures/building.bhaskaracharya.json")
    mount_building("/bhaskaracharya", bhaskar)
    print(f"loaded bhaskaracharya: {len(bhaskar.nodes)} nodes, {len(bhaskar.equipment)} equipment")

# the Aryabhatta block opposite it, modelled from its five Emergency Escape Route boards
if os.path.exists("fixtures/building.aryabhatta.json"):
    aryabhatta = world.load("fixtures/building.aryabhatta.json")
    mount_building("/aryabhatta", aryabhatta)
    print(f"loaded aryabhatta: {len(aryabhatta.nodes)} nodes, {len(aryabhatta.equipment)} equipment")
