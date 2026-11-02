# Linking committee PVs to dossiers and splitting them by agenda item

Resolves [#88](https://github.com/AmaurySalles/luxdem/issues/88) (map [#83](https://github.com/AmaurySalles/luxdem/issues/83)). Builds on [`chd-document-types.md`](https://github.com/AmaurySalles/luxdem/blob/research/chd-document-types/docs/research/chd-document-types.md) (#84). Researched 2026-11-02.

## Gist

Yes on both counts. Each `chd.lu/fr/meeting/<id>` page gives everything needed in one place: the PV PDF link, and the **ordered agenda** (`<ol>`), where each item that concerns a dossier links to `/fr/dossier/<n>`. The PV text repeats the same numbered agenda at the top, then repeats each heading (`N.` plus the dossier number or title) in the body, in the same order. A splitter that walks the agenda and finds each heading `1..n` in order found **49/49 items in 8/8 PVs** (2020–2026, three committees). Recommendation: make the meeting the unit. Discover meetings from dossier pages, scrape each meeting page once (PV URL plus agenda items with dossier numbers), and split the PV text on the numbered headings. Check that the number of items found equals the number on the agenda, and fall back to the whole PV when it does not. Store one row per (meeting, item) with a nullable dossier number.

## Method and sources

- Dossier pages `https://www.chd.lu/fr/dossier/<n>` for 8357, 8358, 8116, 8481, 8535, 8534, 8532, 7642 (housing / logement, from #84's sample). Fetched 2026-11-02.
- Meeting pages `https://www.chd.lu/fr/meeting/<id>` for every meeting linked from those dossiers that I sampled: 9728, 11920, 12120, 12121, 12899, 12955, 13410, 13447, 13556, 13822, 1014572, 1014685, 1014695.
- PV PDFs (`wdocs-pub.chd.lu`, fetched with TLS verification off as in `app/methodo/scraper.py:101`, text extracted with `pypdf`) for 8 meetings: 9728 (LOG 03, 3.12.2020), 12120 (CSTRIPA 13, 16.12.2022), 12899 (LAT 08, 17.4.2024), 13410 (LAT 23, 8.5.2025), 13447 (AI 38, 23.4.2025), 13822 (LAT 31, 28.11.2025), 1014572 (LAT 39, 7.5.2026), 1014685 (LAT 41, 2.7.2026).
- Open-data portal: `https://www.chd.lu/fr/open-data` → dataset 110 `la-liste-des-reunions-de-commissions` (data.public.lu API).
- Throwaway prototype splitter (scratch, not committed). Its logic is described in §3.

## 1. Meeting page = PV ↔ dossiers mapping (authoritative)

`/fr/meeting/<id>` (e.g. 12899, Commission du Logement et de l'Aménagement du territoire, 17 avril 2024) contains:

- Title `Réunion de commission - 17 avril 2024`, a commission link (`/fr/commission/750`) and a video.
- "Documents utiles → Procès verbal": the PV PDF link (`https://wdocs-pub.chd.lu/docs/Reunions/2023_LAT/a0OMz00000BKL9bMAH/20260218_PV.pdf`). It was the only `wdocs-pub` link on all 13 meeting pages.
- Tab `Ordre du Jour`: `<div id="timeline-content-list"> <ol> <li class="chd-timelineContentList__item">…`, one `<li>` per agenda item, in order. Items about a dossier start with `<a href="/fr/dossier/8357">Dossier parlementaire n°8357</a> :` followed by the title and sub-points (`- Présentation du projet de loi`, `- Examen de l'avis du Conseil d'Etat`, …). Other items have no link (`Approbation des projets de procès-verbal…`, `Projet de règlement grand-ducal…`, `Informations sur les acquisitions de logements par l'Etat`, `Divers`).

| Meeting | Date | Items | Items with dossier |
|---|---|---|---|
| 9728 | 3.12.2020 (LOG) | 6 | 7713, 7684, 7642 |
| 12120 | 16.12.2022 (CSTRIPA) | 8 | 8116, 8107, 8098, 8103, 8113, 8110 |
| 12899 | 17.4.2024 (LAT) | 10 | 8357, 8358, 8359, 8362, 7856, 7642 |
| 13410 | 8.5.2025 (LAT) | 5 | 8535, 8532, 8534 |
| 13447 | 23.4.2025 (AI) | 5 | 8408, 8409, 8481 |
| 13822 | 28.11.2025 (LAT) | 3 | 8532, 8548 |
| 1014572 | 7.5.2026 (LAT) | 3 | 8535, 8534 |
| 1014685 | 2.7.2026 (LAT) | 7 | 8534, 8535 |

The links go both ways. Dossier pages link to `/fr/meeting/<id>` from their activity timeline ("Voir la réunion"), and every meeting listed on a dossier page has that dossier in its agenda. For example, 8534 lists 1014572, 1014685, 1014695 and 13410, and all four agendas contain 8534. The dossier timeline also links the PV, but it does not say which agenda item the dossier is. Only the meeting page gives the position.

You cannot get the meeting from the PV URL alone. Older PVs sit under `Reunions/<legislature>_<COMMISSION>/<Salesforce-style id>/<upload date>_PV.pdf` (e.g. `a0OMz00000BKL9bMAH`, which is not the meeting id). 2026 PVs sit under `Reunions_de_la_Commission_du_Logement_…/Documents_de_travail/Reunion_du_02-07-2026/20260922_PV.pdf`. The filename date is the upload date: all older PVs were re-uploaded as `20260218_PV.pdf`. So the meeting page is the join, or the footnote below.

PV text since about 2024 also carries the back-link in a footnote: `¹ Retrouvez la vidéo de la réunion ici : https://www.chd.lu/fr/meeting/12899` (12899, 13410, 13822, 1014572, 1014685; absent in 9728, 12120, 13447). It is a useful consistency check, but not a primary key.

Open data does not help. Dataset 110 (`110-reunion-commission.csv`, last resource update 2024-07-15) has only `MEETING_DATE, MEETING_NAME, MEETING_DESCRIPTION`. It has no meeting id, no dossier and no PV.

## 2. PV text structure: reliable agenda-item boundaries

All 8 PVs are born-digital and follow the same template:

1. Header: `P.V. LAT 08` (committee acronym plus sequence number), committee, `Procès-verbal de la réunion du 17 avril 2024`.
2. `Ordre du jour :` with numbered items `1.` … `n.`. Dossier items carry the number after the item number (`2. 8357`), then the title and sub-points. The item count and order match the meeting page's `<ol>` in all 8 PVs.
3. `*` separator → `Présents :` / `Excusés :` attendance → `*` → `Présidence :` → `*`.
4. Body: the same headings repeated in order, each followed by the discussion. Ends with `Luxembourg, le <date>` and signatures.

Body heading layouts vary by era and clerk, so a single regex is fragile:

- `2. 8357` on its own line, title on the next lines (12899, 12120, 9728, 13410, 13822)
- `2. 8534 Projet de loi portant modification…` on one line (1014572, 1014685)
- `2. Projet de loi n° 8408 portant abrogation…` (13447: dossier number inside the title, not after the item number)
- Some body headings drop the dossier number. In 12899 the body has `7.` and `8.` for agenda items `7. 8362` and `8. 7856`.
- Numbered text inside titles and bodies can look like a heading: 13447's agenda title contains `1. création d'un fonds de chômage ; 2. réglementation…`.
- The `1. Approbation…` item is not always there (1014572 starts with `1. 8535`).
- Page markers `3/10` appear on their own lines between headings and text.

## 3. Splitting rule (validated)

Prototype rule:

1. Drop page-marker lines (`^\d+/\d+$`).
2. Agenda = the lines between `Ordre du jour` and the first `*`. Collect the items by **sequential** number: the next item must be `k+1`, which rejects `1. création…` inside a title. Record the optional dossier number and the first words of the title.
3. Body = the lines after the third `*`. For each `k = 1..n`, the heading is the first line after heading `k-1` that matches `^\s*k\s*\.` and whose next ~4 lines (normalised) contain the item's dossier number or the start of its title.
4. Section `k` = from heading `k` up to heading `k+1` (the last section runs to the end).

Result: 49 of 49 agenda items located in 8 of 8 PVs, with no misplacements (checked by hand against the headings). Sections can then be tagged with dossier numbers from the meeting page's `<ol>` (same position) or from the PV agenda line.

Sub-points inside a dossier item (`• Présentation du projet de loi`, `Désignation d'un rapporteur`, `Examen de l'avis du Conseil d'État`) are visible but less regular, and the dossier-level split does not need them.

## 4. Recommendation

- **Unit = meeting.** Use the key `meeting_id` (from `/fr/meeting/<id>`). Fields: date, commission, PV URL, PV number (`P.V. LAT 08`). Dedupe: one PV is linked from every dossier on the agenda (12899 has 6 dossiers).
- **Discovery:** collect `/fr/meeting/<id>` links from dossier pages, which the scraper already fetches. Fetch each meeting page once.
- **Mapping:** parse `#timeline-content-list li` in order → `agenda_item(meeting_id, position, dossier_number | NULL, title, subpoints)`. Treat this as the source of truth for PV → dossiers.
- **Splitting:** extract the PV text and apply the rule in §3. Check that the number of headings found equals the meeting page's item count, and that the dossier number matches per position where the PV shows it. On a mismatch, store the whole PV against the meeting with no item split, and flag it.
- **Segment:** `pv_segment(meeting_id, position, dossier_number, text)`. Speaker and party extraction (#84 §3) runs per segment.
- Non-dossier items (Approbation, Divers, rapports d'activité, règlements grand-ducaux) get `dossier_number = NULL`. Keep them or drop them per downstream need.

## Open points

- Joint meetings (`réunion jointe … (FIN, LAT)`) not sampled. They may have one meeting page and one PV shared across committees.
- Meetings with no PV yet (recent) were not seen. All 13 sampled pages had a PV. The PV appears months later (2.7.2026 meeting → `20260922_PV.pdf`), so re-scrape is needed. The current scraper skips known dossiers (#84).
- Only meetings reachable from dossier pages were checked. No meeting index or sitemap was explored.
- Sample is 8 PVs (5 LAT/LOG, 1 CSTRIPA, 1 AI, from 2020 to 2026). Pre-2018 PVs not checked.
- The meeting pages' HTML structure (`chd-timelineContentList__item`) is undocumented and could change.
