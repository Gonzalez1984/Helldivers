# Audyt architektoniczny i domenowy generatora Helldivers Field Manual

Data: bieżąca sesja. Branch: `gonzalez1984-helldivers-work` @ `bfaf7a3`.
**Zgodnie z poleceniem: żaden kod nie został zmieniony w ramach tego audytu.** Wszystkie ustalenia poniżej pochodzą z lektury kodu (`crawler/*.py`) i z live-query do MediaWiki API helldivers.wiki.gg wykonanych wyłącznie w celu diagnostycznym (odczyt, brak zapisu).

---

## 1. EXECUTIVE SUMMARY

Projekt generuje PDF na bazie **binarnego modelu posiadania** (owned/not-owned) wyprowadzanego heurystycznie z tekstu kolumny „Source”/„Warbond” w tabelach wiki, przy użyciu dopasowania podłańcuchów (substring matching) na dwóch niezależnie utrzymywanych listach słów kluczowych (`ownership.py` i `validate.py`). Znalazłem i zweryfikowałem źródłowo dwie **niezależne, konkretne przyczyny** długo obserwowanych anomalii liczbowych (booster≈0, throwable=0) — obie są prostymi błędami zgodności danych/nazw, nie przypadkiem czy cache'em. Poza tym architektura ma głębszy problem strukturalny: model „katalog + dopasowanie tekstu źródła” jest z natury kruchy wobec zmian treści wiki i już teraz jest niespójny (broń ładowana inną ścieżką niż wszystko inne). Rekomenduję nie tylko punktowe poprawki, ale zmianę modelu danych z „Item + source string” na jawny **enum pochodzenia (provenance)** ustalany deterministycznie z API (kategorie/linki), zamiast zgadywany z tekstu.

## 2. CURRENT ARCHITECTURE MAP

```
app.py (CLI orchestrator)
 └─ warbonds.py   → discover_warbonds() : lista nazw Warbondów (z resolve redirectów)
 └─ catalog.py    → load_catalog(kind)  : per-kind lista Item (tabela HTML lub category members)
 └─ parse.py      → table_rows/parse_catalog/parse_stratagem_catalog/parse_weapons_from_category
 └─ ownership.py  → owns_by_source()/build_owned() : Item -> owned bool (substring heuristics)
 └─ extract.py    → per-Item image resolution (stratagem fast-path vs generic scoring; skip .svg poza stratagemami)
 └─ validate.py   → hard-fail asserts na finalnym zbiorze (duplikuje warbond_keywords)
 └─ pdf.py        → renderuje siatkę kart + paski strzałek (ReportLab)
model.py          → Item(dataclass): kind, title, source, stats, image, key=f'{kind}:{title.casefold()}'
api.py            → WikiAPI: get()+cache czasowe, brak backoff/Retry-After
```

Brak: statusu ownership jako enuma, śledzenia wersji/revision wiki, provenance per pole, testów jednostkowych parserów.

## 3. GAME-DOMAIN MODEL — CO GRA FAKTYCZNIE MODELUJE

W Helldivers 2 posiadanie przedmiotu wynika z: (a) darmowego ekwipunku startowego, (b) zakupu/odblokowania w konkretnym Warbondzie (wymaga Medali), (c) stratagemów bazowych odblokowywanych postępem w Ship Management (nie są przypisane do żadnego Warbondu i nie są „darmowe” w sensie startowym — są odblokowywane Requisition Slips niezależnie od gracza). Obecny kod **nie rozróżnia (c) od (a)** — traktuje je jako "assume_all_non_mission_stratagems=True" czyli "zgaduj że gracz ma wszystko czego nie da się jednoznacznie odrzucić". To jest uproszczenie świadome (komentarz w kodzie to przyznaje), ale ukrywa fakt, że **stratagem może być odblokowany, ale gracz może go jeszcze nie mieć odblokowanego w drzewku Ship Management** — kod tego nie modeluje wcale, bo wiki nie ma takiej informacji per-gracz.

## 4. OWNERSHIP MODEL ANALYSIS (KRYTYKA ZAŁOŻEŃ)

Kwestionowane założenia z briefu, ocena:

