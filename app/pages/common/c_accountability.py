"""
Components shared by the minister and dossier pages (#119, demo of 2026-11-27): assessment
badges, vote tallies per party and the sources line. French only.
"""
import dash_mantine_components as dmc

from app.domain_model import LawAssessment
from app.domain_model import VoteChoice
from app.methodo.dossier_record import BallotRecord

_ASSESSMENT_COLOR = {LawAssessment.Delivers: 'green', LawAssessment.Partial: 'yellow',
                     LawAssessment.Unrelated: 'gray'}
_CHOICE_COLOR = {VoteChoice.Oui: 'green', VoteChoice.Non: 'red', VoteChoice.Abstention: 'yellow',
                 VoteChoice.PasParticipe: 'gray'}
_CHOICES = [VoteChoice.Oui, VoteChoice.Non, VoteChoice.Abstention, VoteChoice.PasParticipe]


def assessment_badge(assessment: LawAssessment | None) -> dmc.Badge:
    if assessment is None:
        return dmc.Badge('pas de verdict', color='gray', variant='outline')
    return dmc.Badge(assessment.value, color=_ASSESSMENT_COLOR[assessment], variant='light',
                     style={'overflow': 'visible'}, miw='fit-content')


def tally(ballot: BallotRecord) -> dmc.Group:
    """'Oui 51 · Non 5 · Abstention 4' as badges."""
    return dmc.Group([dmc.Badge(f'{choice.value} {ballot.counts[choice]}',
                                color=_CHOICE_COLOR[choice], variant='light')
                      for choice in _CHOICES if ballot.counts.get(choice)], gap=4)


def party_table(ballot: BallotRecord) -> dmc.Table:
    """Seats per party and choice."""
    head = dmc.TableThead(dmc.TableTr([dmc.TableTh('Parti')]
                                      + [dmc.TableTh(choice.value) for choice in _CHOICES]))
    body = dmc.TableTbody([
        dmc.TableTr([dmc.TableTd(group, fw=600)]
                    + [dmc.TableTd(counts.get(choice) or '–') for choice in _CHOICES])
        for group, counts in ballot.by_group.items()])
    return dmc.Table([head, body], striped=True, withTableBorder=True, fz=13)


def choice_text(choice: VoteChoice) -> dmc.Text:
    return dmc.Text(choice.value, c=_CHOICE_COLOR[choice], fw=600, fz=13, span=True)


def sources_line(*sources: str) -> dmc.Text:
    return dmc.Text('Sources : ' + ' · '.join(sources), fz=11, c='dimmed', mt='xs')
