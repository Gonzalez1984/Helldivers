# Lessons Learned — Crawler Maintenance Notes

Praktyczne wnioski z sesji naprawiającej `throwable=0` i `booster≈1`
(zobacz `docs/audit_2025.md` dla pełnego audytu architektonicznego).
Czytaj to przed kolejną turą napraw w `crawler/`.

## 1. Ten sam string-matching bug bywa zduplikowany w kilku miejscach

`ownership.py` i `validate.py` niezależnie implementują dopasowanie
nazwy Warbondu do tekstu źródła (`warbond_keywords`, substring match).
Naprawienie logiki tylko w jednym pliku **nie wystarczy** — drugi
zduplikowany check i tak odrzuci poprawny item na etapie walidacji.
Jeśli zmieniasz logikę dopasowania Warbondów, sprawdź oba pliki i
rozważ wydzielenie wspólnej funkcji (`_normalize_warbond_text` w
`ownership.py` jest teraz importowana też przez `validate.py` —
trzymaj się tego wzorca zamiast kopiować logikę ponownie).

## 2. Nie ufaj `CATALOGS` dict bez weryfikacji na żywo

`crawler/catalog.py: CATALOGS` mapuje kind → nazwa strony wiki. Strony
wiki bywają redirectami (np. `Throwable` → sekcja na `Weapons`) albo w
ogóle nie istnieją pod oczekiwaną nazwą (`Throwables` nie istniało).
`load_catalog()` łapie **wszystkie** wyjątki i cicho zwraca `[]` z
samym printem do stdout — `validate.py` tego nie sprawdza, więc taki
błąd nie zatrzyma pipeline'u, tylko po cichu wyzeruje kategorię.
**Zawsze zweryfikuj nazwę strony/kategorii live** (`api.rendered_html`,
`api.category_members`) zamiast ufać istniejącej stałej w kodzie.

## 3. `.svg` jest generalnie omijany poza dedykowanym fast-pathem

`extract.py: resolve_image()` ma dwie ścieżki:
- **fast path** przez `item.stats['icon_file']` (link z kolumny "Icon"
  w tabeli katalogu) — działa dla `.svg` i jest preferowana.
- **generic path** przez `api.pages(prop='images')` + heurystyczne
  scoring (`_score()`) — **jawnie pomija pliki `.svg`** (`continue`),
  mimo że `pdf.py` od dawna potrafi je renderować przez `svg2rlg`.

Jeśli dodajesz nowy kind lub naprawiasz image resolution, sprawdź
najpierw czy tabela źródłowa ma kolumnę `Icon` z bezpośrednim linkiem
`File:` — jeśli tak, dodaj ekstrakcję `icon_file` w odpowiednim
parserze (`parse_catalog`/`parse_stratagem_catalog` w `parse.py`)
zamiast polegać na generic page-image scoring.

## 4. Zawsze weryfikuj pełnym przebiegiem, nie fragmentem

Punktowe testy (`load_catalog()`, `owns_by_source()` w izolacji)
potrafią "przejść" mimo że pełny `python -m crawler --default-profile`
i tak zawiedzie na kolejnym etapie (np. `validate.py`, image
resolution). Po każdej poprawce uruchom cały pipeline i porównaj
finalne liczniki per-kind (stratagem/primary/secondary/throwable/
armor/booster) zamiast ufać częściowej weryfikacji.

## 5. Środowisko Windows — powtarzające się przeszkody

- `pip` nie jest na PATH — używaj `python -m pip`.
- Foxit PDF Reader blokuje `output/*.pdf` (PermissionError) dopóki
  użytkownik go nie zamknie — jeśli regen PDF failuje z
  `PermissionError`, zapytaj usera o zamknięcie przeglądarki zamiast
  zgadywać inną przyczynę.
- Wiele równoległych worktree tego samego repo (`C:\Projects\Helldivers`
  główny checkout, różne `gonzalez1984-*` worktree per sesja) łatwo
  prowadzi do pomyłek co do "która wersja jest najnowsza" — zawsze
  sprawdź `git log --oneline -3` i porównaj z `origin/main` przed
  założeniem że coś jest "aktualne".

## 6. Znane, wciąż niezaadresowane obszary (patrz `docs/audit_2025.md`)

- `is_mission_stratagem()` — hardcoded lista nazw stratagemów zamiast
  wykrywania strukturalnego (po sekcji strony).
- `%27` (zakodowany apostrof) nie jest dekodowany w
  `canonical_title()` (`parse.py`) — powoduje błędy resolve obrazków
  dla tytułów z apostrofem (np. `DS-42 Federation's Blade`).
- Brak exponential backoff/Retry-After dla HTTP 429 w `api.py`.
- Model danych (`Item`) nie ma jawnego `ownership_status`/`provenance`
  — ownership jest czysto implicit (include/exclude), co utrudnia
  debugowanie tego typu bugów w przyszłości.
