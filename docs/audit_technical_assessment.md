# Technical Assessment: Helldivers 2 Field Manual Crawler

Branch: `gonzalez1984-crawler-architectural-audit` @ `734be3d`.
**No code was modified to produce this document.** Findings come from reading
`crawler/*.py`, `docs/audit_2025.md` (prior session's audit, in Polish, still
largely valid), `docs/lessons_learned.md`, git history, and one live full run
of `python -m crawler --default-profile`.

---

## 1. EXECUTIVE SUMMARY

The crawler currently works and is materially better than the state described
in the task prompt: `booster=0` and `throwable=0` were real bugs from an
earlier commit and are **already fixed** (verified by a live run: catalogs are
now primary=52, secondary=23, throwable=21, armor=107, booster=18,
stratagem=114; final owned counts primary=52, secondary=22, throwable=21,
armor=30, booster=9, stratagem=80). So the specific numeric complaint in the
prompt is stale — but the prompt's deeper architectural challenge is not, and
remains almost entirely valid against the current code.

The project's core defect is unchanged: **ownership is derived by matching
free-text strings** (`Item.source`, a "Type" column, a "Warbond" column)
against hand-maintained keyword lists (`ownership.py:owns_by_source`,
`is_mission_stratagem`, `classify_warbond_type`, duplicated in `validate.py`).
This is not a domain model, it is text-matching that happens to currently
agree with the domain most of the time. Every "fix" applied so far
(`_normalize_warbond_text`, the `Throwable`→category rerouting, the icon_file
fast path) has been a patch to make specific observed strings match,
not a structural change to stop depending on string identity. The project has
already accumulated two rounds of "fix the string bug" (PR #3, #4) and the
underlying architecture that produces these bugs is untouched.

The Warbond-reward pipeline is **currently completely broken and silently
tolerated**: the live run shows `0 relevant reward rows` for **all 10**
selected Warbonds (see §6, §8). `build_owned` still produces 216 candidates
because of the separate keyword-based `owns_by_source` path, so nothing
crashes — this is the single most important finding in this audit, and it is
a direct, verifiable instance of the exact failure mode this audit was
commissioned to find: a parallel/duplicate source of truth silently
degrading to zero while a heuristic fallback path masks it. The root cause
was isolated during this audit (read-only diagnostics, no code changed,
§6): `discover_warbonds()` records a Warbond's link **display text** (e.g.
`"Helldivers Mobilize!"`) instead of the `href`'s actual target page title
(`Helldivers Mobilize Warbond`); that display text is a *redirect page*, and
`api.rendered_html()` calls MediaWiki's `action=parse` without
`redirects=1`, so it renders the one-line redirect stub instead of the real
Warbond page — for every single Warbond, since every entry on the
`Warbonds` index page follows this exact same display-name/redirect
pattern.

Recommendation: treat this audit as confirming the prior one's diagnosis and
adding one newly-discovered, currently-live, silent failure (Warbond reward
parsing = 0 rows for every Warbond). Do not implement fixes yet per the
prompt's explicit instruction; the next session should investigate §6/§8
before touching any other code, because it is actively producing wrong
ownership data in every generated PDF today.

## 2. CURRENT ARCHITECTURE

```
app.py            CLI orchestrator (argparse; --default-profile / --warbonds / --strict-stratagem-ownership / --refresh)
 ├─ warbonds.py    discover_warbonds() / choose_warbonds()
 ├─ extract.py     extract_warbond() -> parse_warbond_rewards(rendered_html(warbond), warbond)
 ├─ catalog.py     load_catalog(kind) -> per-kind list[Item] (HTML table OR category members)
 ├─ ownership.py   Ownership dataclass, owns_by_source(), is_mission_stratagem(), build_owned()
 ├─ extract.py     resolve_image() -> icon_file fast path or page-image heuristic scoring
 ├─ validate.py    hard-fail asserts on final owned set (duplicates warbond_keywords list)
 └─ pdf.py         ReportLab-based A4 grid renderer, incl. svg2rlg for .svg icons
model.py           Item dataclass: kind, title, source, acquisition, stats, image_*, key=f'{kind}:{title.casefold()}'
api.py             WikiAPI: requests + on-disk time-based cache, no backoff/Retry-After
config.py          paths/constants
```

Two independent, only loosely-reconciled ownership signals feed
`build_owned`: (1) `wb_items`/`wb_keys` from `parse_warbond_rewards` per
selected Warbond page, and (2) `owns_by_source`, a keyword/substring matcher
run per catalog item against `item.source`. The code comments in `app.py`
and `ownership.py` suggest these were meant to agree/reinforce each other;
in practice (2) alone is currently doing all the work because (1) returns
nothing (§6, §8).

Missing, confirmed again in this session: ownership status as an explicit
enum, wiki revision/version tracking, per-field provenance, parser unit
tests against frozen fixtures, and any validation that Warbond-reward
extraction actually produced non-zero rows for a selected Warbond it should
have.

