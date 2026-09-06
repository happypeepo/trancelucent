"""Gemini Robotics ER 2 chat parsing.

One API call per request. Every response is validated twice: by its Pydantic
schema, then by checking every id it returned against the world model.
An id the world does not know becomes "unknown" with confidence 0.0.
"""

import os
import sys

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

MODEL = "gemini-robotics-er-2-preview"
# robotics-overview docs: "use medium for a good balance between latency and performance"
THINKING_LEVEL = "medium"

# --- plumbing ----------------------------------------------------------------

# Multiple keys, so one project running out of quota doesn't take the chat down.
# GEMINI_API_KEY is the primary; GEMINI_API_KEY_2, _3, ... are extra ones to fall
# back to, in order. Each is a distinct Google AI Studio project's key - rotating
# is not a way around one project's quota, it is spreading load across several.
def _api_keys():
    keys = [os.environ[k] for k in ("GEMINI_API_KEY",) if os.environ.get(k)]
    i = 2
    while os.environ.get(f"GEMINI_API_KEY_{i}"):
        keys.append(os.environ[f"GEMINI_API_KEY_{i}"])
        i += 1
    return keys


_clients = None
_key_index = 0


def _clients_lazy():
    # built lazily so import never touches the network or requires a key set
    global _clients
    if _clients is None:
        _clients = [genai.Client(api_key=k) for k in _api_keys()]
        if not _clients:
            _clients = [genai.Client()]  # surfaces the real "no key" error at call time
    return _clients


def _is_exhausted(exc):
    # 429 RESOURCE_EXHAUSTED is the quota signal; anything else (bad request, bad
    # schema, server error) is a real failure and must not be papered over by
    # silently trying the next key.
    return isinstance(exc, errors.APIError) and exc.code == 429


def _reject(kind, bad_id):
    print(f"gemini: rejected {kind} id {bad_id!r} — not in world model", file=sys.stderr)


def _call(parts, prompt, schema):
    global _key_index
    clients = _clients_lazy()
    last_exc = None
    for offset in range(len(clients)):
        i = (_key_index + offset) % len(clients)
        try:
            resp = clients[i].models.generate_content(
                model=MODEL,
                contents=[*parts, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
                ),
            )
            _key_index = i  # stick with the key that worked
            return schema.model_validate_json(resp.text)
        except errors.APIError as e:
            last_exc = e
            if not _is_exhausted(e) or offset == len(clients) - 1:
                raise
            print(f"gemini: key {i + 1}/{len(clients)} exhausted, trying the next one",
                  file=sys.stderr)
    raise last_exc


# --- chat: plain English -> one command --------------------------------------
# The model only parses intent. It never routes, never measures, never names a
# distance — main.py runs the command against the networkx world and writes the
# factual half of the reply itself.

CHAT_ACTIONS = ("route", "block", "unblock", "show_level", "reset_view", "not_found",
                "credits", "none")


# `floor` in the building file is a 1-based deck index: the ground floor is 1. Humans
# and the model both say "ground" and "level 6". These two are the only translation
# between the conventions - main.py phrases its replies with them too, so the sentence
# the visitor reads can never disagree with the deck the page lights up.
def level_name(floor):
    return "ground" if floor == 1 else f"level {floor - 1}"


def deck(level):
    """Inverse of level_name. None for anything that is not a level."""
    # the model answers "6", "level 6", "floor 6" or "L6" - all name the same deck
    s = str(level or "").strip().lower()
    for prefix in ("level", "floor", "lvl", "l"):
        s = s.removeprefix(prefix).strip()
    if s in ("ground", "g", "0"):
        return 1
    return int(s) + 1 if s.isdigit() else None

CHAT_PROMPT = """You turn a visitor's plain-English request into ONE command for the
navigation system of {building}.

Locations (id: name, type, level):
{nodes}

Equipment (id: name, at location):
{equipment}

Recent conversation:
{history}

The visitor now says: {message}

Choose exactly one action:
- "route"       they want to get somewhere. Set from_id and to_id.
- "block"       they report a place shut, blocked, flooded, closed or under repair. Set node_id.
- "unblock"     they report a place open or clear again. Set node_id, or leave node_id empty
                to clear every blockage at once.
- "show_level"  they want to look at one level or at all of them. Set level to "ground", to a
                level number exactly as it is written in the list above, or to "all".
- "reset_view"  they want the camera back where it started.
- "not_found"   they want to get somewhere, but no id in the lists above is the place they named.
- "credits"     they ask who made, built, designed or is behind this project, or whose it is.
- "none"        anything else: a greeting, or a question you cannot express as the actions above.

Rules:
- Every id MUST be copied from the lists above. Never invent one. Leave a field "" when it does not apply.
- If they name a piece of equipment as the destination, put the EQUIPMENT id in to_id.
- If they never say where they are starting from, leave from_id "" and the system starts at the entrance.
- accessible is true only when they ask for step-free, no stairs, wheelchair, pram, luggage or lift access.
- Resolve "there", "it", "that one", "the same place" against the recent conversation above.
- Visitors shorten a room to the building letter and its number: "B314", "b103", "B 112".
  Ignore the letter and match the number against the room names above - "b103" is the room
  named "Lecture Hall 103", "B314" the one named "... 314". Only match a number a room
  name actually contains; never invent a room for a number that is not in the list.
- "CodeCell", "code cell", "the CC room" and "the codecell room" all mean room 112, the room
  named "PG Seminar Hall 112" - that is where the CodeCell members are found.
- Student bodies and clubs are known by their room, not by the room's name on the plan:
  "CSI" or "Computer Society of India" is room 311, named "Tutorial Room-1 311".
  "Bloombox" is room 314, named "Advance Database Management System 314".
  "SMLRA" is room 216, named "Artificial Intelligence & Robotics Lab 216".
- reply: ONE short friendly sentence, used only when the action is "none" or "not_found".
  Never state a distance, a number of metres, a level count or a list of steps — the
  system works those out itself.
- for "not_found", reply names the place you could not find and stops there. The system
  adds the offer of help itself, so do not offer anything or ask a question.
"""


class ChatCommand(BaseModel):
    action: str
    from_id: str
    to_id: str
    node_id: str
    level: str
    accessible: bool
    reply: str


def chat(message, history, world):
    nodes = "\n".join(
        f"- {n['id']}: {n['name']}, {n['type']}, {level_name(n.get('floor', 1))}"
        for n in world.nodes.values()
    )
    equipment = "\n".join(
        f"- {e['id']}: {e['name']}, at {e['node']}" for e in world.equipment.values()
    ) or "- (none)"
    prompt = CHAT_PROMPT.format(
        building=world.building, nodes=nodes, equipment=equipment,
        history=history or "(nothing yet)", message=message,
    )
    r = _call([], prompt, ChatCommand)

    if r.action not in CHAT_ACTIONS:
        _reject("chat action", r.action)
        r.action = "none"
    for field in ("from_id", "to_id", "node_id"):
        value = getattr(r, field)
        if value and not world.has(value):
            _reject(f"chat {field}", value)
            setattr(r, field, "")
    return r
