# Legilux access and linking CHD dossiers to final laws

Research for [#85](https://github.com/AmaurySalles/luxdem/issues/85) (map [#83](https://github.com/AmaurySalles/luxdem/issues/83)). Checked 2026-11-02 against live endpoints.

**Answer.** Yes, use Legilux, and the link is free. Legilux's open SPARQL endpoint stores the CHD dossier number on every draft (`jolux:parliamentDraftId "7642"`, plus `jolux:parliamentDraftUrl https://www.chd.lu/fr/dossier/7642`). The same draft links to the resulting law (`jolux:hasResultingLegalResource`). One query maps every dossier to its law's ELI. Coverage is 100% of laws from 2009 to 2025, and the mapping is 1:1 since 2020. From the ELI you get the law as Akoma Ntoso XML, HTML, PDF/A and DOCX, all under CC BY 4.0, with no key and no rate limit seen. The operative text is the same as the CHD *texte voté*. Legilux adds the law's date (the CHD text has `xxx` placeholders), the enacting formula, the signatures, a `Doc. parl.` back-reference, links to every act it modifies, and consolidated versions. Only the Journal officiel version has legal force. **Recommendation:** ingest the Legilux original (`/jo`) XML as the "enacted" document. Keep the CHD texte voté as a fallback for dossiers that have been voted but not yet published (for example 8577). Leave consolidations out for now.

## The CHD number is on the Legilux draft, so linking takes one query

Legilux models each bill as a draft resource (`/eli/dl/pl/{year}/{n}`, alias `/eli/etat/projet/pl/{yyyynnnn}`). The draft carries `jolux:parliamentDraftId` (the CHD number as a string), `jolux:parliamentDraftUrl`, `jolux:conseilEtatDraftId` and `jolux:hasResultingLegalResource` → the law's `/jo` ELI ([draft for 8080](http://data.legilux.public.lu/eli/etat/projet/pl/20220111), fetched as Turtle). The law points back through `jolux:draft`. Its text also ends with `Doc. parl. <ref href="/eli/dl/pl/2020/234">7642</ref> ; sess. ord. …` ([a311 XML](https://legilux.public.lu/filestore/eli/etat/leg/loi/2024/07/23/a311/jo/fr/xml/eli-etat-leg-loi-2024-07-23-a311-jo-fr-xml.xml)).

```sparql
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
SELECT ?chd ?draft ?law ?date ?memorial ?title WHERE {
  ?draft jolux:parliamentDraftId ?chd .
  OPTIONAL { ?draft jolux:hasResultingLegalResource ?law .
             ?law jolux:dateDocument ?date ; jolux:isPartOf ?memorial ;
                  jolux:isRealizedBy/jolux:titleShort ?title . }
}
```

POST to `https://data.legilux.public.lu/sparqlendpoint` with `Accept: text/csv`. Every draft (4,071 rows) came back in under 1 s. 748 of them have no law yet. Dossier 8577 ("premier vote effectué") is already there with an empty `?law`, so the same query also tells you when a voted dossier gets published.

Coverage, measured by counting `LOI` acts per year that a draft with a `parliamentDraftId` points to:

| Years | Laws linked to a CHD number |
|---|---|
| ≤1999 | 0% |
| 2000–2008 | 24–92% |
| 2009–2025 | 100% (2017: 88/89) |
| 2026 (to date) | 102/103 |

Since 2020 no draft yields more than one law, and no law has more than one draft (two `GROUP BY … HAVING COUNT > 1` queries both returned nothing). The pipeline only scrapes dossiers numbered 8000 and up, which are all post-2020, so the link is complete and 1:1 for it.

**What CHD gives you.** The dossier page lists an activity, "Publié au Mémorial A n°NNN en page 1". For older dossiers it has no link ([8080](https://www.chd.lu/fr/dossier/8080), [8353](https://www.chd.lu/fr/dossier/8353), [7642](https://www.chd.lu/fr/dossier/7642)). Recent ones carry the ELI as an `<a href>` ([8535](https://www.chd.lu/fr/dossier/8535) → `https://legilux.public.lu/eli/etat/leg/loi/2026/09/07/a476/jo`). The Mémorial number alone is ambiguous: numbering restarts at 1 each year (Art. 3, [loi du 23 décembre 2016](https://legilux.public.lu/filestore/eli/etat/leg/loi/2016/12/23/n25/jo/fr/html/eli-etat-leg-loi-2016-12-23-n25-jo-fr-html.html)). The CHD activity date can also differ from the publication date by a day (8535: CHD 29.09.2026, Legilux `publicationDate` 2026-09-28). So use SPARQL, not the CHD text.

## Verified end to end on three housing dossiers

| CHD | Law (ELI) | Mémorial A | Pub. date | In force | CHD texte voté vs Legilux body |
|---|---|---|---|---|---|
| [7642](https://www.chd.lu/fr/dossier/7642) bail à usage d'habitation | [loi/2024/07/23/a311/jo](http://data.legilux.public.lu/eli/etat/leg/loi/2024/07/23/a311/jo) | 2024 n°311 | 2024-07-25 | 2024-08-01 | 98.4% of chars matched; diffs = 5 `xxx` date placeholders + headers/footers. One of the two CHD PDFs is a Xerox scan with **no text layer** |
| [8353](https://www.chd.lu/fr/dossier/8353) relance du marché du logement | [loi/2024/05/22/a219/jo](http://data.legilux.public.lu/eli/etat/leg/loi/2024/05/22/a219/jo) | 2024 n°219 | 2024-05-31 | 2024-01-01 (retroactive) | 97.7% matched; diffs = placeholders, headers, PDF reading order on formulas/tables |
| [8535](https://www.chd.lu/fr/dossier/8535) logement abordable + bail | [loi/2026/09/07/a476/jo](http://data.legilux.public.lu/eli/etat/leg/loi/2026/09/07/a476/jo) | 2026 n°476 | 2026-09-28 | 2026-10-02 | 99.5% matched; diffs = headers, "Chambre des Députés" stamps, formula order |

Method: the text of the Akoma Ntoso `<body>` compared with `pypdf` text from the CHD `TexteVote` PDF. Both were lower-cased, enumerators (`1°`) and all non-word characters were removed, then a character-level `difflib` diff was run. Every remaining difference was checked by hand. None was a change to wording. The CHD files: [7642 scan](https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/7642/20250801_TexteVote.pdf), [7642 Word](https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/7642/20250801_TexteVote_2.pdf), [8353](https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8353/20250515_TexteVote.pdf), [8535](https://wdocs-pub.chd.lu/docs/Dossiers_parlementaires/8535/20260715_TexteVote.pdf).

**Same operative text.** In all three dossiers the vote went through *dispense du second vote*. What was voted is what was promulgated.

**What Legilux adds over the texte voté:**
- **Dates filled in.** The CHD text says "l'entrée en vigueur de la loi du xxx". Legilux has "loi du 23 juillet 2024".
- **Enacting formula and visas.** "Nous Henri… Le Conseil d'État entendu; Vu l'adoption par la Chambre…; Vu la décision de la Chambre du 10 juillet 2024 et celle du Conseil d'État du 12 juillet 2024 portant qu'il n'y a pas lieu à second vote". Also the promulgation clause and the signatures (Grand-Duc, minister).
- **Clean, structured text.** Articles, paragraphs, lists and tables are in XML, so there is no OCR and no PDF reading-order problem. Cross-references are hyperlinked to ELIs.
- **Metadata.** `dateDocument`, `publicationDate`, `dateEntryInForce`, `inForceStatus`, `responsibilityOf` (ministry), `subjectLevel1/2` (thematic vocabulary), and `modifies` / `cites` / `repeals` edges to other acts.
- **Consolidated versions** of the laws it amends (below).
- **Legal force.** Only the published Journal officiel "fait seul foi et produit des effets juridiques" (Art. 5, loi du 23 décembre 2016).

The CHD texte voté has its own advantage. It exists from the day of the vote, weeks before publication (8535: vote 15.07, published 28.09). It is also signed off by the President and the Secretary-General of the Chamber.

## Access: SPARQL plus content negotiation plus filestore; no bulk dump

- **SPARQL**: `https://data.legilux.public.lu/sparqlendpoint` (documented alias `/sparql`). It returns CSV, HTML and RDF, and covers both the JOLux and ELI models. Drafts are in JOLux only ([data.public.lu dataset](https://data.public.lu/fr/datasets/legilux-journal-officiel-du-grand-duche-de-luxembourg-1/), "SPARQL API endpoint… freely interrogate the metadata"). Ontology prefix: `http://data.legilux.public.lu/resource/ontology/jolux#`.
- **ELI dereferencing**: `GET http://data.legilux.public.lu/eli/…/jo` with `Accept: text/turtle` or `application/rdf+xml` returns 303 to a `CONSTRUCT` over that resource's named graph. JSON and JSON-LD return 415. `legilux.public.lu/eli/…` is a JavaScript single-page app: a plain fetch gets a 2 KB "javascript required" shell. Requests with a spoofed browser User-Agent got a 403, while plain `curl` got a 200.
- **Files**: each manifestation's `jolux:isExemplifiedBy` gives `…/filestore/eli/etat/leg/loi/Y/M/D/aNNN/jo/fr/{xml,html,pdfa,docx}/eli-etat-leg-loi-Y-M-D-aNNN-jo-fr-{fmt}.{ext}`. These files are served on both `data.legilux.public.lu` and `legilux.public.lu`.
- **Bulk**: none. The only data.public.lu resources from the Service central de législation are the SPARQL endpoint and the technical-docs SPA (dataset above). There is a sitemap at `legilux.public.lu/sitemap-index.xml`.
- **Licence**: every manifestation carries `jolux:license <http://creativecommons.org/licenses/by/4.0/>` and the notice "Copyright : Ministère d'État – Service central de législation". The dataset licence is `cc-by`. Attribute SCL.
- **Rate limits**: none documented, and no rate-limit headers were returned. `robots.txt` on `data.legilux.public.lu` disallows `/eli/*` and `/filestore/*`. `legilux.public.lu/robots.txt` does not disallow `/filestore` and allows `/eli/etat/leg/`. So fetch files from `legilux.public.lu/filestore/…`, keep the volume small (a few hundred laws), and cache.

## Formats: Akoma Ntoso XML is the one to parse

| Format | Notes |
|---|---|
| XML | Akoma Ntoso in the pre-1.0 `http://docs.oasis-open.org/legaldocml/ns/akn/3.0/CSD13` namespace, plus an `scl:` extension (`<act contains="originalVersion">`). `<preface>/<longTitle>`, `<preamble>` (formula, visas), `<body>` (articles), `<conclusions>` (signatures), `<components>` (`Doc. parl.` ref). The FRBR fields are empty placeholders (`2999-01-01`). The real metadata is in `scl:JOLUX*` blocks and in the RDF. List numbers sit in `scl:symbol` attributes, not in the text. |
| HTML | Clean HTML, with hyperlinks to the ELIs of cited acts. |
| PDF/A | The official edition: `jolux:legalValue` = `definitif`, "édition émanant du gouvernement avec valeur légale" ([authority](http://data.legilux.public.lu/resource/authority/statut-version/definitif)). |
| DOCX | Also available. Disallowed in `legilux.public.lu/robots.txt`. |

## Original vs consolidated

- **Original** (`…/jo`): the amending law as published. This is what the dossier enacted, and it is the right document for "intent vs enacted" analysis.
- **Consolidated** (`…/{base-law}/consolide/YYYYMMDD`): the full text of the *amended* base law as it applies from a date. Each one has `dateApplicability`/`dateEndApplicability`, `inForceStatus`, and the same four formats (PDF instead of PDF/A). For the bail law `2006/09/21/n1` there are 9 consolidations. Two of them line up with our dossiers: `consolide/20240801` (the day 7642 entered into force) and `consolide/20261002` (8535). Find them with `?c jolux:isMemberOf <…/2006/09/21/n1>` and follow `?law jolux:modifies ?base` from the new law. Consolidations carry `legalValue` = `officiel`, "édition émanant du gouvernement", without legal force ([authority](http://data.legilux.public.lu/resource/authority/statut-version/officiel)). No property links a consolidation directly to the act that triggered it. Join on `dateEntryInForce` = `dateApplicability`. This is inferred from the two matches above.

## Recommendation

1. Linking: run one SPARQL query from `parliamentDraftId` to `hasResultingLegalResource`. Store `eli`, `memorial` (year and number), `dateDocument`, `publicationDate` and `dateEntryInForce` on the dossier. Re-run it to pick up newly published laws. Don't parse the CHD "Publié au Mémorial" text.
2. Enacted text: ingest `…/jo/fr/xml`. It is structured and has no OCR problems, so it can be chunked per article. Fall back to HTML if parsing the CSD13 namespace costs too much.
3. For a dossier that has been voted but not yet published, use the CHD `TexteVote` PDF. Some of these are scans with no text layer, so Docling OCR is needed, or pick the Word-born sibling when there are two. Mark the chunk `stage=texte_vote`, not `loi`.
4. Skip consolidated texts for now. They answer "what is the law today", not "what did this dossier enact".

## Unresolved

- Draft-related documents (avis, amendments) are modelled on Legilux, for example `…/pl/2020/234/evenement/avce/3/doc/davce/1` with title "60.326ac2 Deuxième avis complémentaire…". But their manifestations returned an empty graph, so file access through Legilux was not confirmed. Use CHD for those documents ([#84](https://github.com/AmaurySalles/luxdem/issues/84)/[#86](https://github.com/AmaurySalles/luxdem/issues/86)).
- The 2026 law with no CHD link was not identified.
- The SPARQL row cap was not measured. 4,071 rows came back uncapped.
