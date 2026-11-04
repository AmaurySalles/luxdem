# Authoritative roster for deputies and ministers

Research for [#93](https://github.com/AmaurySalles/luxdem/issues/93) (map [#83](https://github.com/AmaurySalles/luxdem/issues/83)). Checked 2026-11-04 against live sources. All fetches used an honest research User-Agent and stayed within robots.txt.

**Answer.** Partly. No single source has both stable ids and a full dated roster.
- **Deputies:** chd.lu person pages `https://www.chd.lu/fr/deputy/{id}` give the only stable person id. Use it as the actor key. One id covers a person's whole career: Kox has `319` for 2004–2019 plus his minister posts, and Baum has `859` for three legislatures. Each page lists every dated mandate, party group, committee and delegation role. Ministerial posts are also listed for people who were deputies.
- **The CHD open data** on data.public.lu (CC0) has the bulk dated rows: datasets 104 (committees), 105 (current deputies), 106 (former deputies, back to 1999) and 109 (votes). **These files have no person id.** They give names only, as separate surname and first-name columns.
- **Ministers:** gouvernement.lu has one page per government, back to 2009 and earlier. It is HTML only and has no ids. Members appear as `SURNAME Firstname` with their portfolios, and reshuffles are written as prose. Legilux SPARQL does **not** model people, only ministries (`legal-institution/MI` …).
- **Recommendation:** build `person` from chd.lu deputy ids, plus a synthetic id for minister-only people taken from the gouvernement.lu slug (e.g. `yuriko-backes`). Load `affiliation` rows from the open data CSVs and join them on (surname, first name). Always match on surname and first name together, never surname alone: CHD has two Baums (Gilles DP, Marc déi Lénk) and two Weyderts (Raymond 2009–13, Stéphanie 2023–).

## Sources compared

| Source | Stable id | Coverage | Fields | Access / licence |
|---|---|---|---|---|
| chd.lu deputy page `/fr/deputy/{n}` | **yes**, numeric, career-long (same id in declaration PDFs `wdocs-pub.chd.lu/declarations/1278_DIF_rev0.pdf`) | all deputies incl. former (Asselborn `49`: mandates from 1984) | name, dated mandates, group, committees/delegations with role (Président, Membre…), ministerial posts with ministry, birth date, outside mandates | HTML; robots.txt `Allow: /*/deputy/*`, `/*/commission/*`, `/*/group/*`. Pages are not indexed: the current 60 are listed on `/fr/deputies`, and former deputies have no list (found by search or by probing ids) |
| data.public.lu 105 *Députés actifs* | none | current 60 | title, surname, first name, `date_debut_depute`, group abbreviation, birth date, constituency | CSV (cp1252), refreshed daily (2026-11-04), CC0 |
| data.public.lu 106 *anciens Députés* | none | 328 mandates / 159 people, starts 1999 | title, surname, first name, start/end per mandate, group, party | CSV/XML/XLSX, CC0, **snapshot 2025-03-28** (misses people who left later) |
| data.public.lu 104 *organes, commissions, délégations* | committee id `grp_id` only; **not** the chd.lu web id (Justice: 183 here vs `/fr/commission/760`) | 3,655 rows. The 2009–13 legislature is thin (14 rows starting 2009); full from 2013 | committee, type, dates, role, surname, first name, group, role start/end | CSV (cp1252) daily, CC0 |
| data.public.lu 109 *votes* | none | CSV rows 2021-07 → 2026-07 (89k) | date, vote name (`PL8727`), surname, first name, group, result | CSV daily, CC0 |
| gouvernement.lu `/fr/gouvernement/anciens-membres-gouvernement/{slug}.html` | page slug only | Juncker–Polfer, Juncker–Asselborn I/II, Bettel–Schneider, B–S–Braz, B–S–Bausch, B–Kersch–Bausch, B–Lenert–Bausch, Frieden–Bettel (2023-11-17→2025-12-11), current | `SURNAME Firstname`, portfolios, government start/end; reshuffles as free text | HTML; robots.txt blocks only query strings. Legal notice: text may be consulted, downloaded and printed; nothing grants reuse beyond that |
| data.public.lu *Liste ministres et ministères 2023* (SIP) | none | Frieden I only, 2025-01 snapshot | `Firstname SURNAME` + portfolio in FR/DE/EN/LB | XLSX, CC0 |
| Legilux SPARQL | n/a | — | no person class. `jolux:responsibilityOf` → ministry codes. `personInCharge` holds an institution string. `prov:agent` holds back-office users | SPARQL, CC BY 4.0 |

## Sampled people

| Person | chd.lu | Open data | gouvernement.lu |
|---|---|---|---|
| Henri Kox | [`/fr/deputy/319`](https://www.chd.lu/fr/deputy/319): deputy 2004–09, 09–13, 13–18, 18–19. Ministre du Logement 11/10/2019–17/11/2023. Ministre délégué Défense / Sécurité intérieure, then Ministre de la Sécurité intérieure 23/07/2020– | 106: 4 mandates, déi gréng. 104: 44 rows | [B–S–Braz](https://gouvernement.lu/fr/gouvernement/anciens-membres-gouvernement/bettel-schneider-braz.html) reshuffle text: "Henri KOX entre au gouvernement… ministre du Logement" |
| Gilles Baum | [`/fr/deputy/859`](https://www.chd.lu/fr/deputy/859): deputy 2013–18, 2018–23, 2023–. President of the DP group and of the Commission du Logement | 105: `Baum,Gilles,…,DP`. 109: votes. Homonym Marc Baum (déi Lénk) | — |
| Stéphanie Weydert | [`/fr/deputy/1278`](https://www.chd.lu/fr/deputy/1278): deputy since 21/11/2023. Présidente of the Commission des Affaires intérieures since 03/02/2025. 20+ dated roles | 105 CSV. 104: 24 rows, mixed with Raymond Weydert (2009–13) on surname | — |
| Dan Hardy | [`/fr/deputy/1300`](https://www.chd.lu/fr/deputy/1300) | 105: since 2024-07-11, ADR. 109: `Hardy,Dan,ADR` | — |
| Jean Asselborn | [`/fr/deputy/49`](https://www.chd.lu/fr/deputy/49): deputy 1984–2004. Minister rows only for 2013–2023, **not 2004–2013** | 106 | [Juncker–Asselborn II](https://gouvernement.lu/fr/gouvernement/anciens-membres-gouvernement/juncker-asselborn-II.html): Vice-Premier ministre, Affaires étrangères |

The ministerial posts on chd.lu pages are incomplete (Asselborn has none before 2013), and people who were only ministers may have no page: a search found none for Yuriko Backes. So use gouvernement.lu for ministers.

## Mapping to the name forms in CHD documents

| Document form | Example | Join |
|---|---|---|
| Bulletin de vote | `ADR / Hardy Dan Non` | `lastname firstname` under a party header. Matches 105/109 columns directly. A compound surname like `Di Bartolomeo Mars` makes the surname/first-name split ambiguous, so try a longest-surname match against the roster |
| Rapport | `Mme Stéphanie WEYDERT` | title + first name + UPPERCASE surname. Case-fold, then match (surname, first name) |
| PV | `M. Gilles Baum (DP)` | title + first name + surname + (group). The group helps resolve homonyms |
| Dossier "Auteur" | `M. Henri Kox, Ministre du Logement` | name + office. Match the person, then the office against the gouvernement.lu portfolio valid on the document date |
| gouvernement.lu | `KOX Henri` | UPPERCASE surname first |

All forms carry the first name, so matching on (case-folded surname, first name), with accents removed, joins them to the roster. Spellings matched exactly across sources for the five people above. There is one encoding catch: 104, 105 and 109 are cp1252, while 106 is UTF-8 with a BOM.

## Caveats
- chd.lu robots.txt has `Disallow: /*/dossier/*` (as well as `/*/search`, `/*/ajax/*` and `?page=`). The current scraper (`app/methodo/scraper.py`) fetches `/fr/dossier/{n}`, which conflicts with that rule.
- Open data is refreshed "tous les deux mois en moyenne" ([chd.lu/fr/open-data](https://www.chd.lu/fr/open-data)). 104, 105 and 109 were dated 2026-11-04, but 106 has not changed since 2025-03-28.
- chd.lu ids are not documented as stable. What supports stability: ids are reused in the declaration PDF filenames, one id spans 1984–2004 (Asselborn), and the same ids appear in the de/en/lb versions of the site.

## Endpoints (fetched 2026-11-04)
- https://www.chd.lu/robots.txt, https://www.chd.lu/fr/deputies, https://www.chd.lu/fr/open-data
- https://data.public.lu/api/1/datasets/liste-des-deputes-actifs/ (105), `/liste-des-anciens-deputes/` (106), `/liste-organes-commissions-et-delegations/` (104), `/liste-des-votes-en-seances-plenieres/` (109), `/liste-ministres-et-ministeres-fr-de-en-lb-2023/`
- https://gouvernement.lu/fr/gouvernement/anciens-membres-gouvernement.html, https://gouvernement.lu/robots.txt, https://gouvernement.lu/fr/support/aspects-legaux.html
- https://data.legilux.public.lu/sparqlendpoint (class/predicate census for Person/Agent/Minist*/sign*)