## 3. SOURCE-OF-TRUTH ANALYSIS

| Data type | Authoritative source | Presentation-only | Safe to infer | Requires explicit evidence | Failure severity if wrong |
|---|---|---|---|---|---|
| Item existence/name (primary/secondary/armor/stratagem/booster catalog) | MediaWiki category membership (`Category:X`) where it exists; rendered HTML table otherwise | Table column order, icon graphic, card layout | Nothing — existence is a fact, not an inference | N/A | Hard fail if catalog for a kind returns 0 (already implemented in `validate.py`) |
| Item ↔ Warbond mapping | The per-Warbond reward page's own table (`parse_warbond_rewards`) | The catalog table's free-text "Source"/"Warbond" column, which is a redundant, human-edited restatement of the same fact | Nothing | Yes — this is exactly the "does the player own it" fact | Hard fail (currently silently degrades to "trust the catalog's Source column instead", §6) |
| Free/starter status | A recognizable structural marker (dedicated category, or the reward table's own "Free"/"Starter" section heading) — **not currently used**; the code trusts a free-text Source column value `'starter equipment'`/`'free'` | — | Nothing | Yes | Should hard-fail if the marker can't be found structurally, currently silent-passes on string match |
| Stratagem "mission-only" status | Ideally a wiki category or explicit page section (`Mission Stratagems`) if one exists — not verified live this session, flagged unresolved in prior audit too | The specific stratagem's own name | Nothing — this is exactly the fact in dispute | Yes | Currently silently governed by a 25-item hardcoded phrase list (`is_mission_stratagem`) — this is the "hardcoded item-name exception" the prompt explicitly forbids, and it already exists in the codebase, unfixed |
| Image identity | `imageinfo` on a filename obtained from an unambiguous per-row `File:` link (the `icon_file` fast path) | Guessed page-image scoring (`_score()`) based on filename substrings | Nothing safely — filename similarity is not identity | Yes, an explicit File: link | Should hard-fail (or flag LOW-CONFIDENCE) when only heuristic scoring resolved the image; currently just accepted silently if it doesn't hit `BAD` keywords |
| "All non-mission stratagems owned" | Not derivable from the wiki at all — this is a **user assumption**, not a wiki fact | N/A | N/A | This is a project-level policy decision, must be visible in the audit trail as ASSUMED, never CONFIRMED | Should never be silently treated as equal-confidence to a Warbond-table match; currently it is (both just become `owned=True` with no distinguishing field) |

Overall: the wiki's rendered "Source" column, wherever it duplicates a
structurally-derivable fact (Warbond membership, free/starter status), should
be demoted to a fallback/cross-check, not the primary signal. Right now it
*is* the primary signal because the structurally-correct signal (Warbond
reward tables) is broken (§6).

## 4. HELLDIVERS 2 DOMAIN MODEL

Distinct acquisition routes that the current code either doesn't model or
conflates:

- **Free/starter equipment** — owned by every player from account creation.
  Currently modeled via a Source-column string match (`'starter equipment'`,
  `'free'`) for catalog-table kinds, and via a hardcoded
  `source='Free Starter Equipment'` constant for weapons loaded from
  category membership (`parse_weapons_from_category` — this is **not** true:
  not every primary/secondary weapon is free/starter; most require Warbonds).
  This is a real domain-model bug independent of the string-matching
  fragility issue: `parse_weapons_from_category` currently asserts every
  category-listed weapon is free, which is factually wrong for the game.
- **Warbond rewards** — require Medals + Super Credits to purchase the
  Warbond and unlock the specific page. Correctly conceptually modeled as
  "Warbond reward" in `parse_warbond_rewards`, but the extraction is broken
  (§6).
- **Ship Management stratagem unlocks** — base stratagems (Eagles, Orbitals,
  Support Weapons, backpacks, sentries, emplacements) unlocked with
  Requisition Slips independent of any Warbond, and independent of the
  player's personal unlock progress (the wiki cannot know whether a given
  player has unlocked a given base stratagem). The code's
  `assume_all_non_mission_stratagems=True` default treats "exists, isn't
  mission-only, isn't Warbond-gated" as "owned" — this is an explicit,
  documented **assumption**, not a fact, and the prompt is right to demand
  this not be silently treated as equal-confidence to a Warbond match.
- **Mission-only/temporary stratagems** — only usable during specific
  missions/MOs, never permanently "owned" in the loadout sense. Currently
  detected by a 25-phrase hardcoded list of specific stratagem names.
- **Super Store armor** — rotating store purchased with Super Credits, not
  tied to any Warbond. Not distinguished at all in the current code; armor
  items whose Source column doesn't match a Warbond keyword and don't match
  starter/free either simply fall through to `not owned` — which happens to
  be roughly correct behavior (excluded rather than wrongly included) but
  for the wrong conceptual reason (absence of a keyword match, not a
  positive "this is Super Store" determination).