- **„katalog = posiadanie”** — FAŁSZYWE dla Warbondów (trzeba go kupić/odblokować stronicami), PRAWDZIWE tylko dla ekwipunku startowego i bazowych stratagemów. Kod miesza te dwa reżimy w jednej funkcji `owns_by_source`, rozróżniając je tylko przez to, czy tekst źródła "wygląda" jak nazwa Warbondu.
- **„wszystkie nie-misyjne stratagemy = posiadane”** — to świadomy, udokumentowany hack (`assume_all_non_mission_stratagems`, domyślnie True), NIE fakt domenowy. Powinien być jawną, opisaną w UI/README decyzją użytkownika, nie cichym domyślnym zachowaniem.
- **„katalog wiki = autorytatywne źródło posiadania”** — wiki opisuje TREŚĆ gry (co istnieje), nie STAN KONTA gracza. Nie ma i nie może być z samego wiki poprawnego 1:1 mapowania na "co ja posiadam" — może tylko dawać listę kandydatów do ręcznej selekcji (co zresztą `choose_extras()` już częściowo robi dla dodatkowych stratagemów, ale nie dla broni/pancerzy/boosterów).
- **„struktura HTML = struktura domeny”** — FAŁSZYWE i to jest źródło obu głównych bugów (patrz sekcje 5 i 8): nazwa strony wiki i treść kolumny tekstowej to artefakty redakcyjne wiki, nie stabilne API.
- **„podobieństwo nazwy pliku = tożsamość obrazka”** — częściowo prawdziwe dla stratagemów (dedykowany `icon_file` z kolumny Icon, dobre rozwiązanie), ale dla reszty przedmiotów `extract.py` zgaduje przez heurystyczny `_score()` na podstawie nazwy strony — kruche, i explicite pomija pliki `.svg`, mimo że `pdf.py` już potrafi je renderować (potwierdzone tą sesją).

## 5. CATALOG MODEL ANALYSIS

`crawler/catalog.py` ma jawną asymetrię: `primary`/`secondary` ładowane przez `api.category_members('Primary/Secondary Weapons')` + `parse_weapons_from_category()` (deterministyczne, oparte o kategorię MediaWiki — najbardziej solidne podejście w całym projekcie), podczas gdy `throwable`/`armor`/`booster`/`stratagem` idą przez `parse_catalog()`/`parse_stratagem_catalog()` na **twardo zakodowanej nazwie strony** (`CATALOGS` dict). To niespójne architektonicznie: dwie różne metody pozyskiwania danych bez udokumentowanego powodu poza "weapons zostały już naprawione w PR #1, reszta nie".

**Krytyczny, zweryfikowany fakt:** `load_catalog()` łapie **wszystkie** wyjątki (`except Exception as e: ... return []`), więc każdy błąd nazwy strony/struktury kończy się cichym `[]`, bez twardego fail — co bezpośrednio produkuje throwable=0 (patrz sekcja 8) bez żadnego ostrzeżenia widocznego użytkownikowi poza jednym printem do stdout, którego `validate.py` nie sprawdza.

## 6. WARBOND OWNERSHIP AUDIT

`parse_warbond_rewards()`/`classify_warbond_type()` (w `parse.py`) parsują tabelę nagród per-Warbond i klasyfikują typ nagrody na podstawie tekstu nagłówka sekcji/tabeli (np. "Booster", "Primary Weapon"). To podejście jest sensowne (Warbondy w grze faktycznie mają sekcjonowaną, oznaczoną strukturę stron rzeczy), ale jest **równoległym źródłem prawdy** względem per-kind katalogów: `build_owned()` łączy owned-by-source (heurystyka substring) z owned-by-warbond_keys (z `parse_warbond_rewards`) przez `x.key in warbond_keys`, zakładając że `Item.key` (`kind:title.casefold()`) wygenerowany w obu ścieżkach parsowania będzie identyczny stringiem — nie zweryfikowałem w tej sesji, czy tytuły z tabeli nagród Warbondu i tytuły z katalogu per-kind zawsze idealnie się zgadzają znakowo (różnice w spacjach/apostrofach/wielkości liter mogą cicho rozłączyć te dwa źródła, analogicznie do bugów w sekcjach 8-9).

## 7. STRATAGEM OWNERSHIP ANALYSIS

