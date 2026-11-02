# CHD dossier document types and their actor information

Resolves [#84](https://github.com/AmaurySalles/luxdem/issues/84) (map [#83](https://github.com/AmaurySalles/luxdem/issues/83)). Researched 2026-11-02.

## Gist

A housing dossier carries ~10–25 documents; the pipeline ingests only `Document de dépôt`. All sampled documents but one are born-digital PDFs (text layer present). Avis, amendments and verbatims are already in the `resource` table but **cannot be fetched by exact title** (titles embed dossier/doc numbers and dates). Rapports de commission, committee PVs, textes votés and vote bulletins are **not scraped at all** (different CSS class). Actor info is rich and regular: avis name the body in the title and use formulaic stances; PVs give speaker + party in parentheses and per-group committee votes; bulletins de vote give per-deputy, per-party Oui/Non/Abst.

## Method and sources

- Code: `app/methodo/scraper.py` (`find_doc_download_url`, `scrape_chd_lu_for_dossiers`), `app/db_model/retrievers/resource_retriever.py`, `app/methodo/main_pipeline.py:27`.
- DB: local `luxdem_db` (741 dossiers, 4,493 resources), queried 2026-11-02.
- Live pages: `https://www.chd.lu/fr/dossier/<n>` fetched 2026-11-02 for 20 dossiers: 8577 (issue's example) + 19 housing dossiers picked from DB titles (logement / loyer / bail / aménagement communal / Pacte logement): 8008, 8073, 8076, 8082, 8086, 8116, 8197, 8272, 8353, 8357, 8358, 8359, 8369, 8481, 8532, 8534, 8535, 8548, 8589.
- Documents: every `wdocs-pub.chd.lu` link on those pages inventoried (deduped by URL); 4 per type downloaded and checked with `pypdf` (pages, extracted chars, Producer/Creator).

## 1. Inventory (20 sampled dossiers)

Type = filename suffix after `YYYYMMDD_` in the URL (stable vocabulary; the title text is not).

| Type (URL suffix) | Docs | Dossiers with ≥1 | Scraped into `resource`? | Typical pages | Format |
|---|---|---|---|---|---|
| Document de dépôt (`_Depot` / `_Depôt`) | 21 | 20/20 | yes | 4–130 | native (InDesign) |
| Avis du Conseil d'État (`_Avis`) | 19 | 19/20 | yes | 2–12 | native (InDesign) |
| Avis complémentaire du CE (`_Avis`) | 6 | 6/20 | yes | 2–4 | native |
| Avis chambres professionnelles (CC, CSL, CdM, CHFEP) (`_Avis`) | 43 | 18/20 | yes | 2–20 | native (InDesign / Word) |
| Avis complémentaire chambres pro | 8 | 5/20 | yes | 2–20 | native |
| Avis other bodies (SYVICOL, FEDAS, CNPD, OAI, CSPH, Huissiers…) (`_Avis`) | 27 (+3 compl.) | 15/20 | yes | 2–12 | native |
| Amendement gouvernemental (`_AmendementGouvernemental`) | 3 | 3/20 | yes | 20–92 | native |
| Amendement parlementaire (`_AmendementParlementaire`) | 8 | 6/20 | 6 of 8 | 2–112 | native; **1 scanned** (8353 plenary amendment, Xerox, 0 chars) |
| Prise de position du Gouvernement (`_PositionGouvernement`) | 2 | 1/20 (propositions de loi) | yes | 2 | native |
| Rapport de commission (`_RapportCommission`) | 15 | 15/20 | **no** | 4–8 | native (InDesign) |
| Committee procès-verbal (`_PV`) | 35 | 17/20 | **no** | 3–10 | native (Word / PDFMaker) |
| Texte voté (`_TexteVote`) | 14 | 14/20 | **no** | 1–20 | native (Word) |
| Bulletin de vote (`_BulletinVote`, since 2025 `_BulletinPremierVote`) | 19 | 15/20 | **no** | 2 | native (JasperReports, tabular) |
| Dispense du second vote (`_AccordDispenseSecondVote`) | 14 | 14/20 | **no** | 2 | native |
| Verbatim plenary debate (`/docs/archive/…/<id>_pdf`) | 17 | 15/20 | yes | 2–5 | native, two-column CR pages |
| Résumé du dossier (`_Resume`) | 15 | 15/20 | yes | 1 | **.docx** until ~2025, PDF after |
| Corrigendum, Demande/Bulletin vote séparé | 4 | ≤2/20 | no | 1–2 | native; DemandeVoteSepare is a Xerox scan with text layer |
| Dossier complet (`compilation/docpa/pdf/<n>_Dossier_Complet.pdf`, also `.zip`) | 1 each | 20/20 | no | all-in-one (8357: 5.1 MB) | native |

Five sampled dossiers (8008, 8082, 8086, 8272, 8589) are still pending, hence no rapport / vote documents.

DB-wide (741 dossiers) title families in `resource`: dépôt 734, avis other 1,693, avis CE 606, avis CE compl. 207, verbatim 450, amend. parl. 181, amend. gov. 81, prise de position 24, "Rapport" 4 (Cour des comptes only). No PV, rapport de commission or texte voté rows exist.

## 2. Can `retrieve_all_resources` fetch them by title?

`retrieve_all_resources` filters `Resource.title == title` (exact equality, `resource_retriever.py`). Only two titles are constant strings:

- `Document de dépôt` (734 rows, 1 distinct title)
- `Résumé du dossier` (469 rows, 1 distinct title)

Every other title is unique per row (`avis_other`: 1,693 rows, 1,693 distinct titles). Exact strings seen on pages / in DB:

- `8353/03 - Avis du Conseil d'État (19.3.2024)` (older, with date) vs `8577/04 - Avis du Conseil d'État` (2025+, no date); also `Avis du Conseil d'Etat` (no accent).
- `8353/09 - Avis complémentaire du Conseil d'État (26.4.2024)` / `8577/07 - Avis complémentaire du Conseil d'État`
- `8353/04 - Avis de la Chambre de Commerce (20.3.2024)` / `8577/01 - Avis de chambre(s) professionnelle(s) : Chambre de Commerce` / `Avis d’une chambre professionnelle : Chambre des Métiers`
- `8577/02 - Avis : Syndicat des villes et communes luxembourgeoises` / `Avis du Syndicat des Villes et Communes Luxembourgeoises (22.5.2023)`
- `8577/05 - Amendement gouvernemental`
- `8535/13 - Amendement parlementaire : Commission du Logement et de l'Aménagement du territoire` / `8353/05 - Amendements adoptés par la/les commission(s) : Commission des Finances; Commission du Logement…`
- `8008/02 - Prise de position du Gouvernement (4.10.2024)`
- `Verbatim - Débat sur le dossier 8353 - Séance du 14.05.2024`
- Not in DB (label text on page): `8577/09 - Rapport de commission(s) : Commission de l'Environnement, du Climat et de la Biodiversité Rapporteur(s) : M. Paul Galles`; PV label is just the filename (`20261022_PV`); TexteVote / Bulletin labels are the vote outcome sentence (`8577 - Le Projet de loi est adopté par 54 voix contre 0 voix et 5 abstentions…`); `8481/10 - Dispense du second vote constitutionnel par le Conseil d'État`.

So: fetch-by-exact-title works only for dépôt/résumé. Other types need a `LIKE`/regex on title or (better) a type derived at scrape time from the URL suffix.

Why rapports/PVs/votes are missing: `find_doc_download_url` keeps only `<a class="chd-iconLinkBlock">` (the "Documents" block). Rapports, PVs, textes votés, bulletins and dispenses are rendered only in the activity timeline as `<a class="chd-link">`. 2 of 106 avis (8082/08, 8589/01) were also timeline-only on 2026-11-02.

Stale DB: `scrape_chd_lu_for_dossiers` skips any dossier already in the DB, so resource lists are frozen at first scrape. Live vs DB: 8577 10 vs 6 links, 8535 18 vs 14, 8534 8 vs 5. URLs also change on re-publication (8577/02: DB `…/8577/20251009_Avis.pdf`, live `…/8577/20260701_Avis.pdf`). Doc number (`8577/02`) is the stable key, not the URL.

Fetch gotchas: some URLs contain non-ASCII (`20250514_Depôt.pdf`) and must be percent-encoded; `wdocs-pub.chd.lu` certs fail Python 3.13+ strict X.509 verification ("Missing Authority Key Identifier"), which is why the scraper uses `verify=False`. Verbatim URLs end in `_pdf` (no extension).

## 3. Actor information

### Committee procès-verbaux: speakers, parties, group votes. Extractable, needs segmentation.

- Meeting-level, not dossier-level: one PV covers the whole agenda (PV LAT 08, 17.4.2024 covers 8357, 8358, 8359, 7856, 7642, …). It must be split on agenda headings (`2. 8357`). The same PV URL is linked from each dossier on the agenda.
- Attendance block: `Présents : Mme Barbara Agostino, M. Gilles Baum, …`, replacements (`M. Mars Di Bartolomeo remplaçant M. Yves Cruchten`), ministers, ministry officials, group staff (`Mme Julie Abt, du groupe parlementaire DP`), `Excusés :`, `Présidence :`.
- Speakers are named with their party in parentheses, in French reported speech:
  - `M. Marc Lies (CSV), tout en saluant l’importance du programme d’acquisition…` (PV 8357)
  - `Mme Paulette Lenert (LSAP) demande de plus amples informations sur les critères…`
  - `Mme Taina Bofferding (LSAP) rappelle que, dans sa prise de position du 28 février 2023…`
- Committee votes on the rapport, by group (PV 8116): `Les représentants des groupes parlementaires DP, LSAP, déi gréng ainsi que le représentant de la sensibilité politique Piraten votent en faveur du projet de rapport. Les représentants du groupe parlementaire CSV et de la sensibilité politique ADR s’abstiennent.` Often just `adopté à l’unanimité`.
- Link label carries no meaning (`20260218_PV`, upload date). Meeting date, commission and agenda come from the activity block (`23.09.2026 Présentation du projet de loi … Commission de l'Environnement… 20261022_PV`) or the URL path (`Reunions_de_la_Commission_de_l_Environnement…/Reunion_du_23-09-2026/`).

### Avis: body is structured, stance is formulaic. Extractable.

- Issuing body is in the title (see §2), although naming is inconsistent across eras (`Avis de la Chambre de Commerce` vs `Avis de chambre(s) professionnelle(s) : Chambre de Commerce`). It needs a normalisation map.
- Stance phrases recur per body:
  - Chambre de Commerce: `Après consultation de ses ressortissants, la Chambre de Commerce est en mesure d’approuver les trois projets de loi … sous réserve de la prise en compte de ses remarques.` (8359)
  - Chambre des Salariés: `En conclusion, notre Chambre ne peut approuver le projet dans son ensemble…` (8082 compl.)
  - Chambre des Métiers: `La Chambre des Métiers ne peut approuver le projet de loi lui soumis pour avis que sous la réserve…` (8086)
  - SYVICOL: `Le SYVICOL accueille favorablement…` / `il s’oppose fermement à ce que les conventions…` (8535)
  - Conseil d'État: `doit s’opposer formellement à l’article 8, point 5°` (8086); compl.: `le Conseil d’État est en mesure de lever son opposition formelle.` (8535)
- CE `opposition formelle` is a machine-detectable, legally meaningful signal (count per article, raised vs lifted across avis / avis compl.).

### Rapports de commission: rapporteur, composition, digest of every avis

- Title gives commission and rapporteur. Body opens with the full membership (`La Commission des Affaires intérieures se compose de : Mme Stéphanie WEYDERT, Présidente-Rapportrice ; M. Guy ARENDT, …`) and an `ANTECEDENTS` chronology of every avis and amendment with dates (8481).
- Sections per avis summarise each body's stance (8358 `VI. AVIS DE LA CHAMBRE DE COMMERCE`): `Dans son avis du 5 avril 2024, la Fédération des acteurs du secteur social Luxembourg (ci-après « FEDAS ») approuve la correction… De plus, la FEDAS salue la suppression du régime transitoire du calcul des loyers.` This is a compact, single-document source of actor stances.
- No party positions (consensual document).

### Bulletin de vote: fully structured per-deputy, per-party vote

8535 `BulletinPremierVote`: header `Oui Abst Non / 51 4 5`, then grouped by party: `ADR / Hardy Dan Non (Lemaire Michel) Keup Fred Non (Weidig Tom) …`, `CSV / Adehm Diane Oui …`. Proxies in parentheses. The best source for party positions on the final text, and trivially parseable.

### Verbatim plenary debate: speaker + party markers, in Luxembourgish

- Speaker turns are marked `M. Gilles Baum (DP), rapporteur | Merci, Här …`, `Mme Alexandra Schoos (ADR) | An och d’ADR huet …`, `M. David Wagner (déi Lénk) | …` (8357, 14.05.2024).
- Text is the original Luxembourgish, not French. The PDF is a page excerpt of the Compte rendu, so it includes neighbouring agenda items (the 8357 excerpt starts mid-motion on Gaza). Needs trimming to the dossier's debate.

## 4. Worth ingesting? (assessment)

- High value, low cost (native, short, regular): avis CE (+compl.), avis chambres/other bodies, rapport de commission, bulletin de vote.
- High value, needs work: PVs (segmentation by agenda item; meeting-level dedupe), verbatims (Luxembourgish; trimming).
- Low value for actor analysis: texte voté (law text), dispense second vote, corrigendum, résumé (.docx on older dossiers).
- Long: amendments (up to 112 pages, mostly coordinated text) and dépôt (up to 130 pages).

## Open points

- Sample is 20 dossiers (19 housing). Frequencies are indicative, not DB-wide for unscraped types.
- Scanned-PDF rate is ~1 of ~70 sampled. A full pass would need the whole inventory downloaded.
- Did not check the `/fr/meeting/<id>` pages (video + agenda), which might give PV-to-dossier mapping directly.
