"""
Minister page (#119, demo of 2026-11-27): a minister's functions and party, with sources, and
the laws they tabled in one policy area, each with its verdict and how each party voted.
French only.

The policy area is the examining commission (a chd.lu fact): housing laws are those the
Commission du Logement examined.
"""
from collections import defaultdict
from datetime import date
from urllib.parse import parse_qs
from urllib.parse import urlparse

import dash_mantine_components as dmc
from dash import callback
from dash import Input
from dash import Output
from ecodev_core import engine
from ecodev_front import basic_layout
from ecodev_front import CHILDREN
from ecodev_front import HREF
from ecodev_front import Page
from ecodev_front import URL
from sqlmodel import Session

from app.db_model.retrievers.government_retriever import retrieve_dossiers_by_author_and_commission
from app.domain_model import BallotKind
from app.domain_model import VoteChoice
from app.methodo.authors import author_profile
from app.methodo.authors import AuthorProfile
from app.methodo.dossier_record import BallotRecord
from app.methodo.dossier_record import dossier_record
from app.methodo.dossier_record import DossierRecord
from app.pages.common import display_app_header
from app.pages.common import main_footer
from app.pages.common.c_accountability import assessment_badge
from app.pages.common.c_accountability import dossier_url
from app.pages.common.c_accountability import HOUSING_COMMISSION
from app.pages.common.c_accountability import MINISTER_PATH
from app.pages.common.c_accountability import sources_line
from app.pages.common.c_accountability import tally
from app.pages.common.c_trail import trail_chart
from app.pages.common.c_trail import TrailRow

PAGE_MINISTRE = Page(
    module=__name__,
    name='ministre',
    icon='iconoir:user',
    title='Ministre',
    description="Les lois d'un ministre : verdicts et votes",
    layout=basic_layout,
)

NAME_PARAM = 'nom'
DEFAULT_MINISTER = 'Claude Meisch'
assert PAGE_MINISTRE.url == MINISTER_PATH


def _final_law_vote(record: DossierRecord) -> BallotRecord | None:
    """The last vote on the law itself, not on an amendment, motion or separate article."""
    votes = [b for b in record.ballots if b.kind == BallotKind.Dossier
             and 'séparé' not in b.label.lower()]
    return votes[-1] if votes else None


def _party_positions(ballot: BallotRecord) -> dmc.Text:
    """'Oui : CSV, DP · Non : ADR', each party under its majority choice."""
    parties: dict[VoteChoice, list[str]] = defaultdict(list)
    for group, counts in ballot.by_group.items():
        parties[max(counts, key=counts.get)].append(group)
    return dmc.Text(' · '.join(f'{choice.value} : {", ".join(groups)}'
                               for choice, groups in parties.items()), fz=12, c='dimmed')


def _law_row(record: DossierRecord) -> dmc.TableTr:
    vote = _final_law_vote(record)
    return dmc.TableTr([
        dmc.TableTd(dmc.Anchor(record.number, href=dossier_url(record.number), fw=600)),
        dmc.TableTd(dmc.Text(record.title, fz=13, lineClamp=2)),
        dmc.TableTd(f'{record.deposit_date:%d.%m.%Y}' if record.deposit_date else ''),
        dmc.TableTd(assessment_badge(record.verdict.assessment if record.verdict else None),
                    style={'whiteSpace': 'nowrap'}),
        dmc.TableTd(dmc.Stack([dmc.Text(f'{vote.held_at:%d.%m.%Y}', fz=12), tally(vote),
                               _party_positions(vote)], gap=2)
                    if vote else dmc.Text('pas encore voté', fz=12, c='dimmed')),
    ])


def _layout(profile: AuthorProfile, records: list[DossierRecord]) -> dmc.Stack:
    sources = [s for s in (profile.functions_source, profile.party_source) if s]
    head = dmc.TableThead(dmc.TableTr([dmc.TableTh(h) for h in (
        'N°', 'Projet', 'Dépôt', "Accord de coalition", 'Vote final à la Chambre')]))
    return dmc.Stack([
        dmc.Title(f'{profile.name} ({profile.party or "parti non renseigné"})', order=2),
        dmc.List([dmc.ListItem(f) for f in profile.functions]),
        sources_line(*sources) if sources else dmc.Box(),
        dmc.Title('Projets de loi sur le logement', order=4, mt='lg'),
        dmc.Text(f"Déposés par {profile.name} et examinés par la {HOUSING_COMMISSION} et de "
                 "l'Aménagement du territoire.", fz=13, c='dimmed'),
        dmc.Table([head, dmc.TableTbody([_law_row(r) for r in records])],
                  highlightOnHover=True, withTableBorder=True, verticalSpacing='sm'),
        dmc.Title('Parcours législatif', order=4, mt='lg'),
        dmc.Text("Du dépôt à l'avis du Conseil d'État, au rapport de commission, au vote et à "
                 'la publication au Mémorial. Survolez une barre pour les dates.',
                 fz=13, c='dimmed'),
        trail_chart([TrailRow(r.number, r.trail) for r in records]),
        sources_line('activités datées des dossiers sur chd.lu'),
    ], gap='xs')


@callback(Output(PAGE_MINISTRE.id, CHILDREN), Input(URL, HREF))
def render_minister_page(href: str) -> dmc.Stack | list:
    if not href or urlparse(href).path != PAGE_MINISTRE.url:
        return []
    name = parse_qs(urlparse(href).query).get(NAME_PARAM, [DEFAULT_MINISTER])[0]
    with Session(engine) as session:
        dossiers = retrieve_dossiers_by_author_and_commission(session, name, HOUSING_COMMISSION)
        content = (_layout(author_profile(session, name, date.today()),
                           [dossier_record(session, d) for d in dossiers])
                   if dossiers else dmc.Alert(f'Aucun projet de loi logement pour {name}.',
                                              color='yellow'))
    return dmc.Stack([display_app_header(),
                      dmc.Container(content, size='xl', py='lg'),
                      main_footer()])