`is_mission_stratagem()` to zakodowana na sztywno lista 25 fraz-substringów (np. `'hellbomb'`, `'seaf artillery'`). Problem: to jest lista **nazw konkretnych stratagemów**, nie kategoria domenowa wykrywalna programowo — jeśli wiki doda nowy stratagem misyjny, kod go nie wykryje, dopóki ktoś ręcznie nie dopisze nazwy. To dokładnie ten typ „hardcoded item-name exception”, którego brief każe unikać, a już istnieje w kodzie bazowym (nie dodany przeze mnie w tej sesji). Wiki faktycznie ma dla stratagemów kolumnę/sekcję `category`/`section` (używaną częściowo: `item.stats.get('section')`), co sugeruje, że można by wykryć "mission-only" bardziej strukturalnie (np. po sekcji strony "Mission Stratagems" zamiast po nazwie) — nie zweryfikowałem czy taka sekcja istnieje wprost na stronie Stratagems, wymaga to dodatkowego zapytania do wiki.

## 8. BOOSTER ROOT-CAUSE ANALYSIS (ZWERYFIKOWANE ŹRÓDŁOWO)

Wykonałem live zapytanie `api.rendered_html('Boosters')` → tabela `['Icon','Booster','Description','Warbond','Price']`, `parse_catalog()` poprawnie zwraca **18** boosterów (nie 0) — więc parsowanie tabeli samo w sobie działa.

**Rzeczywista przyczyna niskiej liczby (booster≈1 z 18):** kolumna „Warbond” na wiki dla 6 podstawowych boosterów (Hellpod Space Optimization, Vitality/Stamina/Muscle Enhancement, Increased Reinforcement Budget, UAV Recon Booster) zawiera tekst `"Helldivers Mobilize"` **bez wykrzyknika**, natomiast `DEFAULT_WARBONDS` w `ownership.py` linia 8 definiuje `'Helldivers Mobilize!'` **z wykrzyknikiem**. `source_matches_warbond()` robi `w.casefold() in s` — czyli sprawdza, czy `"helldivers mobilize!"` jest podciągiem `"helldivers mobilize"`. Nie jest (brakuje `!`), więc dopasowanie do Warbondu **zawodzi**. Następnie kod trafia w `warbond_keywords` (linia 86/101), gdzie token `'mobilize'` **jest** podciągiem źródła → item zostaje jawnie odrzucony jako "z niewybranego Warbondu", mimo że to bazowy, darmowy Warbond startowy. Dla pozostałych 12 boosterów (Steeled Veterans, Cutting Edge, itd.) to normalne zachowanie — nie są w `DEFAULT_WARBONDS`/wybranych przez usera, więc odrzucenie bywa poprawne, ALE tylko jeśli user faktycznie ich nie ma.

**To jest wina niespójności tekstu wiki vs stała w kodzie, nie architektury per se** — ale ujawnia fundamentalną słabość: **cały ownership model opiera się na literalnym dopasowaniu tekstu**, które wiki może zmienić (dodać/usunąć interpunkcję, zmienić kapitalizację) bez żadnego ostrzeżenia w kodzie. Nie ma żadnego testu regresyjnego chroniącego przed tym typem cichej desynchronizacji.

## 9. THROWABLE ROOT-CAUSE ANALYSIS (ZWERYFIKOWANE ŹRÓDŁOWO)

`CATALOGS['throwable'] = 'Throwables'` (`crawler/catalog.py` linia 10) — **strona o tej nazwie nie istnieje** na helldivers.wiki.gg. Zweryfikowałem live: `api.rendered_html('Throwables')` → `WikiError: missingtitle`. Poprawna nazwa strony to **`"Throwable"`** (liczba pojedyncza, zweryfikowane przez `action=opensearch`). Ponieważ `load_catalog()` łapie wszystkie wyjątki i zwraca `[]` (sekcja 5), to skutkuje **zawsze** throwable=0 na tym branchu, bez żadnego twardego błędu — tylko print ostrzeżenia do stdout, którego nikt (w tym `validate.py`) nie sprawdza. To w 100% wyjaśnia throwable=0 zaobserwowane w tej sesji. (Rozbieżność z throwable=21 wspomnianym w prompt użytkownika sugeruje, że w innej/wcześniejszej wersji kodu nazwa strony była już kiedyś poprawiona lub inna, ale na obecnym `bfaf7a3` jest błędna).

## 10. IMAGE RESOLUTION ANALYSIS

