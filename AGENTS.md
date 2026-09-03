# Agent Rules

Rules only. For usage/pipeline/scope see `README.md`; for root-cause writeups,
resolved decisions and pitfalls see `docs/audit_2025.md` and
`docs/lessons_learned.md` — read both before touching `crawler/`.

- Catalog membership is not ownership. The wiki describes what exists in the
  game, not what a player owns. Never collapse "item is in a catalog" into
  "item is owned" without going through the existing Warbond/base-equipment
  ownership logic in `ownership.py`.
- Don't add item-name-specific hacks (e.g. extending the mission-stratagem
  keyword list) without first checking whether a structural signal exists
  (category, section, table column). If none exists and you add a
  name-based exception anyway, note it in `docs/lessons_learned.md`.
- Don't weaken `validate.py` to make a run pass. An empty per-kind catalog is
  a deliberate hard error (see `docs/audit_2025.md` §19) — if validation
  fails, fix the root cause, don't loosen the check.
- Don't claim a fix works without running it: `python -m crawler
  --default-profile` and compare per-kind counts against the previous run.
  Partial/unit-level checks are not sufficient proof (see
  `docs/lessons_learned.md` §4).
- Record non-obvious user decisions (e.g. "keep silent catalog-fetch
  failures") as a dated, appended entry in `docs/audit_2025.md`. Never
  overwrite or rewrite past entries — only append.
- Before changing Warbond-name matching or ownership heuristics, read
  `docs/lessons_learned.md` §1–2 (duplicated matching logic, unverified wiki
  page names).
