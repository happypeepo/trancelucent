# Building chat plan (CometChat)

One public chat room per building. Everyone with `/bhaskaracharya` open shares one room;
`/aryabhatta` is a separate room. Built for the CometChat "Zero to Chat" hackathon
(closes 2026-10-07). Nothing below is built yet. Khush decided section 2 on 2026-10-07.

Visitors never need a CometChat account. The server quietly creates an invisible CometChat
user for each anonymous `VISITOR` id and hands the page a pass to log in as it.

---

## 1. Facts this plan rests on (verified 2026-10-07)

| fact | source |
|---|---|
| App region is **`in`**. `GET /v3/groups` returns 200 on `api-in`, 401 on `us` / `eu` | live probe with the REST key |
| Only CometChat's sample group exists (`cometchat-guid-1`, private). Our GUIDs are free | same probe |
| The SDK ships a browser build, `CometChat.js` (~589 KB). A `<script>` tag gives a global `CometChat`. No npm, no bundler | setup-sdk docs, jsdelivr listing |
| UID and GUID allow letters, digits, `_` and `-`. `VISITOR` (a `randomUUID`, or the `v-...` fallback) is already a valid UID | key-concepts docs |
| **Auth Key** can create and log in users from the browser (CometChat calls this dev mode). **REST key** can do anything and must stay server side | key-concepts, authentication docs |
| A public group: `joinGroup(GUID, PUBLIC, '')`. Membership persists, so a visitor joins once | join-group docs |
| Moderation rules live in the dashboard. A sent message is `PENDING`, then `APPROVED` or `DISAPPROVED` via `onMessageModerated`. **A disapproved message is never delivered to anyone else**; only its sender ever sees it | ai-moderation, moderation getting-started |
| **Moderation may need a paid plan.** The MCP's `moderation-setup` bundle lists "a plan that includes Moderation (Enterprise/Plus)" as a prerequisite. Unverified on this app | CometChat MCP |
| Legacy extensions (Profanity Filter, Data Masking, Image Moderation) must be off before using the new rules, or each message is processed twice | moderation overview |
| Free plan: 100 monthly active users. Rate limit: 10,000 core ops/min, which login and createUser share | hackathon page, rate-limits docs |
| `sw.js` returns early for any cross-origin request, so CometChat's script, API and socket already bypass the service worker | `sw.js` |

## 2. Decisions (Khush, 2026-10-07)

**D1. SDK source: unpkg, pinned to an exact 4.x version, with an SRI `integrity` hash.**
One line. The pin and the hash mean an upstream change can't silently alter what runs.
Rejected: vendoring the 589 KB file into git, and an unpinned URL (silent upgrades mid-demo).