- **Items existing but not owned** — anything in a full catalog is real game
  content regardless of any specific player's account state. The catalog
  view (`load_catalog`) is correctly kept separate from the owned view
  (`build_owned`), which is good; the leak is in *how* "owned" gets decided,
  not in mixing the two lists.

## 5. OWNERSHIP MODEL ANALYSIS

**CURRENT BEHAVIOR:** `owns_by_source()` returns a plain `bool`. An item is
"owned" if (a) its Source string contains a selected-Warbond name
(punctuation-normalized), or (b) it's a stratagem, isn't mission-only, isn't
matched to any known Warbond keyword, and the global
`assume_all_non_mission_stratagems` flag is True, or (c) its Source string
contains `'starter equipment'`/`'free'`.

**PROBLEM:** Three semantically distinct confidence levels — "matched an
explicit Warbond reward row", "matched free/starter text", "assumed owned
because we couldn't prove otherwise" — collapse into the same boolean. The
PDF and `validate.py` cannot tell them apart, so a user reading the audit
page cannot distinguish "I definitely own this" from "the tool guessed I own
this." This is exactly the ambiguity the prompt's `CONFIRMED / ASSUMED /
UNKNOWN / NOT_OWNED` proposal is meant to solve.

**EVIDENCE:** `ownership.py` lines 86-115; `Item` (`model.py`) has no
ownership-status field at all, only implicit inclusion in the `owned` list.

**PROPOSED CHANGE:** Add `ownership_status: Literal['confirmed','assumed','unknown','not_owned']` and `provenance: str` (e.g. `'warbond_reward_table'`, `'free_starter'`, `'assumed_base_stratagem'`) to `Item`. `build_owned` should set these explicitly instead of returning a filtered list where the reason is already discarded. `validate.py` and `pdf.py` then render/require this field instead of re-deriving confidence from string matches a second and third time.

**WHY IT IS BETTER:** Matches the "audit document" goal stated in the
project's own README ("The PDF's audit page records the acquisition/source
used for every included entry") — currently the audit page can say *what*
string matched, but not *how confident* that match is, which is the more
important fact for an audit document.

**POSSIBLE DOWNSIDES:** Larger `Item`/dataclass surface; every call site
that currently treats ownership as binary must be updated; risk of
half-migrating (some paths set status, others still short-circuit to a
plain bool) if not done atomically.

Is the model *sufficient* otherwise? No — independent of the enum question,
`base + Warbond + assumed stratagems` as currently coded does not track
Super Store armor, doesn't validate that a "Warbond match" is actually
grounded in a real reward-table row (§6 shows it currently isn't), and
`parse_weapons_from_category`'s blanket `source='Free Starter Equipment'`
is factually wrong for most weapons (§4).

## 6. WARBOND MODEL ANALYSIS — CONFIRMED LIVE, CURRENTLY BROKEN

**CURRENT BEHAVIOR:** `extract_warbond()` calls
`parse_warbond_rewards(api.rendered_html(warbond), warbond)`, which requires
a table with both an `'item'` and a `'type'` header (case-folded), extracts
a link from the `item` cell, classifies the `type` cell's text via
`classify_warbond_type()`, and keeps the row only if classification succeeds.

**PROBLEM — VERIFIED LIVE THIS SESSION, ROOT CAUSE ISOLATED:** The live run of
`python -m crawler --default-profile` shows:

```
Helldivers Mobilize!: 0 relevant reward rows
Steeled Veterans: 0 relevant reward rows
Urban Legends: 0 relevant reward rows
Servants of Freedom: 0 relevant reward rows
Borderline Justice: 0 relevant reward rows
Control Group: 0 relevant reward rows
Dust Devils: 0 relevant reward rows
Python Commandos: 0 relevant reward rows
Siege Breakers: 0 relevant reward rows
Entrenched Division: 0 relevant reward rows
unique owned-by-Warbond item keys: 0
```

Every single selected Warbond returned zero reward rows. This is not a
per-Warbond content issue; it is systemic. **Root cause, isolated by live
diagnostic during this audit (read-only; no code changed):**

```
>>> api.rendered_html('Helldivers Mobilize!')  # length 1055 chars, no <table>
<div class="redirectMsg"><p>Redirect to:</p><ul class="redirectText">
<li><a href="/wiki/Helldivers_Mobilize_Warbond" title="Helldivers Mobilize Warbond">
Helldivers Mobilize Warbond</a></li></ul></div>
```

`discover_warbonds()` (`warbonds.py` line 11-16) builds its Warbond name
list from each link's **anchor display text** (`a.get_text(...)`), e.g.
`"Helldivers Mobilize!"` — but the link's actual `href` target is
`/wiki/Helldivers_Mobilize_Warbond`, a *different, canonical* page title.
The display text is itself the title of a **redirect page**.
`WikiAPI.rendered_html()` (`api.py` line 55-57) calls MediaWiki's
`action=parse&page=<title>` **without `redirects=1`**, so for a redirect
title it returns the one-line "Redirect to: ..." stub HTML, not the target
page's content — hence zero tables, zero reward rows, for every Warbond.
This reproduces for all 10 selected Warbonds because every entry on the
`Warbonds` index page follows the same "display text is a redirect, href
points to the real title" pattern; it is not a per-page content problem at
all, it's a single missed `redirects=1` parameter (or, better, using the
href-derived title instead of the display text) applied uniformly wrong
across the entire pipeline.

**WHY THIS IS THE MOST IMPORTANT FINDING:** Because `owns_by_source()`'s
keyword-substring fallback independently classifies items as "owned by
Warbond X" using the catalog's own Source column text, the pipeline
produces a plausible-looking `owned=216` result with a non-empty PDF even
though the entire structurally-grounded Warbond evidence path is silently
producing zero rows. `validate.py`'s existing "every selected Warbond must
be represented in the catalog" check
(`if not any(_normalize_warbond_text(wb) in _normalize_warbond_text(x.source)...)`)
also uses the *catalog's* Source text, not `wb_items`/`wb_keys`, so it
cannot detect this failure either — it would only fail if a Warbond had zero
matching catalog-Source rows too, which apparently isn't the case here.
This is a live example of exactly the failure mode the prompt is worried
about: parallel sources of truth where one silently degrades and the other
masks it.

**PROPOSED CHANGE:** Before any other work, live-fetch
`api.rendered_html('Helldivers Mobilize!')` (or whichever exact title
`discover_warbonds` resolves it to) and inspect the actual table headers and
"Type" column text against `classify_warbond_type()`'s keyword list. Add a
hard validation: if `wb_keys` is empty after processing at least one
selected Warbond, fail loudly instead of silently falling through to the
keyword-substring ownership path. Longer-term, `build_owned` should require
agreement between the two signals (or explicitly flag disagreement) rather
than treating the substring path as an unconditional fallback.

**WHY IT IS BETTER:** Turns a currently-silent, currently-wrong data
provenance chain into a visible failure, matching the project's own stated
audit goals.

**POSSIBLE DOWNSIDES:** If the two signals structurally can't be reconciled
(e.g. `Item.key` casing/apostrophe mismatches between reward-table parsing
and catalog parsing, as the prior audit hypothesized), a hard fail here
could block PDF generation entirely until that's fixed — arguably correct
behavior for an "auditable" tool, but a UX regression from "always produces
something" if not paired with a clear diagnostic message.

Separately, and independent of whether the extraction is fixed:
`classify_warbond_type()`, `is_mission_stratagem()`, and the two duplicated
`warbond_keywords` tuples (`ownership.py` + `validate.py`) are all
human-readable-string-dependent, exactly as the prompt suspected. A "generic
reward entity, classify later" model would be more robust only if the
classification signal itself became structural (e.g. a stable
per-Warbond-page section heading or a MediaWiki category per reward type)
rather than the "Type" column's free text — which is arguably no more
structural than what's used today, so this may be the same fragility moved
one column over rather than solved. This deserves live inspection of the
actual current Warbond page HTML before deciding, which is precisely what
next-step work should start with (§6, §20).

## 7. CATALOG MODEL ANALYSIS

**CURRENT BEHAVIOR:** `CATALOGS` (page-name table parsing) covers
primary/secondary/armor/booster/stratagem; `CATEGORY_CATALOGS` (MediaWiki
category-membership) covers primary/secondary/throwable. Primary and
secondary are listed in *both* dicts, but `load_catalog` checks
`CATEGORY_CATALOGS` first, so category membership wins for those two kinds
and the `CATALOGS` entries for `'primary'`/`'secondary'` are currently dead
code paths.

**PROBLEM:** This dual-dict structure is confusing (`CATALOGS['primary']`
and `CATALOGS['secondary']` are unreachable, which is not obvious from
reading `catalog.py` alone) and undocumented as to *why* certain kinds get
category-based extraction and others don't, beyond the inline comment
("Throwable is a redirect... no table of its own"). Comparing to the
prompt's underlying question: does one canonical equipment catalog + typed
views make more sense than separate catalogs? The category-membership path
(primary/secondary/throwable) is fundamentally list-of-titles-only — it
carries **no** Source/acquisition/stats data at all, which is why
`parse_weapons_from_category` has to fabricate
`source='Free Starter Equipment'` for every item (a confirmed domain-model
bug, §4). The table-based path (armor/booster/stratagem) carries genuine
per-item Source/stats/icon data. These are not just two ways to reach the
same shape of data — one path structurally cannot carry ownership evidence
at all, which is a strong argument that "which catalogs need Warbond-table
cross-referencing vs. which can assume free/starter" is a decision currently
being made implicitly by which extraction path was easiest to implement,
not by actual domain semantics.

**EVIDENCE:** `catalog.py` lines 7-23; `parse.py` line 160-165
(`parse_weapons_from_category` unconditionally sets `source='Free Starter
Equipment'`, `acquisition='Free'`).

