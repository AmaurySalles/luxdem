# LuxDem

Tracks whether Luxembourg's government delivers on its coalition commitments, by analysing the laws it proposes and passes and who pushes them.

## Language

### Legislative process

**Dossier**:
One legislative file at the Chambre des Députés (a projet or proposition de loi), identified by its number (e.g. `8577`).
_Avoid_: Bill, law (for the file itself)

**Document de dépôt**:
The text as first filed in a Dossier; it shows intent.
_Avoid_: Draft, original bill

**Texte voté**:
The text the Chambre adopted; stands in for the law until it is published.
_Avoid_: Final text

**Law**:
The text as published by Legilux; the authority on what was enacted.
_Avoid_: Enacted bill

**Text stage**:
How far a Dossier's text got: published, voted or amended.
_Avoid_: Status (that is the CHD dossier status)

**Opposition formelle**:
A Conseil d'État objection that a provision is legally unacceptable; it blocks the dispense du second vote until lifted.
_Avoid_: Formal objection, CE veto

### Actors

**Actor**:
Anyone who authors, amends, advises on or votes on a Dossier: a Person, party, Government, ministry, Committee, the Conseil d'État, a professional chamber or another body.
_Avoid_: Stakeholder, participant

**Person**:
An Actor who is one human, independent of the Mandates they hold over time.
_Avoid_: Deputy, minister (as identities; those are Mandates)

**Mandate**:
A dated role a Person holds: deputy in a legislature, minister of a ministry, Committee member.
_Avoid_: Position (that is a Stance)

**Affiliation**:
A dated membership of one Actor in another: Person in party or Committee, ministry in Government. Mandates are Affiliations.
_Avoid_: Membership snapshot

**Government**:
One cabinet in office (e.g. Frieden–Bettel), with its coalition parties.
_Avoid_: Executive, the state

**Committee**:
A commission of the Chambre that examines a Dossier, adopts amendments and issues the rapport.
_Avoid_: Commission (ambiguous with the European Commission)

**Unresolved actor**:
An Actor created from a name that matched no known Actor; kept under its raw name until merged.

**Position**:
An Actor's Stance on a whole Dossier or one provision, backed by a source. The Conseil d'État has none; its role shows in Oppositions formelles and Triggers.
_Avoid_: Opinion, view

**Stance**:
The direction of a Position: for, against or reserved.
_Avoid_: Sentiment, vote (a vote is one source of a Stance)

**Fact row**:
One atomic fact taken from a single source document (a Position, Opposition formelle, amendment, vote or role), carrying its source and Evidence.
_Avoid_: Claim, extraction

**Evidence**:
The verbatim quote from the source document that backs a Fact row.
_Avoid_: Snippet, excerpt

**Dissent**:
A deputy voting against the majority of their own party on a Dossier.
_Avoid_: Rebellion, defection

### Analysis

**Dossier profile**:
The per-Dossier analysis: what changed from intent to enacted, what triggered each change, Positions, the vote, Oppositions formelles, author and rapporteur, built only from the Dossier's Fact rows.
_Avoid_: Law analysis, dossier summary

**Key change**:
A provision added, removed, weakened or strengthened between the Document de dépôt and the latest text.
_Avoid_: Diff, amendment (an amendment is one possible trigger)

**Trigger**:
The Actor and source document that caused a Key change.
_Avoid_: Cause, reason

**Topic verdict**:
The judgement, per topic, of whether coalition commitments are delivered, read from Dossier profiles, with only voted or published text counting as delivery.
_Avoid_: Topic analysis result, scorecard (that is the UI)

**Actor record**:
An Actor's Positions, Oppositions formelles, Triggers and votes across many Dossiers.
_Avoid_: Voting record, actor profile
