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
Anyone who takes a Position on a Dossier: a deputy, party, ministry, the Conseil d'État or a professional chamber.
_Avoid_: Stakeholder, participant

**Position**:
An Actor's Stance on a whole Dossier or one provision, backed by a source.
_Avoid_: Opinion, view

**Stance**:
The direction of a Position: for, against or reserved.
_Avoid_: Sentiment, vote (a vote is one source of a Stance)

**Dissent**:
A deputy voting against the majority of their own party on a Dossier.
_Avoid_: Rebellion, defection

### Analysis

**Dossier profile**:
The per-Dossier analysis: what changed from intent to enacted, what triggered each change, Positions, the vote, Oppositions formelles, author and rapporteur.
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
An Actor's Positions across many Dossiers.
_Avoid_: Voting record, actor profile
