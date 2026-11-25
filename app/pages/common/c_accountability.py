"""
Components shared by the minister and dossier pages (#119, demo of 2026-11-27): assessment
badges, vote tallies per party and the sources line. French only.
"""
import dash_mantine_components as dmc

from app.domain_model import LawAssessment
from app.domain_model import OnhStance
from app.domain_model import VoteChoice
from app.methodo.dossier_record import BallotRecord

# Paths of the demo pages, here so pages can link to each other without importing each other
DOSSIER_PATH = '/dossier'
DEPUTY_PATH = '/depute'
MINISTER_PATH = '/ministre'
HOUSING_COMMISSION = 'Commission du Logement'


def dossier_url(number: str) -> str:
    return f'{DOSSIER_PATH}?numero={number}'


def deputy_url(deputy_id: int) -> str:
    return f'{DEPUTY_PATH}?id={deputy_id}'


def minister_url(name: str) -> str:
    return f'{MINISTER_PATH}?nom={name}'


_ASSESSMENT_COLOR = {LawAssessment.Delivers: 'green', LawAssessment.Partial: 'yellow',
                     LawAssessment.Unrelated: 'gray'}
_STANCE_COLOR = {OnhStance.Follows: 'green', OnhStance.Contradicts: 'red',
                 OnhStance.NotAddressed: 'gray'}
_CHOICE_COLOR = {VoteChoice.Oui: 'green', VoteChoice.Non: 'red', VoteChoice.Abstention: 'yellow',
                 VoteChoice.PasParticipe: 'gray'}
_CHOICES = [VoteChoice.Oui, VoteChoice.Non, VoteChoice.Abstention, VoteChoice.PasParticipe]


def assessment_badge(assessment: LawAssessment | None) -> dmc.Badge:
    if assessment is None:
        return dmc.Badge('pas de verdict', color='gray', variant='outline')
    return dmc.Badge(assessment.value, color=_ASSESSMENT_COLOR[assessment], variant='light',
                     styles={'root': {'maxWidth': 'none', 'overflow': 'visible'},
                             'label': {'overflow': 'visible', 'textOverflow': 'clip'}})


def stance_badge(stance: OnhStance | None) -> dmc.Badge:
    if stance is None:
        return dmc.Badge('non qualifié', color='gray', variant='outline', size='sm')
    return dmc.Badge(stance.value, color=_STANCE_COLOR[stance], variant='light', size='sm',
                     styles={'root': {'maxWidth': 'none', 'overflow': 'visible'},
                             'label': {'overflow': 'visible', 'textOverflow': 'clip'}})


def stance_counts(stances: list[OnhStance | None]) -> dmc.Group | dmc.Text:
    """'suit 2 · non traité 1' as badges; 'aucune étude liée' when the ONH leg is empty."""
    if not stances:
        return dmc.Text('aucune étude liée', fz=12, c='dimmed')
    counts = {stance: stances.count(stance) for stance in OnhStance if stance in stances}
    return dmc.Group([dmc.Badge(f'{stance.value} {n}', color=_STANCE_COLOR[stance],
                                variant='light', size='sm')
                      for stance, n in counts.items()], gap=4)


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