**PROPOSED CHANGE:** Separate the catalog abstraction into two concerns:
(1) *enumerate all titles of a kind* (category membership is the right,
robust source here for weapons since it's not a text-scraped table), (2)
*determine acquisition route + evidence per title* (currently entirely
missing for category-enumerated kinds — should cross-reference the same
Warbond reward tables used elsewhere, not assume free/starter). Table-parsed
kinds (armor/booster/stratagem) already do (1) and (2) together per row,
which is fine as long as (2)'s Source-column data is corroborated against
Warbond reward tables rather than trusted alone (§6).

**WHY IT IS BETTER:** Removes a confirmed factual error (treating all
weapons as free/starter) and unifies "how do we know who owns this" across
kinds instead of it depending on which extraction mechanism happened to be
implemented for that kind.

**POSSIBLE DOWNSIDES:** More cross-referencing work per weapon
(category-enumerated items would need their own Warbond-reward-table
lookup, doubling effort compared to today's shortcut); risks reintroducing
the exact Item-key string-mismatch fragility flagged in the prior audit if
not done via a stable identifier (canonical title, not casefolded display
text) between the two paths.

## 8. BOOSTER ROOT-CAUSE ANALYSIS

**CURRENT BEHAVIOR (verified live):** `load_catalog(api,'booster')` returns
18 entries; final `resolved` set contains 9 boosters in the PDF.

**PROBLEM:** The prompt's premise (`booster=0`) no longer holds — this was
fixed in commit `f9f1171` per `docs/audit_2025.md` §8 (the
`_normalize_warbond_text` punctuation-stripping fix for
`"Helldivers Mobilize"` vs `"Helldivers Mobilize!"`). The remaining question
is whether 18→9 (roughly half excluded) is *correct*. Given the
`--default-profile` selects 10 of the ~13+ known Warbonds, and boosters not
tied to a selected Warbond and not free/starter should indeed be excluded,
9/18 is plausibly right — but this can't be confirmed without the Warbond
reward-table cross-reference, which is currently broken (§6). Since
`owns_by_source` is doing 100% of the work for booster ownership right now
(the fallback keyword path, not the broken `wb_keys`), whether 9 is the
*correct* set or just the set the keyword list happens to catch cannot be
verified until §6 is fixed.

**EVIDENCE:** Live run output (§ Executive Summary); `docs/audit_2025.md`
§8 root-cause writeup (still accurate as history, not as current state).

**PROPOSED CHANGE:** No change recommended until §6 is resolved; then
re-verify the 9-item booster set against the (now-working) Warbond reward
tables rather than the keyword fallback.

**WHY IT IS BETTER:** Confirms correctness via the structurally-grounded
signal instead of continuing to trust the fallback that happens to produce
a plausible-looking number.

**POSSIBLE DOWNSIDES:** None — this is a verification step, not a behavior
change.

## 9. THROWABLE ROOT-CAUSE ANALYSIS

**CURRENT BEHAVIOR (verified live):** `load_catalog(api,'throwable')`
returns 21 entries via `CATEGORY_CATALOGS['throwable'] = 'Throwables'` +
`api.category_members()` + `parse_weapons_from_category()`. Final resolved
count: 21 (100% retained).

**PROBLEM:** Confirmed fixed (was `'Throwables'` page-table lookup that
404'd; now `Category:Throwables` membership, per `docs/audit_2025.md` §9 and
commit `f9f1171`). However, because `parse_weapons_from_category` marks
**everything** it enumerates as `source='Free Starter Equipment'` (§4, §7),
100% throwable retention is not evidence the ownership logic is working —
it's evidence that every throwable is unconditionally marked ownable
regardless of whether it's actually a Warbond-gated grenade. This needs the
same Warbond-reward cross-reference fix as weapons before the 21/21 figure
can be trusted.

**EVIDENCE:** Live run output; `parse.py` lines 160-165.

**PROPOSED CHANGE:** Same as §7 — category-enumerated kinds need real
acquisition-route determination, not a hardcoded free/starter assumption.

**WHY IT IS BETTER:** Prevents a systematic over-inclusion bug that is
currently invisible because it "looks like" 100% correct data.

**POSSIBLE DOWNSIDES:** None identified; this is a correctness bug fix, not
a design tradeoff.

Are primary/secondary/throwable "genuinely three semantic categories," per
the prompt's question? Yes in-game (different equip slots, different HUD
icons, different stratagem-drop rules for support-weapon variants aside),
but structurally in the wiki they are three category-membership lists
fetched identically — three *views*, not three *parsers*. The current code
already reflects that correctly (one function, `parse_weapons_from_category`,
parameterized by `kind`).

## 10. STRATAGEM OWNERSHIP ANALYSIS

**CURRENT BEHAVIOR:** `assume_all_non_mission_stratagems` defaults to
`True` (i.e. `--strict-stratagem-ownership` is opt-in, not opt-out).
`is_mission_stratagem()` uses a 25-phrase hardcoded substring list. Anything
not classified as mission-only and not matched to a selected Warbond is
assumed owned.

**PROBLEM:** This is exactly the case the prompt calls out:
"available/unlockable/unlocked/owned/assumed-owned" collapse into a binary.
It is explicitly documented as an assumption in code comments and the
README, which is good practice, but the PDF output cannot currently
distinguish a `CONFIRMED` Warbond stratagem from an `ASSUMED` base
stratagem — both just appear as included items with a Source string, with
no visible confidence marker (§5).

**EVIDENCE:** `ownership.py` lines 86-104; README "Default user profile"
section already documents the assumption in prose, confirming the project
owner is aware this is a policy choice, not a fact.

**PROPOSED CHANGE:** Same enum from §5:
`ownership_status='assumed'` + `provenance='assumed_base_stratagem_ship_management'`
for this bucket, distinct from `'confirmed'` for Warbond-table matches. Also
replace the 25-name `is_mission_stratagem` hardcoded list with a structural
signal if the wiki's Stratagems page has a distinguishable section/category
for mission-only stratagems (needs live verification, not yet done this
session — flagged as unresolved in both audits now).

**WHY IT IS BETTER:** Makes the "trust me" assumption visible in the audit
document per-item instead of uniformly hidden, and removes a
maintenance-burden hardcoded name list that will silently miss any new
mission stratagem the wiki adds.

**POSSIBLE DOWNSIDES:** If no structural distinguishing signal exists on the
wiki for mission-vs-permanent stratagems, the hardcoded list may be
unavoidable — in which case the honest fix is to keep the list but make its
fragility explicit (e.g. a test that fails loudly if the wiki's Stratagems
table gains rows not covered by either the mission list or Warbond
matching, forcing a human to categorize new entries rather than silently
defaulting them to "assumed owned").

## 11. IMAGE RESOLUTION ANALYSIS

**CURRENT BEHAVIOR:** Two paths in `extract.py::resolve_image` — (1) fast
path via `item.stats['icon_file']`, a direct `File:` link captured from a
table's dedicated "Icon" column during parsing (armor/booster/stratagem);
(2) generic path via `api.pages(prop='images')` + heuristic `_score()`
scoring by filename substring, used when no `icon_file` exists (currently:
weapons, since `parse_weapons_from_category` produces no `stats` at all).

**PROBLEM:** Path (2) is filename-similarity-as-identity exactly as the
prompt warns against, and the live run shows it's not fully reliable: 2
items (`PLAS-15 Loyalist`, `PLAS-45 Epoch`) failed image resolution
entirely and were silently dropped from the PDF with only a printed
warning — meaning the generated PDF is missing 2 weapons the user
presumably owns, with no visible marker in the PDF itself that anything is
missing. `canonical_title()` (`parse.py` line 21-26) does correctly call
`unquote()` now, so the previously-flagged `%27`/apostrophe encoding bug
(`DS-42 Federation%27s Blade`) appears fixed — confirmed live: item #124
in the run is correctly titled `DS-42 Federation's Blade`.

**EVIDENCE:** Live run output ("Skipped 2 items due to missing images");
`parse.py` line 24 (`unquote(x)` present).

**PROPOSED CHANGE:** (a) Because weapons are enumerated via category
membership with no Icon column data, give them the same
page→official-file-relation treatment as armor/booster/stratagem where
possible — e.g. if the wiki's weapon infobox template has a canonical
"Image" or "Render" parameter accessible via the API (needs live
verification), extract that instead of scoring candidate filenames. (b)
Silently-dropped items due to image failure should be a validation
failure (or at minimum a visible line in the generated PDF/audit page),
not just a console print — an "audit document" that's silently missing
known-real items it decided not to render is a credibility problem for
exactly the audience this PDF serves.

**WHY IT IS BETTER:** Removes filename-guessing for the one remaining kind
that still needs it, and stops silently shipping an incomplete PDF.

**POSSIBLE DOWNSIDES:** If no structural per-page canonical-image API field
exists, heuristic scoring may be unavoidable for weapons — in which case
the PDF/audit output should at least flag which items' images were
resolved via heuristic vs. explicit link, consistent with the confidence
model proposed in §5.

## 12. MEDIAWIKI/API ROBUSTNESS

**CURRENT BEHAVIOR:** `api.py` has a simple time-based on-disk cache;
confirmed live this session: two `429 Too Many Requests` errors occurred
during image resolution mid-run, each just caught and logged as a per-item
warning (contributing to the 2 dropped items in §11 — it's not clear from
the run output whether those specific 2 failures were rate-limit-caused or
genuinely-missing-image-caused, which is itself a diagnosability gap).

**PROBLEM:** No exponential backoff, no `Retry-After` header handling, no
distinction between "this image genuinely doesn't exist" (permanent) and
"we got rate-limited" (retryable) in the error handling/logging — both
paths currently look identical to the user (`WARNING: Wiki API failed: 429...`
vs `WARNING: No trustworthy image for ...`), so a rate-limit-induced gap in
the PDF is currently indistinguishable from a genuine data gap without
reading the raw exception text.

**EVIDENCE:** Live run output lines: `WARNING: Wiki API failed: 429 Client
Error: Too Many Requests for url: https://helldivers...` (items #74 and
#174).

**PROPOSED CHANGE:** Add retry-with-backoff specifically for 429/5xx in
`api.py`'s request layer (respecting `Retry-After` if present), and
separately, make the failure classification in `resolve_image`/`app.py`
distinguish "retryable transport error, retried and still failed" from
"no matching image found after exhausting real candidates" so the two
failure modes produce differently-worded, differently-actionable warnings.

**WHY IT IS BETTER:** Directly reduces data loss (2 dropped items this
run may well be recoverable with a retry) and improves diagnosability.

**POSSIBLE DOWNSIDES:** Slower runs if backoff is conservative; needs a
retry cap to avoid hanging indefinitely if the wiki is genuinely down.

## 13. CACHE AND REPRODUCIBILITY

**CURRENT BEHAVIOR:** Time-based (TTL) cache in `cache/api/`, no wiki
revision ID tracking, no recorded parser version alongside cached data.

**PROBLEM:** Unchanged from prior audit's finding — two runs within the
same cache window produce identical output even if the wiki changed
underneath; a run after cache expiry can silently produce a different PDF
with no code change, making "why did my Field Manual change" undiagnosable
after the fact.

**EVIDENCE:** `docs/audit_2025.md` §13 (unchanged; not re-verified live this
session as no cache-expiry boundary was crossed during testing).

**PROPOSED CHANGE:** Record wiki page revision IDs (available via MediaWiki
`action=query&prop=revisions`) alongside cached responses and in a
run-metadata block in the generated PDF's audit page (page title +
revision ID + fetch timestamp per data source actually used for that run).

**WHY IT IS BETTER:** Lets a human answer "was this because the wiki
changed or because the code changed" without re-running with `--refresh`
and diffing.

**POSSIBLE DOWNSIDES:** Slightly larger cache files; one more API call
per distinct page if revision ID isn't already returned by the calls
already being made (needs checking — `rendered_html`/`category_members`
may already receive revision metadata for free).

## 14. TESTING GAPS

Confirmed: **zero** test files exist in this repository (no `tests/`
directory, no `test_*.py` files found in the current tree). Every fix so
far (per git history: PR #2, #3, #4) has been validated only by re-running
the full pipeline against the live wiki and reading console counts — this
matches the prior audit's finding and `docs/lessons_learned.md` §4's advice
("always verify with the full pipeline"), which is itself an admission that
no automated regression protection exists.

Recommended, in priority order given the confirmed-live issues in this
audit:
1. `parse_warbond_rewards()` against a frozen HTML fixture of one real
   Warbond page — this would have caught §6 immediately and automatically,
   rather than requiring a full live run + manual console-reading to
   notice.
2. `classify_warbond_type()` / `is_mission_stratagem()` against the actual
   current set of "Type" strings / stratagem names seen on the live wiki
   today (a snapshot test that fails when the wiki adds a Type value or
   stratagem name not covered by either function — turns silent
   misclassification into a visible test failure).
3. `canonical_title()` URL-decoding (already fixed; a regression test would
   have prevented needing to re-verify it live this session).
4. `parse_weapons_from_category` — should NOT hardcode "everything is
   free/starter" as the expected/intended behavior (§4, §7); a test here
   must encode the *correct* domain semantics (weapon acquisition varies),
   which will currently fail against real code — that's the point: don't
   write a test that encodes today's bug as correct.
5. `resolve_image` fast-path vs. generic-path selection and `_score()`
   ranking against known-good and known-bad filename sets.
6. `validate.py`'s empty-catalog and Warbond-representation checks against
   constructed catalogs (unit-level, no live API needed).

## 15. PROPOSED TARGET ARCHITECTURE

Three explicitly separated layers, matching the prompt's requested
Source/Domain/Presentation split:

- **Source model**: raw wiki facts as fetched — page HTML/tables, category
  membership lists, image file info, revision IDs. Lives in `api.py` +
  thin per-page parsers. No ownership concepts here at all.
- **Domain model**: `Item` + acquisition route + `ownership_status` enum +
  `provenance`. Built by reconciling *multiple* source signals (Warbond
  reward tables AND catalog Source-column text AND category membership),
  flagging disagreement rather than silently preferring one when they
  conflict. This is currently missing — today one signal (catalog Source
  text) unconditionally wins whenever the other (Warbond table) fails,
  invisibly (§6).
- **Presentation model**: what `pdf.py` renders — grouped/sorted views,
  confidence badges, audit trail per item. Should consume the domain
  model's explicit fields rather than re-deriving anything from raw source
  text (currently `validate.py` re-derives Warbond-match logic from
  `Item.source` a second time, independently of `ownership.py` — a
  DRY violation already flagged in the prior audit and still present).

## 16. PROPOSED DATA MODEL

```python
@dataclass
class Item:
    title: str
    kind: Kind
    url: str
    ownership_status: Literal['confirmed','assumed','unknown','not_owned'] = 'unknown'
    provenance: str = ''            # e.g. 'warbond_reward_table:Urban Legends'
    acquisition_route: str = ''     # e.g. 'warbond', 'free_starter', 'ship_management_base', 'super_store', 'mission_only'
    source_page_title: str = ''
    source_revision_id: str | None = None
    # existing fields retained: image_*, stats, stratagem_code, traits, notes
```

`ownership_status`/`provenance` replace the current implicit
include/exclude decision baked into `build_owned`'s filtering. `validate.py`
and `pdf.py` consume these fields directly instead of re-running
Warbond-keyword matching against `Item.source`.

## 17. MIGRATION PLAN

1. Fix and verify the Warbond reward-table extraction (§6) — this is a
   currently-live, silent bug and should be resolved (with fixture tests,
   §14) before any structural refactor, since the refactor's whole point is
   to make this kind of silent failure visible, and right now it would be
   easy to "fix" the refactor against data that's already wrong.
2. Add frozen-HTML fixture tests for the parsers listed in §14 as a safety
   net, using the *current* (post-§6-fix) live HTML as the fixture
   baseline.
3. Introduce `ownership_status`/`provenance` on `Item` (§16), initially
   populated by the existing logic unchanged (mechanical refactor, no
   behavior change) so the migration itself doesn't conflate "restructure"
   with "change ownership decisions."
4. Change `build_owned` to consult both signals (Warbond table + Source
   text) and set status/provenance explicitly per the decision tree in §5;
   flag disagreement instead of silently preferring one.
5. Fix `parse_weapons_from_category`'s incorrect blanket free/starter
   assumption (§4, §7, §9) using the now-working Warbond cross-reference.
6. Update `validate.py`/`pdf.py` to consume the new fields instead of
   re-deriving from `Item.source`; delete the duplicated `warbond_keywords`
   tuple in `validate.py`.
7. Address image-resolution robustness (§11) and API backoff (§12) as
   independent, parallel-track fixes — they don't block the ownership-model
   migration.

## 18. RISKS AND TRADE-OFFS

- Fixing §6 may reveal that far fewer items are legitimately Warbond-backed
  than the current keyword-fallback path currently includes — the next PDF
  generated after the fix could shrink meaningfully compared to today's
  216-candidate/183-resolved output. This is the *correct* outcome for an
  auditable tool but is a visible regression in item count that should be
  clearly explained to the user, not silently shipped.
- Hard-failing on previously-silent conditions (empty `wb_keys`, image
  resolution failures, Warbond/catalog disagreement) trades "always
  produces a PDF" for "sometimes requires human intervention" — correct
  for an audit tool, but a UX cost worth being explicit about.
- Structural signals (categories, section headings, revision IDs) may not
  exist for every fact the prompt wants (e.g. mission-stratagem detection,
  §10) — some hardcoded lists may be unavoidable; the goal should be
  making their fragility visible/tested, not necessarily eliminating them
  entirely.

## 19. WHAT SHOULD NOT BE CHANGED

- The overall pipeline shape (discover Warbonds → fetch rewards → fetch
  catalogs → resolve ownership → resolve images → validate → PDF) is sound
  and matches the domain reasonably well; the problems are within stages,
  not in the stage sequence.
- Category-membership-based enumeration for primary/secondary/throwable is
  the right mechanism for *listing* those kinds (robust against page-table
  redesign) — only the *acquisition-route determination* for those kinds is
  wrong, not the enumeration mechanism itself.
- The `icon_file` fast-path image resolution for armor/booster/stratagem is
  correct and should be the model extended to weapons, not replaced.
- `validate.py`'s existing hard-fail-on-empty-catalog check is good
  practice and should be kept; it just needs a sibling check for empty
  Warbond-reward extraction (§6), which is currently the actual live gap.
- The project's practice of documenting known assumptions in the README
  (e.g. the stratagem-ownership assumption) is good and should continue —
  the gap is in *machine-readable* provenance, not in the human-readable
  documentation, which is already reasonably honest about its own
  limitations.

## 20. RECOMMENDED NEXT IMPLEMENTATION STEP

Before any refactor: live-inspect `api.rendered_html()` for one selected
Warbond page (e.g. `'Helldivers Mobilize!'` or whatever exact title
`discover_warbonds`/`choose_warbonds` resolves it to) and determine exactly
why `parse_warbond_rewards` returns 0 rows for all 10 Warbonds in the
current live run (§6). This is the single highest-value, lowest-risk next
step: it is a read-only diagnostic, it targets a confirmed-live silent
failure (not a hypothetical), and every other proposed improvement in this
document (the confidence-status model, catalog cross-referencing, the
weapon free/starter bug) depends on the Warbond-reward signal actually
working before it can be trusted as an input to anything else.