**D2. Login: a pass from our server, not a key in the page.**
`POST /chat-token` in `main.py` takes the visitor's `X-Visitor-Id`, uses the **REST key** to
mint a CometChat auth token for that UID (creating the user first if it doesn't exist), and
returns `{app_id, region, token}`. The page calls `CometChat.login(token)`. The REST key never
leaves the server, and the Auth Key isn't used by the app at all.
- Stdlib `urllib` only, ~25 lines. No new dependency.
- **`X-Visitor-Id` is validated against `^[A-Za-z0-9_-]{1,100}$` before it goes anywhere near a
  URL.** It's interpolated into the REST path, so this is the trust boundary.
- REST shape, confirmed through the CometChat MCP: first `POST /v3/users` with
  `{uid, name, withAuthToken: true}`, which creates the user and returns the token in one call
  (a new visitor, the common case). If the user already exists, `POST /v3/users/{uid}/auth_tokens`.
  CometChat lowercases uids; `randomUUID` output is already lowercase.
- **POST only** (Khush, 2026-10-07): opening `/chat-token` in a browser shows nothing, not even
  the app id. The page POSTs once per chat-tab open and gets `{app_id, region, token}`; a stored
  SDK session is reused and the pass goes unspent. CometChat keeps a user's newest 100 passes and
  retires older ones, so unspent passes don't pile up.
- Rejected: Auth Key in the page. The key would sit in public page source.

**D3. Credentials: env vars.** `COMETCHAT_APP_ID`, `COMETCHAT_REGION`, `COMETCHAT_REST_KEY` in
`.env` and as fly secrets. Unset means `/chat-token` returns 503 and the tab says "Chat isn't set
up on this server", the same honest failure as "The timetable is not loaded on this server."
One endpoint instead of a separate config endpoint.

**D4. Names: `Visitor 4F2A`**, the last four characters of the UID, uppercased. The server sets
it when it creates the user. No prompt, no new UI.

**D5. Load timing: on the first open of the Building chat tab.** A visitor who only navigates
never downloads 589 KB, never opens a socket, and never counts toward the 100 MAU. This keeps
the boot cost the `VISUAL PERFORMANCE PLAN.md` work paid for.
*(Revised: Building chat is now the default tab everywhere, so a desktop joins at page open and a
phone when Chat is opened. Every visitor who joins counts toward the 100 MAU.)*

**D6. History (default, not asked):** on open, load the last 30 text messages, then go live.

### Rules this knowingly bends

- `SPEC.md`'s out-of-scope list names **WebSockets**. The socket goes from the browser to CometChat's servers; ours stays plain HTTP. SPEC is historical per README, but it's named here so the decision is explicit.
- README and `context.md` say **no CDN** (D1).
- A new endpoint (`POST /chat-token`), an outbound call from `main.py`, and a new third-party service.
- Python dependencies are untouched. `requirements.txt` doesn't change.

## 3. Design

**Room.** GUID = the building slug from `BASE` (`/bhaskaracharya` becomes `bhaskaracharya`), so one file still serves every building and nothing is hardcoded. A building with no group gets "Chat isn't set up for this building yet."

**Flow, on the first open of the tab:**

```
POST /chat-token (X-Visitor-Id)         -> {app_id, region, token}, or 503 "not set up"   (D2, D3)
inject <script CometChat.js>            -> D1
CometChat.init(app_id, AppSettingsBuilder().setRegion(region)
               .autoEstablishSocketConnection(true).build())
getLoggedinUser()  || login(token)
joinGroup(GUID, PUBLIC, '')             -> "already joined" counts as success
MessagesRequestBuilder().setGUID(GUID).setLimit(30)
  .setCategories(['message']).setTypes(['text']).build().fetchPrevious()
addMessageListener('room', {
  onTextMessageReceived: m => only if m.getReceiverId() === GUID,
  onMessageModerated:    m => my own bubble: APPROVED -> normal, PENDING or DISAPPROVED -> stays dimmed
                              (Khush, 2026-10-07: no "removed" notice, a dimmed bubble is enough)
                              The event never arrived in testing, so recheck() also asks
                              getMessageDetails() every 2 s for up to 30 s after a send.
})
```

- **Filter by receiver.** A visitor who has opened both buildings is a member of both groups, and the listener gets messages from every group they've joined. Without the `getReceiverId() === GUID` check, Aryabhatta messages would show up in Bhaskaracharya.
- No `subscribePresenceForAllUsers()`: nobody needs presence, and it adds traffic.
- **Send:** `sendMessage(new TextMessage(GUID, text, RECEIVER_TYPE.GROUP))`. Your own bubble is dimmed while `PENDING`.
- Exact error codes ("user doesn't exist", "already joined") are confirmed against the docs or the CometChat MCP when this is implemented, not guessed.

**UI.** This follows the PWA rules in `.claude/PWA.md`: nothing scrolls, and the chat overlays the model.

- The `#chat` header `<p class="k">Ask</p>` becomes two tabs: **Ask** · **Building chat**. Ask is the default, and the assistant chat is untouched.
  *(Revised: now **Building chat** on the left as the default and **Ask AI** on the right margin,
  both bordered like buttons, on phone and desktop.)*
- The Building panel gets its own log (`#rlog`) and form (`#rf`). It reuses `.msg.u` (you) and `.msg.a` (others), and each of the others' bubbles carries a small mono name line. `#chips` is hidden on this tab.
- `say()` gains an optional target log instead of a second copy of it.
- Phone: the same `aside` overlay that `#mask` opens. `setChat()` focuses whichever tab's input is showing.
- Offline (`body.offline`): the panel says it's offline and Send is disabled. No dashes in any UI string.

**Files.** Banner-anchored splices only (`context.md`).

| file | change | size |
|---|---|---|
| `trancelucent.html` | tab markup, ~10 lines CSS, new `/* ---- building chat ---- */` region | ~60 lines |
| `main.py` | `POST /chat-token`: validate UID, mint token via REST (stdlib `urllib`) | ~25 lines |
| `.env.example` | three vars | 3 lines |
| `README.md` | Building chat section; tech-stack row; correct the "no CDN" line | short |
| `sw.js` | nothing (cross-origin is already skipped, and `/chat-token` is a POST, which it never touches) | 0 |

## 4. One-off setup, outside the repo

1. **Create the two groups**, once, with the REST key from `.env`:
   `POST https://${COMETCHAT_APP_ID}.api-${COMETCHAT_REGION}.cometchat.io/v3/groups`

   | guid | name | type | owner | members |
   |---|---|---|---|---|
   | `aryabhatta` | Aryabhatta | `public` | omitted (CometChat's system user) | none |
   | `bhaskaracharya` | Bhaskaracharya | `public` | omitted | none |

   - **The guid must equal the URL slug.** The page derives it from `BASE`, and a guid can never be changed after creation.
   - `public` means anyone joins without approval or a password. Visitors join themselves on first open, so nobody is pre-added.
   - Omitting `owner` makes CometChat's system user the owner, so there's no admin account for us to keep.
   - Up to 300 members a group keeps every feature. Above that, CometChat drops typing indicators and receipts, and we use neither.
2. **Dashboard → Moderation.** First check it exists on this plan. CometChat's `moderation-setup`
   bundle lists "a plan that includes Moderation (Enterprise/Plus)" as a prerequisite. If it's
   there: enable it, set the profanity rule to **Block**, and turn off the legacy extensions.
   Moderation rules are app-wide, so both rooms are covered by one setup.
3. **Keys live only in `.env` (gitignored) and fly secrets.** No key or App ID is in any tracked
   file. Khush chose not to rotate the REST key (2026-10-07).
4. **Deploy (Khush):** `fly secrets set COMETCHAT_APP_ID=... COMETCHAT_REGION=in COMETCHAT_REST_KEY=...`

## 5. Verification

- `node --check` on the extracted inline script (recipe in `context.md`).
- No env vars: opening the tab says "Chat isn't set up on this server", the rest of the page is unchanged, and the console is clean.
- `curl -X POST /chat-token -H "X-Visitor-Id: ../groups"` returns 400 and makes no REST call.
- `view-source:` of the page and every response the browser receives contain neither key.
- Two browsers (normal plus incognito) on `/bhaskaracharya`: a message from one appears in the other. A third on `/aryabhatta` does **not** see it.
- A visitor who opened both buildings sees each room's messages only in that room.
- A profane message: the sender's bubble stays dimmed, and the other browser never receives it.
- Network panel on a fresh load: no request to unpkg or CometChat until the tab is opened (D5).
- Phone viewport 390 x 844 and Fold 280 x 653: the tab fits, nothing scrolls the page, and the input is 16 px (no iOS zoom).

## 6. Hackathon demo (90 s max)

Their rules: the demo must show the connector/MCP in the editor, and the MCP doing real work is a third of the score.

1. **Editor, ~15 s.** A fresh Claude Code session with `cometchat-docs` loaded, pulling the group-chat recipe that this build follows. Record it during implementation, not as a re-enactment.
2. **Live chat, ~40 s.** Two phones on `/bhaskaracharya` chatting with the 3D model visible behind the overlay. A third screen on `/aryabhatta` shows a separate room.
3. **Moderation, ~15 s.** A blocked message vanishes for the sender and never reaches the other phone.
4. **Close, ~15 s.** Ask the assistant for a route in one tab, then talk to people in the building in the other.

Submit: quote-tweet the challenge thread with the video, tag @CometChat, #ZeroToChat. A repo link is optional (this repo is private).

## 7. Known ceilings

- `# ponytail:` **100 MAU.** Every unique visitor who opens the tab counts as one. A busy public month stops new logins. The upgrade is a paid plan. D5 already keeps the count to people who actually chat.
- **`X-Visitor-Id` is self-asserted** (D2). Anyone who learns another visitor's id can get a pass
  for it and post as them, and a script can POST random ids to create users until the MAU cap is
  gone. The keys stay safe either way. The upgrade is a per-IP rate limit on `/chat-token`.
- **Names aren't locked.** A logged-in user can rename themselves through the SDK
  (`updateCurrentUserDetails`). Blocking that is a dashboard role setting, if it ever matters.
- **Identity is anonymous.** Private browsing regenerates `VISITOR` on every reload, so that visitor is a new user each time.
- **No moderation tooling of our own.** Review happens in CometChat's dashboard (blocked and flagged queues).
