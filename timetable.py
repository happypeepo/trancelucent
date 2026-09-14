"""The semester timetable: who is in which room, hour by hour. No network, no model.

Loads fixtures/timetable.json (built once by timetables/_work/build.py) and holds the 60
hour-wise states - (day, hour) -> which rooms are booked and where each professor is.
Room "parts" are what the model draws: a whole room, or one half of a split lab (B115A).
"""
import json
import re
from difflib import get_close_matches

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
FIRST, LAST = 7, 19          # the sheets run 7:00-19:00, Monday to Friday
NOT_A_NAME = {"dr", "prof", "professor", "sir", "maam", "ma", "am", "madam", "mam", "mr", "mrs", "ms",
              "miss", "teacher", "where", "is", "the", "find"}


class Timetable:
    def __init__(self, data):
        self.rooms, self.profs, self.sessions = data["rooms"], data["profs"], data["sessions"]
        self.as_of = data["as_of"]
        self.part_of = {}    # any printed code -> the parts it books (A314 books all three thirds)
        for part, r in self.rooms.items():
            for code in r["codes"]:
                self.part_of.setdefault(code, []).append(part)
        # the 60 hour-wise states, Mon-Fri x 7:00-18:00, empty ones included:
        # (day, hour) -> {"rooms": {part: [session]}, "profs": {code: [session]}}
        self.states = {(d, h): {"rooms": {}, "profs": {}} for d in DAYS[:5] for h in range(FIRST, LAST)}
        for s in self.sessions:
            for h in range(s["from"], s["to"]):
                st = self.states[(s["day"], h)]
                for part in self.part_of.get(s["room"], []):
                    st["rooms"].setdefault(part, []).append(s)
                for p in s["profs"]:
                    st["profs"].setdefault(p, []).append(s)

    def booked(self, part, day, hour):
        """Sessions that make `part` in use. A makeup slot does not (plan D9)."""
        st = self.states.get((day, hour), {"rooms": {}})
        return [s for s in st["rooms"].get(part, []) if not s["makeup"]]

    def status(self, part, day, hour):
        """("in_use", sessions, until) | ("free", makeup_sessions, until) | ("no_data", [], None).
        Free only for a room with its own sheet - anything else we simply cannot see (plan D1)."""
        now = self.booked(part, day, hour)
        if now:
            end = hour + 1
            while end < LAST and self.booked(part, day, end):
                end += 1
            return "in_use", now, end
        if not self.rooms[part]["own_sheet"]:
            return "no_data", [], None
        end = max(hour + 1, FIRST)
        while end < LAST and not self.booked(part, day, end):
            end += 1
        makeup = [s for s in self.states.get((day, hour), {"rooms": {}})["rooms"].get(part, []) if s["makeup"]]
        return "free", makeup, end

    def free(self, building, day, hour, skip=()):
        """Parts in `building` that are free at day/hour. `skip` takes printed codes (B115A, A314)."""
        skipped = {p for code in skip for p in self.part_of.get(code, [code])}
        return [p for p, r in self.rooms.items()
                if r["building"] == building and p not in skipped and self.status(p, day, hour)[0] == "free"]

    def where(self, prof, day, hour):
        """(sessions now, last session earlier today, next session) for one professor."""
        key = lambda s: (DAYS.index(s["day"]), s["from"])
        mine = sorted((s for s in self.sessions if prof in s["profs"]), key=key)
        now = [s for s in mine if s["day"] == day and s["from"] <= hour < s["to"]]
        last = [s for s in mine if s["day"] == day and s["to"] <= hour]
        later = [s for s in mine if key(s) > (DAYS.index(day), hour)]
        return now, (last[-1] if last else None), (later or mine or [None])[0]   # next week wraps round

    def find_prof(self, query):
        """Professor codes matching what the student typed: initials, else every name word
        close-matching a word of the name. Deterministic - no professor id comes from the model."""
        q = (query or "").strip()
        if q.upper().replace(".", "") in self.profs:
            return [q.upper().replace(".", "")]
        words = [w for w in re.findall(r"[a-z]+", q.lower().replace("'", "")) if w not in NOT_A_NAME]
        if not words:
            return []
        hits = []
        for code, p in self.profs.items():
            parts = re.findall(r"[a-z]+", (p["name"] or "").lower())
            if parts and all(get_close_matches(w, parts, n=1, cutoff=0.8) for w in words):
                hits.append(code)
        return hits

    def weekly(self, building):
        """For the page (Phase 2): node -> its parts, each with a weekly list of busy spans."""
        out = {}
        for part, r in self.rooms.items():
            if r["building"] != building or not r["node"]:
                continue
            busy = sorted({(s["day"], s["from"], s["to"], s["what"], "/".join(s["profs"]), s["makeup"])
                           for code in r["codes"] for s in self.sessions if s["room"] == code},
                          key=lambda b: (DAYS.index(b[0]), b[1]))
            out.setdefault(r["node"], []).append({"code": part, "own": r["own_sheet"], "busy": [list(b) for b in busy]})
        return {"as_of": self.as_of, "nodes": out}


def load(path):
    with open(path, encoding="utf-8") as f:
        return Timetable(json.load(f))


if __name__ == "__main__":   # the one runnable check: python timetable.py
    t = load("fixtures/timetable.json")
    assert len(t.states) == 60, len(t.states)
    # newest file wins: GJS moved Fri 10:00 from B112 (Aug 21 sheet) to A303 (Sep 3 sheet)
    assert t.status("B112", "Fri", 10)[0] == "free", t.status("B112", "Fri", 10)
    assert "GJS" in t.states[("Fri", 10)]["profs"] and t.states[("Fri", 10)]["profs"]["GJS"][0]["room"] == "A303"
    now, last, nxt = t.where("PSG", "Tue", 11)
    assert now and now[0]["room"] == "A302", now
    # halves: the two halves of lab 115 are separate parts on one node
    assert t.rooms["B115A"]["node"] == t.rooms["B115B"]["node"] == "web_technology_lab_115_f2"
    # a room with no sheet of its own is never called free
    assert t.status("B303", "Sun", 12)[0] == "no_data"
    # an own-sheet room we cannot place on the model still answers
    assert t.rooms["A103"]["node"] is None and t.status("A103", "Sun", 12)[0] == "free"
    # MAKEUP LEC is free, with the makeup slot carried as a note
    state, notes, _ = t.status("B103", "Mon", 10)
    assert state == "free" and notes and notes[0]["makeup"], (state, notes)
    assert t.find_prof("psg") == ["PSG"] and t.find_prof("Gotmare ma'am") == ["PSG"]
    assert "SRJ" in t.find_prof("joshi maam") and t.find_prof("zzqx") == []
    assert "web_technology_lab_115_f2" in t.weekly("bhaskaracharya")["nodes"]
    print(f"ok: {len(t.sessions)} sessions, {len(t.rooms)} room parts, {len(t.profs)} professors, as of {t.as_of}")