`extract.py` ma dedykowaną szybką ścieżkę dla stratagemów (ikona wprost z kolumny `Icon` w tabeli, dobre podejście strukturalne), ale dla reszty kind-ów jawnie pomija pliki `.svg` (`continue`), mimo że `pdf.py` od tej sesji potrafi je renderować przez `svg2rlg`. To jest teraz **niespójność międzymodułowa**: `extract.py` zakłada ograniczenie, które już nie istnieje w `pdf.py`. Bug `DS-42 Federation%27s Blade`: `canonical_title()` w `parse.py` linia 20-25 robi `href.split('/wiki/',1)[1]` bez `urllib.parse.unquote()`, więc `%27` (zakodowany apostrof) trafia dosłownie do tytułu zamiast zdekodować się na `'`.

## 11. VALIDATION LOGIC AUDIT

`validate.py` duplikuje dokładnie ten sam string tuple `warbond_keywords` co `ownership.py` (dwa niezależne miejsca do synchronizacji ręcznej — DRY violation). Waliduje puste ownership, duplikaty kluczy, złe URL-e, brak dowodu dla stratagemów, przeciek z niewybranych Warbondów — ale **nie waliduje**, że każdy kind w `catalogs` faktycznie coś zwrócił (throwable=0 nie jest traktowany jako błąd krytyczny mimo że to prawdopodobnie zawsze oznacza błąd pipeline'u, nie stan faktyczny gry).

## 12. MEDIAWIKI/API ROBUSTNESS

`api.py`: prosty cache czasowy, brak exponential backoff, brak respektowania `Retry-After` na 429 — obserwowane sporadyczne 429 podczas resolve obrazków są po prostu logowane i pomijane (utrata danych, nie błąd twardy).

## 13. CACHE AND REPRODUCIBILITY

Cache oparty o czas (nie o revision id strony wiki) — oznacza że dwa uruchomienia w tym samym oknie czasowym dają identyczny wynik nawet jeśli treść wiki się zmieniła, a po wygaśnięciu cache wynik może się zmienić bez zmiany kodu — utrudnia to odróżnienie "zmiana w kodzie" od "zmiana na wiki" przy diagnozowaniu przyszłych regresji (dokładnie ta niepewność, która utrudniła też ten audyt przy próbie wyjaśnienia rozbieżności liczb z opisu zadania).

## 14. TESTING GAPS

Brak jednostkowych testów dla: `canonical_title` (encoding), `source_matches_warbond` (interpunkcja), `is_mission_stratagem` (lista nazw), `CATALOGS` (nazwy stron - powinny być weryfikowane testem integracyjnym z realnym API lub nagranym fixture HTML), `parse_catalog` na realnych fixture'ach HTML dla każdego kind.

## 15. PROPOSED DATA MODEL

Rozszerzyć `Item` o: `ownership_status: Literal['owned','not_owned','ambiguous']` zamiast dorozumianego include/exclude, `provenance: str` (np. `'category_member'`, `'warbond_reward_table'`, `'source_column_heuristic'`) zamiast tylko surowego `source`, opcjonalnie `wiki_revision_id` per pobrana strona dla reprodukowalności.

## 16. PROPOSED OWNERSHIP MODEL

Zastąpić dopasowanie substring w `source` tekstowym przez: (a) dla Warbondów — jawne mapowanie Item.key → Warbond na podstawie `parse_warbond_rewards()` (już istnieje, ale nie jest jedynym źródłem prawdy — powinno być), (b) dla bazowych stratagemów/ekwipunku startowego — jawna, oddzielna kategoria `base_unlock` zamiast wrzucania w ten sam heurystyczny bucket co Warbondy, (c) normalizować teksty Warbond (usuwać/ignorować interpunkcję typu `!`) przy porównaniu zamiast wymagać identyczności znak-w-znak.

## 17. PROPOSED CATALOG MODEL

Ujednolicić pozyskiwanie katalogów: dla kind-ów gdzie istnieje stabilna kategoria MediaWiki (tak jak Primary/Secondary Weapons), preferować `category_members()` nad parsowaniem tabeli HTML — bardziej odporne na redesign strony. Tam gdzie musi zostać parsowanie tabeli (Boosters, Armor), `CATALOGS` powinien być zweryfikowany przeciw rzeczywistym nazwom stron (Throwable, nie Throwables) i `load_catalog()` powinien **nie** łapać cicho wszystkich wyjątków dla kind-ów podstawowych — powinien eskalować jako twardy błąd/ostrzeżenie widoczne w `validate.py`.

## 18. RISK ASSESSMENT OF PROPOSED CHANGES

- Naprawa nazwy strony `Throwables`→`Throwable`: niskie ryzyko, czysto deklaratywna zmiana stałej.
- Normalizacja interpunkcji w dopasowaniu Warbondów: średnie ryzyko — trzeba uważać żeby nie zaburzyć odrzucania niewybranych Warbondów (fałszywe pozytywy).
- Zmiana `load_catalog` na nie-cichy fail: niskie ryzyko techniczne, ale zmienia UX (pipeline może teraz "crashować" tam gdzie wcześniej cicho dawał 0) — wymaga jawnej zgody użytkownika co do zachowania.
- Rozszerzenie modelu danych o `provenance`/`ownership_status`: większy refaktor, dotyka `model.py`, `catalog.py`, `ownership.py`, `pdf.py`, `validate.py` jednocześnie — wysokie ryzyko regresji bez testów, powinno być rozbite na osobne PR-y.

## 19. OPEN QUESTIONS FOR USER — RESOLVED

- ~~Czy chcesz, by literalne niedopasowanie tekstu Warbondu (np. brak `!`) traktować jako miękki fallback (normalizacja interpunkcji) czy wolisz naprawić samą stałą `DEFAULT_WARBONDS`?~~ **Rozwiązane**: dodano miękką normalizację (`_normalize_warbond_text()` w `ownership.py`, reużywana w `validate.py`).
- ~~Czy `load_catalog()` powinien w przyszłości **crashować** (twardy fail) przy błędzie pobrania katalogu podstawowego kind-u, czy zostać przy obecnym cichym `[]` + printem?~~ **Decyzja użytkownika (2026-09-03): zostawić ciche zachowanie na poziomie `load_catalog()`.** `load_catalog()` w `crawler/catalog.py` nadal łapie wszystkie wyjątki i zwraca `[]` z printem ostrzeżenia. Jednak żeby pusty katalog nie ginął w ciszy aż do wygenerowania PDF-a, dodano osobny twardy check w `crawler/validate.py`: jeśli **cały** katalog danego kind-u wraca pusty, `validate()` rzuca `RuntimeError` z listą brakujących kind-ów. To rozróżnienie zachowuje odporność ładowania per-item/per-page przy jednoczesnym głośnym sygnalizowaniu systemowego problemu (dokładnie ten scenariusz, który pozwolił `throwable=0` przejść niezauważenie).
- ~~Czy chcesz też, żebym w kolejnym kroku zweryfikował zgodność kluczy (`Item.key`) między `parse_warbond_rewards()` a per-kind katalogami (sekcja 6), zanim zaczniemy cokolwiek zmieniać?~~ **Sprawdzone (2026-09-03)**: dla wszystkich 10 Warbondów w `DEFAULT_WARBONDS`, każdy `Item.key` zwrócony przez `parse_warbond_rewards()` ma dokładnie pasujący klucz w co najmniej jednym per-kind katalogu (0 rozbieżności). Ryzyko opisane w sekcji 6 (literówki/różnice w apostrofach/spacjach rozłączające te dwa źródła) jest **teoretyczne, obecnie niezmaterializowane** — warto dodać to jako test regresyjny (patrz sekcja 14), ale nie wymaga natychmiastowej poprawki kodu.

## 20. RECOMMENDED NEXT IMPLEMENTATION STEP

Zacząć od **dwóch potwierdzonych, izolowanych, niskiego ryzyka poprawek** (bez zmiany modelu danych):
1. `crawler/catalog.py`: `'throwable': 'Throwables'` → `'throwable': 'Throwable'`.
2. `crawler/ownership.py`: normalizacja interpunkcji przy porównaniu nazw Warbondów w `source_matches_warbond()` (np. usuwanie `!`/`'` po obu stronach przed `casefold()`+substring), tak by `"Helldivers Mobilize!"` dopasowywało się do tekstu źródła `"Helldivers Mobilize"`.

Obie zmiany są punktowe, testowalne natychmiast (`python -m crawler --default-profile` i porównanie liczników throwable/booster), i nie wymagają szerszego refaktoru modelu danych, który zostawiam do osobnej decyzji (sekcja 19) przed implementacją.
