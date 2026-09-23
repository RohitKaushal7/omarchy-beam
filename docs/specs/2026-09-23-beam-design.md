# Beam — design

**Status:** approved design, pre-implementation · **Date:** 2026-09-23
**Plugin id:** `dev.reuk.beam` · **Repo:** `RohitKaushal7/omarchy-beam` · **Version:** 0.1.0

## 1. Purpose

Beam is a Spotlight-style launcher for Omarchy 4: one box, summoned with
`SUPER + ALT + SPACE`, that answers or does the thing you typed.

- Launch **apps** and run **Omarchy menu actions** by name — and, with an
  optional TypeSafe Jev key, by *meaning* ("screen warmer" → Nightlight).
- **Calculate and convert inline** — arithmetic, percentages, units, currency,
  time zones and dates, developer values — and copy the result with Enter. This
  restores the walker/elephant-calc behaviour Omarchy 3.8 had
  ([discussion #7237](https://github.com/omacom/omarchy/discussions/7237)) and
  goes well beyond the basic arithmetic in open PR #10294.
- **Search the web** with keyword shortcuts (`yt`, `g`, `gg` for Google AI
  Mode, …), open URLs, and hand anything else to the user's coding agent.

**Success criteria**

1. Feels instant: local results render within one frame (~16 ms) of a
   keystroke; rows containing a calculator answer within 40 ms.
2. Never surprises: late results cannot change what Enter activates; no row
   flicker or reshuffle except as a direct result of typing.
3. Cheap and quiet: no background work while closed; Jev is called only when
   local sources can't answer, debounced and cached.
4. Works without a Jev key; every feature can be switched off.
5. Matches Omarchy's design language and passes the plugin marketplace's
   validation and automated security baseline with outcome `passed`.

**Non-goals (v1):** plotting, variables beyond `ans`, algebra/symbolic maths,
file search, clipboard history, typed free-form arguments for actions
("volume 40%"), a Beam bar widget.

## 2. User experience

### 2.1 Surface

- Kind `menu` (gives the app-library facade: Omarchy's app search, icons and
  launching), `keepLoaded: true`, summoned by
  `omarchy-shell shell toggle dev.reuk.beam '{}'`.
- Full-screen transparent layer-shell window (`WlrLayer.Overlay`, exclusive
  keyboard focus, namespace `omarchy-beam`) with the menu's scrim; click
  outside dismisses.
- Centred card identical in styling to `omarchy.menu`: `Color.menu.*` tokens,
  `Border.surfaceSpec("menu", …)`, `Style.cornerRadius`,
  `Style.spacing.panelPadding`, `Style.font.menuFamily`. Default width 560 px
  (setting). The card's top edge freezes on the first keystroke and the list
  grows downward (menu behaviour). Max list height 70 % of the screen with the
  menu's folded-row peek and scroll scrims.
- Query line: a `Text` at `Style.font.heading` fed by a key catcher (as the
  menu does), placeholder `Beam…` at 0.58 opacity. A search chip, when active,
  renders inline before the text.

### 2.2 Result list, top to bottom

1. **Answer rows** (calculator family): result large (heading, Medium), the
   interpretation dim below (`357 ÷ 2`, `100 USD → INR · rates 2 h old`). Up to
   two alternate rows for multi-form values (`0xff` → `255`, `0b11111111`).
   Enter copies the plain value (`178.5`, no symbols), the row flashes
   "Copied", Beam closes.
2. **Shortcut / URL row:** `YouTube — press Tab to search`, or when the first
   word exactly matches a keyword and more text follows, `YouTube: lofi beats`.
   URL-like input shows `Open github.com/omacom`.
3. **Apps and Omarchy actions**, merged and ranked with the menu's scoring
   (exact 0 · prefix 10 · contains 30 · name 40 · description 60; apps −5,
   menus −2; ×1000 + depth×25 + order). Row anatomy mirrors the menu: icon
   column (36 px, `iconLarge`; app icons as images), label (heading, Medium),
   breadcrumb (`Setup › Power`, bodySmall, 0.52 opacity) — plus Beam's addition,
   a dim keybinding hint on the right when one exists.
4. **✦ Jev best match** — shown only when the literal search is weak (§3.4).
   Marked with ✦; label and breadcrumb as a normal row.
5. **Fallback rows** (always last, each can be disabled):
   `Search Google for "…"` (engine configurable) and `Ask agent: "…"`
   (`omarchy agent prompt "<query>"`).

Empty query: up to 6 **recent picks** (most recent first; stored in
`~/.local/state/beam/recent.json`).

Empty result state: the menu's `󰈉` glyph and `No matches for “…”`, with the
fallback rows still available.

### 2.3 Keys

| Key | Action |
|---|---|
| ↑ / ↓, PageUp / PageDown | Move selection (wraps; page = 6) |
| Enter | Activate selected row (copy answer / launch / run / open) |
| Tab | Turn a matching keyword or domain into a chip |
| Backspace on empty text with chip | Remove chip |
| Ctrl+Backspace, Ctrl+U | Delete word / clear (menu `Util.editsFilter`) |
| Ctrl+C | Copy the selected row's value (answer, URL, action command) |
| Ctrl+, | Open settings view |
| Esc | Clear text (and chip); if already empty, close |

Pointer: hover selects only after real pointer movement (`PointerMoveGate`);
click activates.

### 2.4 Risky actions

Menu items under `remove.*`, `system.*`, `update.*` and
`install.*` require confirmation (except `system.lock` and
`system.screensaver`): first Enter turns the row into
`Press Enter again to <Label>` (urgent colour); any other key cancels. The
check is code, based on the menu id path — never on Jev.

### 2.5 Stability rules (hard requirements)

1. **Selection follows item identity**, not index. Rows inserted by late data
   (✦ Jev) animate in above the selection (140 ms, `Easing.OutCubic`); the
   highlight stays on the same item. Enter always activates the item that is
   highlighted on screen at key-press time.
2. **Only keystrokes rebuild the list.** Async results may only *insert*
   rows — the ✦ row, or answer rows that arrive after the 40 ms window (e.g.
   while the engine is still starting) — and only for the text currently
   typed. They never remove, reorder or replace existing rows, and rule 1
   keeps the highlight on the same item.
3. **One commit per keystroke.** If the text cannot be a calculator query
   (QML pre-check: no digit, currency symbol, `0x`/`0b`/`0o`/`#`, operator or
   time/date keyword), the list commits immediately from local sources.
   Otherwise the list waits up to 40 ms for the engine's answer and commits
   once. Enter pressed inside that window is applied to the committed list for
   the current text.
4. **No blank frames:** the previous list stays until the new one commits; icon
   sources are cached; the card top is frozen while typing.
5. A strong local match (exact or prefix match on an app or action label)
   suppresses Jev entirely for that query.

## 3. Architecture

### 3.1 Components

```
manifest.json          kinds ["menu"], keepLoaded, entryPoints.menu = Beam.qml
Beam.qml               window, key catcher, list composition, stability rules,
                       engine process ownership, settings loading
ui/ResultRow.qml       menu-style row (icon · label · breadcrumb · hint · ✦)
ui/AnswerRow.qml       calculator answer row with "Copied" flash
ui/Chip.qml            search-engine chip
ui/SettingsView.qml    settings screen built from qs.Ui controls
lib/*.js               pure logic, no QML types (unit-tested with node):
  menu.js              JSONC strip/parse, tree, paths, scoring, risky-path check
  shortcuts.js         built-in engines, keyword/domain matching, URL detection
  compose.js           merges sources into rows, identity keys, insertion rules
  precheck.js          "could this be a calculator query?" gate
bin/beam.py            engine entry: `serve` (JSON lines), `eval`, `stats`, `selftest`
bin/beam/              stdlib-only Python package
  protocol.py          request loop, cancellation, idle exit
  calc.py              tokenizer + Pratt parser over Decimal; functions; %
  units.py             unit tables + conversion
  currency.py          rate cache/fetch + parsing ($, ₹, codes, words)
  timeparse.py         zones, abbreviations, date arithmetic
  devvals.py           bases, colours, unix time, byte sizes
  answer.py            ordered dispatcher with cheap regex gates; first claim wins
  jev.py               catalog, slicing, parallel calls, cache, usage log
  fmt.py               number formatting/grouping
tests/                 unittest (engine), node --test (lib), bench
```

### 3.2 Engine process

- Started lazily on the first summon: `["/usr/bin/python3", "-I",
  "<plugin>/bin/beam.py", "serve"]` via `Process`, `clearEnvironment: true`,
  environment limited to `PATH=/usr/bin:/bin`, `LANG`, `TZ`, `HOME`,
  `XDG_CACHE_HOME`, `XDG_STATE_HOME`, and `TYPESAFE_API_KEY` if set.
- Idle exit after 10 min (setting) without requests; restarted on the next
  summon. Crash → restart once; after a second crash within 60 s, the engine
  stays down for the session and Beam runs with local sources only.
- Protocol: newline-delimited JSON over stdin/stdout.
  - Request: `{"id": n, "op": "answer"|"jev"|"catalog"|"config", ...}`.
  - `answer`: `{"id", "q", "settings"}` → `{"id", "answers": [ {value, label,
    detail, copy, kind} ]}` (empty list = not claimed). Target ≤ 5 ms p95.
  - `jev`: `{"id", "q"}` → `{"id", "pick": {key, p} | null, "cached": bool}`;
    may arrive hundreds of ms later. The engine drops a pending Jev request
    when a newer `jev` request arrives.
  - `catalog`: the QML side sends the action/app catalog (keys + labels +
    breadcrumbs) when it changes; the engine hashes it to key the cache.
  - `config`: settings subset the engine needs (currency, digits, Jev on/off,
    debounce is QML-side).
- QML discards any reply whose id is not the latest for its op. Output larger
  than 1 MiB per line kills and restarts the engine.

### 3.3 Answer dispatcher

Order: developer values → time/date → currency → units → arithmetic. Each
parser has an O(1)-ish regex gate; the first parser that returns a result
claims the query and the rest are skipped. Plain words (`chrome`, `firefox
dev`, `gg ai`) must be rejected by every gate (tested explicitly).

### 3.4 Jev usage

- Called only when **all** hold: query ≥ 3 chars (setting) with a letter; no
  answer, chip or URL claimed it; no strong local match (§2.5.5); the user
  paused typing for 350 ms (setting); the normalised query is not cached.
- Catalog: all visible menu actions (after `when:` evaluation) plus apps, as
  Choice option keys `"<Label> — <Breadcrumb>"`, deduplicated, plus a
  `"(none of these)"` option. Rebuilt only when menu files or the app list
  change.
- Catalog > 254 items → split into ≤ 3 slices sent **in parallel** (one request
  each). Pick = highest-probability non-none answer across slices, accepted if
  p ≥ 0.35. If two slices return different picks both ≥ 0.35, one second-round
  Choice between them decides.
- Cache: LRU of 500 `(catalog hash, normalised query) → pick`, persisted to
  `~/.cache/beam/jev-cache.json`; invalidated when the catalog hash changes.
- Usage log: `~/.local/state/beam/usage.jsonl` (ts, tokens, latency, slices,
  cached, picked). `beam.py stats` summarises calls, cache hit rate, tokens and
  cost ($0.042 / M input tokens).
- Key: `TYPESAFE_API_KEY`, else the key file (default
  `~/.config/typesafe/api_key`, setting). Never stored in `shell.json`. No key or
  any error → no ✦ row, nothing else changes. HTTP 401/403 disables Jev for the
  session and shows the reason in settings.

### 3.5 Currency

- Source: ExchangeRate-API open access (`https://open.er-api.com/v6/latest/USD`,
  no key, ~160 currencies, daily updates). Terms require the attribution
  "Rates By Exchange Rate API" — shown in the currency answer's detail line and
  the README.
- Fetched on the first currency query of a day (refresh interval setting,
  minimum 1 h), cached at `~/.cache/beam/rates.json`. Stale rates are used when
  offline and labelled with their date. The fetch runs in a background thread;
  the first-ever currency query shows `Fetching rates…` until it lands (the
  answer row then updates in place — the only permitted in-place update, since
  the row already exists and keeps its identity).

## 4. Calculator scope

- **Arithmetic:** `+ - * / ^ %`, `x × ÷`, parentheses, implicit multiplication
  (`2(3+4)`, `3pi`), thousands separators (`1,20,000`, `120,000`), unary minus,
  functions `sqrt sin cos tan asin acos atan log ln abs round floor ceil min
  max`, factorial `!`, constants `pi e`, `ans`. Decimal arithmetic with 28-digit
  context; trig via float. No `eval`.
- **Percentages:** `18% of 2400`, `2400 + 18%`, `2400 - 10%`,
  `what % of 2400 is 432`, `432 is what % of 2400`.
- **Units:** length, mass, temperature, volume, area, speed, duration, data
  (SI and IEC), energy, pressure, angle. Forms: `5 ft in cm`, `72f to c`,
  `3.2 GB in MiB`, `5'11" in cm`, `100 km/h in mph`, `5 kg` (→ common
  targets).
- **Currency:** `100 usd in inr`, `₹2400 to eur`, `$50`, `50 bucks in rupees`,
  `50 eur` (→ home currency). Home currency `auto` = from `LC_MONETARY`/`LANG`
  (e.g. `en_IN` → INR), else USD.
- **Time and dates:** `3pm ist in pst`, `now in tokyo`, `time in london`,
  `days until dec 25`, `today + 90 days`, `tomorrow in 3 weeks`,
  `2026-01-15 - 2025-06-01`, `what day is 15 aug 2027`. `zoneinfo` plus a
  curated abbreviation and city map.
- **Developer values:** `0xff`, `0b1010`, `0o17`, `255 in hex|bin|oct`,
  `#ff8800` ↔ `rgb()` ↔ `hsl()`, unix timestamps (9–13 digits) → local time,
  `now in unix`, `1536000 bytes` → `1.46 MiB`.
- **Formatting:** Indian grouping for INR and when the locale is `en_IN` (or
  setting), locale grouping otherwise; 10 significant digits (setting);
  scientific notation beyond 1e15 / below 1e-6.

## 5. Search shortcuts and URLs

Built-in engines (each disable-able, overridable, extendable in settings):

| Keyword | Domain trigger | URL (`%s` = encoded query) |
|---|---|---|
| g | google.com | https://www.google.com/search?q=%s |
| gg | — | https://www.google.com/search?udm=50&q=%s (Google AI Mode) |
| yt | youtube.com | https://www.youtube.com/results?search_query=%s |
| ddg | duckduckgo.com | https://duckduckgo.com/?q=%s |
| gh | github.com | https://github.com/search?q=%s&type=repositories |
| w | wikipedia.org | https://en.wikipedia.org/w/index.php?search=%s |
| r | reddit.com | https://www.reddit.com/search/?q=%s |
| maps | — | https://www.google.com/maps/search/%s |
| aw | wiki.archlinux.org | https://wiki.archlinux.org/index.php?search=%s |
| aur | aur.archlinux.org | https://aur.archlinux.org/packages?K=%s |
| npm | npmjs.com | https://www.npmjs.com/search?q=%s |
| p | perplexity.ai | https://www.perplexity.ai/search?q=%s |
| cl | claude.ai | https://claude.ai/new?q=%s |
| x | x.com | https://x.com/search?q=%s |

- Keyword or domain + Tab → chip; keyword + space + text → top row without
  Tab (exact first-word match only).
- URL detection: scheme URLs; `host.tld[/path]` with a known TLD;
  `localhost[:port]`, IPv4`[:port]` → `http://`. A bare single word is never a
  URL.
- Opening: `Quickshell.execDetached(["omarchy-launch-browser", url])` (argv,
  never a shell string built from user input).

## 6. Actions and apps

- Menu data: parse `$OMARCHY_PATH/default/omarchy/omarchy-menu.jsonc` and
  `~/.config/omarchy/extensions/omarchy-menu.jsonc` (FileView, watched) with a
  port of the menu's JSONC/tree logic in `lib/menu.js`. `when:` conditions are
  evaluated in one batched `bash -lc` script per catalog rebuild (menu
  approach); rows whose `when` fails are hidden.
- Provider submenus (fonts, power profiles, themes) are included only as their
  parent entry in v1 (opening them runs `omarchy menu summon <id>`).
- Actions run through `Quickshell.execDetached(["bash", "-lc", action])` — the
  same trust model as the menu, whose JSONC files are the user's/Omarchy's own
  config. Beam closes before running.
- Keybinding hints: parsed from `omarchy menu keybindings --print` once per
  session (cached), matched to actions by command string and label.
- Apps: `shell.appLibrary.sortedEntries(query)`, `iconSource`, `launch`.
- Recent picks: last 20 activations (id + kind), shown up to 6 on empty query.

## 7. Settings

Stored inline on Beam's entry in `~/.config/omarchy/shell.json` (Omarchy
storage rule 3). Beam reads its entry via a watched FileView and writes via
`shell.updateEntryInline("dev.reuk.beam", settings)`. Settings view: Ctrl+, or
typing `beam settings`; built from `qs.Ui` Toggle/NumberField/Dropdown/
TextField.

| Key | Default |
|---|---|
| `sources.apps`, `.actions`, `.recent`, `.calculator`, `.units`, `.currency`, `.time`, `.developer`, `.shortcuts`, `.urls`, `.webSearchRow`, `.agentRow` | all `true` |
| `jev.enabled` | `true` (inactive without a key) |
| `jev.debounceMs` | 350 |
| `jev.minChars` | 3 |
| `jev.keyFile` | `~/.config/typesafe/api_key` |
| `jev.cacheSize` | 500 |
| `calc.homeCurrency` | `auto` |
| `calc.grouping` | `auto` (`auto`/`indian`/`international`) |
| `calc.significantDigits` | 10 |
| `calc.ratesRefreshHours` | 24 |
| `search.fallbackEngine` | `g` |
| `search.engines` | `[]` of `{keyword, name, url, domain?}` (adds/overrides) |
| `search.disabledBuiltins` | `[]` |
| `behavior.confirmRisky` | `true` |
| `behavior.keybindingHints` | `true` |
| `behavior.agentCommand` | `omarchy agent prompt` |
| `engine.idleExitMinutes` | 10 |
| `look.width` | 560 |
| `look.maxRows` | 8 |

The settings view shows Jev key status only (`found in env ✓` / `found in
file ✓` / `no key — Jev off`), never the key.

## 8. Privacy and security

- Sent to TypeSafe (only when Jev runs): the query text and catalog labels and
  breadcrumbs. Nothing else.
- Sent to ExchangeRate-API: a GET for the USD rate table. Never amounts.
- Search text goes only to the user's browser.
- Engine runs as `python3 -I` with a cleared environment and bounded output;
  no `eval`/`exec`; user input reaches processes only as argv elements, never
  shell strings (menu actions come from the menu config files, as in the
  menu).
- Repo contains no install/setup-named files, no `sudo`/`pkexec`,
  `systemctl`, package-manager commands or binaries, so the marketplace
  baseline outcome should be `passed`.

## 9. Testing and verification

- **Engine (unittest):** table-driven cases per parser (≥ 300 total) including
  negative cases that must not be claimed; formatting; currency with a fixture
  rate file; Jev against a local `http.server` fake (slicing, second round,
  cache, 401, 429, timeout, no key); protocol (stale-id handling, idle exit,
  oversized output); latency bench asserting answer p95 ≤ 5 ms and round trip
  ≤ 40 ms.
- **lib (node --test):** JSONC parsing on the real menu files, scoring parity
  with the menu on sample queries, risky-path detection, shortcut and URL
  detection, precheck gate, compose/identity insertion rules.
- **Static:** `omarchy plugin validate .`, `qmllint -I "$OMARCHY_PATH/shell"`,
  and a local run of the marketplace baseline patterns.
- **Live:** load in the running shell, exercise every result type, capture
  screenshots with `grim` for review and for `preview.png`.

## 10. Delivery

- Checkout: `~/.config/omarchy/plugins/dev.reuk.beam` (git, `main`); ignored by
  the dotfiles repo.
- Personal keybinding in `~/.config/hypr/bindings.lua`:
  `hl.unbind("SUPER + ALT + SPACE")` then
  `o.bind("SUPER + ALT + SPACE", "Beam", "omarchy-shell shell toggle dev.reuk.beam '{}'")`.
  The README documents this for other users (plugins must not edit user
  config).
- README: Install (`omarchy plugin add https://github.com/RohitKaushal7/omarchy-beam.git --enable`),
  Keybinding, Usage, Calculator reference, Search shortcuts, Jev (optional
  setup), Settings, Privacy, How it runs, Development, Remove, License, with
  the rates attribution.
- GitHub repo created only after the user confirms (public).
- Marketplace (later): category Productivity; tags `launcher`, `quickshell`,
  `ai`.
