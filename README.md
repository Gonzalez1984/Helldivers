# Helldivers 2 — Owned Loadout Field Manual

This version deliberately uses the wiki's **semantic catalog tables** rather than guessing ownership from arbitrary links or visual HTML.

## Pipeline

1. Discover current Warbonds from `Warbonds`.
2. User selects owned Warbonds.
3. Download current semantic catalogs for Primary, Secondary, Throwables, Armor and Stratagems.
4. Treat `Starter Equipment` / `Free` / relevant Bridge or ship-management sources as base ownership.
5. Treat items whose source names a selected Warbond as owned.
6. For the requested default profile, assume all ordinary non-mission stratagems are already owned (the user explicitly asked for all basic and acquired-along-the-way stratagems). A strict mode remains available if personal stratagem ownership should be entered manually.
7. Resolve **actual wiki images**. Stratagems prefer `* Stratagem Icon.*`; weapons prefer `* Primary/Secondary Weapon Render.*`; armor prefers armor-set/body render assets.
8. Validate duplicates, ownership provenance, source URLs and image availability.
9. Generate an A4 printable PDF plus an audit page.

## Why this is stricter

The wiki explicitly says most personal weapons are unlocked through Warbonds, with exceptions, while support weapons are commonly acquired through Ship Management. Stratagems have several acquisition routes. Therefore a simple `page exists => user owns it` rule is wrong.

## Maintainer notes

Before making further changes to `crawler/`, read:
- `docs/audit_2025.md` — full architectural/domain audit (ownership model, catalog model, image resolution, validation gaps, proposed fixes).
- `docs/lessons_learned.md` — concrete pitfalls hit while debugging `throwable=0`/`booster` bugs (duplicated substring-matching logic, unverified wiki page names, `.svg` handling, Windows environment quirks). Read this first if you're picking up a bug report about wrong per-kind counts.


The PDF's audit page records the acquisition/source used for every included entry.

## Requirements

Python 3.11+

```bash
pip install -r requirements.txt
python -m crawler
```

Non-interactive:

```bash
python -m crawler --warbonds "Helldivers Mobilize!,Steeled Veterans,Democratic Detonation"
```

The generated PDF is `output/helldivers_loadout.pdf`.

## Cache

`cache/api` and `cache/images` are intentionally retained. A later run can reuse data and only refresh when cache files are removed.

For a completely fresh crawl, delete `cache/` and run again.

## Scope

Included:
- Primary weapons
- Secondary weapons
- Throwables / grenades
- Body armor
- Boosters
- permanent/non-mission Stratagems

Not included in the loadout booklet:
- helmets (they have no gameplay passive)
- capes
- player cards
- weapon attachments/patterns
- cosmetics
- mission-only stratagems unless explicitly selected

## Asset/licensing note

Images and game assets belong to their respective rights holders. The wiki content is generally CC BY-NC-SA 4.0 unless otherwise indicated. The PDF includes attribution and is intended as a personal reference, not a commercial asset pack.

## Default user profile

The project includes the user's requested profile:

- Helldivers Mobilize!
- Steeled Veterans
- Democratic Detonation
- Urban Legends
- Servants of Freedom
- Control Group
- Dust Devils
- Python Commandos
- Siege Breakers
- Borderline Justice
- Entrenched Division
- Castellan's Creed

Run it with `python -m crawler --default-profile`. This profile also assumes all ordinary non-mission stratagems are owned. Use `--strict-stratagem-ownership` if that assumption should be disabled.
