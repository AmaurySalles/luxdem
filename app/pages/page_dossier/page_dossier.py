"""
Dossier page (#119, demo of 2026-11-27): who tabled the law, what it does, whether it delivers
on the coalition agreement (cited verdict), who examined it and how every deputy voted, proxies
named. French only.
"""
from urllib.parse import parse_qs
from urllib.parse import urlparse

import dash_mantine_components as dmc
from dash import callback
from dash import dcc
from dash import Input
from dash import Output
from ecodev_core import engine
from ecodev_front import basic_layout
from ecodev_front import CHILDREN
from ecodev_front import HREF
from ecodev_front import Page
from ecodev_front import URL
from sqlmodel import Session

from app.db_model.retrievers.chd_opendata_retriever import retrieve_latest_import
from app.db_model.retrievers.dossier_retriever import retrieve_dossiers_by_numbers
from app.methodo.chd_opendata import VOTES
from app.methodo.dossier_record import BallotRecord
from app.methodo.dossier_record import dossier_record
from app.methodo.dossier_record import DossierRecord
from app.methodo.evidence import find_citations
from app.pages.common import display_app_header
from app.pages.common import main_footer
from app.pages.common.c_accountability import assessment_badge
from app.pages.common.c_accountability import choice_text
from app.pages.common.c_accountability import deputy_url
from app.pages.common.c_accountability import DOSSIER_PATH
from app.pages.common.c_accountability import party_table
from app.pages.common.c_accountability import sources_line
from app.pages.common.c_accountability import tally
from app.methodo.legislative_trail import HOLDER_RULES
from app.pages.common.c_trail import HOLDER_COLORS
from app.pages.common.c_trail import holder_days_table
from app.pages.common.c_trail import holder_segments
from app.pages.common.c_trail import PHASE_COLORS
from app.pages.common.c_trail import phase_segments
from app.pages.common.c_trail import timeline_chart

PAGE_DOSSIER = Page(
    module=__name__,
    name='dossier',
    icon='iconoir:page',
    title='Dossier',
    description='Un projet de loi : contenu, verdict et votes',
    layout=basic_layout,
)

NUMBER_PARAM = 'numero'
assert PAGE_DOSSIER.url == DOSSIER_PATH


def _author_block(record: DossierRecord) -> dmc.Stack:
    author = record.author
    if author is None:
        return dmc.Stack([])
    party = author.party or 'parti non renseigné'
    functions = ' ; '.join(author.functions) if author.functions else 'député(e)'
    sources = [s for s in (author.functions_source, author.party_source) if s]
    return dmc.Stack([
        dmc.Text([dmc.Text('Auteur : ', fw=600, span=True), f'{author.name} ({party})']),
        dmc.Text(f'Au dépôt : {functions}', fz=13),
        sources_line(*sources) if sources else dmc.Box(),
    ], gap=2)


def _verdict_block(record: DossierRecord) -> dmc.Card:
    verdict = record.verdict
    if verdict is None:
        return dmc.Card(dmc.Text('Pas encore de verdict pour ce dossier.', c='dimmed'),
                        withBorder=True, radius='md', p='md')
    cited = {pid for text in [verdict.analysis_text, verdict.conclusion,
                              *verdict.coalition_commitments, *verdict.gaps_identified]
             for pid in find_citations(text)}
    passages = [p for p in verdict.passages if p.id in cited]
    return dmc.Card([
        dmc.Group([dmc.Title("Tient-il les engagements de l'accord de coalition ?", order=4),
                   assessment_badge(verdict.assessment)], justify='space-between'),
        dmc.Text(verdict.conclusion, mt='sm', fw=500),
        dmc.Title('Engagements concernés', order=6, mt='md'),
        dmc.List([dmc.ListItem(c, fz=13) for c in verdict.coalition_commitments]
                 or [dmc.ListItem('Aucun', fz=13)]),
        dmc.Title('Lacunes', order=6, mt='md'),
        dmc.List([dmc.ListItem(g, fz=13) for g in verdict.gaps_identified]
                 or [dmc.ListItem('Aucune relevée', fz=13)]),
        dmc.Accordion([
            dmc.AccordionItem([dmc.AccordionControl('Analyse détaillée'),
                               dmc.AccordionPanel(dcc.Markdown(verdict.analysis_text))],
                              value='analyse'),
            dmc.AccordionItem([
                dmc.AccordionControl(f'Passages cités ({len(passages)})'),
                dmc.AccordionPanel(dmc.Stack([
                    dmc.Blockquote(p.text[:1200], cite=p.id, fz=12) for p in passages]))],
                value='passages'),
        ], multiple=True, mt='md'),
        dmc.Text('Verdict généré par un modèle de langue ouvert (mistral-small3.2), à partir '
                 'des seuls passages cités ; chaque phrase renvoie à ses sources.',
                 fz=11, c='dimmed', mt='sm'),
    ], withBorder=True, radius='md', p='md')


def _ballot_block(ballot: BallotRecord) -> dmc.AccordionItem:
    seats = dmc.Table([
        dmc.TableThead(dmc.TableTr([dmc.TableTh(h) for h in ('Député(e)', 'Parti', 'Vote',
                                                             'Procuration')])),
        dmc.TableTbody([dmc.TableTr([
            dmc.TableTd(dmc.Anchor(seat.deputy, href=deputy_url(seat.deputy_id), fz=12)),
            dmc.TableTd(seat.political_group),
            dmc.TableTd(choice_text(seat.choice)),
            dmc.TableTd(f'votée par {seat.proxy_holder}' if seat.proxy_holder
                        else 'non résolue' if not seat.owner_known else ''),
        ]) for seat in ballot.seats]),
    ], fz=12, striped=True)
    unresolved = (dmc.Alert(f'{ballot.unresolved_proxies} sièges votés par procuration sans '
                            'bulletin lisible : leur titulaire reste inconnu.', color='yellow',
                            mt='xs')
                  if ballot.unresolved_proxies else dmc.Box())
    return dmc.AccordionItem([
        dmc.AccordionControl(dmc.Group([
            dmc.Text(f'{ballot.held_at:%d.%m.%Y} — {ballot.label}', fw=600, fz=14),
            tally(ballot)], justify='space-between', pr='md')),
        dmc.AccordionPanel([party_table(ballot), unresolved,
                            dmc.Title('Vote de chaque député(e)', order=6, mt='md'), seats]),
    ], value=f'{ballot.label}{ballot.held_at}')


def _trail_block(record: DossierRecord) -> dmc.Stack:
    trail = record.trail
    if not trail.phases:
        return dmc.Stack([dmc.Text('Parcours non disponible.', c='dimmed', fz=13)])
    milestones = dmc.Group([
        dmc.Stack([dmc.Text(step.value, fz=11, c='dimmed'),
                   dmc.Text(f'{day:%d.%m.%Y}', fw=600, fz=13)], gap=0)
        for step, day in trail.milestones.items()], gap='xl')
    steps = dmc.Table(dmc.TableTbody([dmc.TableTr([
        dmc.TableTd(f'{a.day:%d.%m.%Y}', style={'whiteSpace': 'nowrap'}),
        dmc.TableTd(a.description), dmc.TableTd(a.actor, c='dimmed')])
        for a in trail.activities]), fz=12, striped=True)
    return dmc.Stack([
        milestones,
        dmc.Text(f'{trail.total_days} jours depuis le dépôt'
                 + (' (en cours)' if trail.phases[-1].is_open else ''), fz=13),
        timeline_chart(phase_segments(record.number, trail), PHASE_COLORS),
        dmc.Title('Qui tient le projet ?', order=6, mt='sm'),
        timeline_chart(holders := holder_segments(record.number, trail), HOLDER_COLORS),
        holder_days_table(holders),
        dmc.Accordion([
            dmc.AccordionItem([dmc.AccordionControl(f'Toutes les étapes ({len(trail.activities)})'),
                               dmc.AccordionPanel(steps)], value='etapes'),
            dmc.AccordionItem([dmc.AccordionControl("Règles d'attribution"),
                               dmc.AccordionPanel(dmc.List([dmc.ListItem(rule, fz=12)
                                                            for rule in HOLDER_RULES]))],
                              value='regles'),
        ], multiple=True),
    ], gap='xs')


def _layout(record: DossierRecord, votes_source: str) -> dmc.Stack:
    return dmc.Stack([
        dmc.Anchor(f'Dossier parlementaire n° {record.number} sur chd.lu', href=record.chd_url,
                   target='_blank', fz=13),
        dmc.Title(record.title, order=3),
        dmc.Text(f'Déposé le {record.deposit_date:%d.%m.%Y}' if record.deposit_date else '',
                 c='dimmed', fz=13),
        _author_block(record),
        dmc.Text([dmc.Text('Commission : ', fw=600, span=True),
                  ' ; '.join(record.commissions) or 'non renseignée']),
        dmc.Text([dmc.Text('Rapporteur : ', fw=600, span=True),
                  ' ; '.join(record.rapporteurs) or 'pas encore désigné']),
        _verdict_block(record),
        dmc.Title('Parcours législatif', order=4, mt='md'),
        _trail_block(record),
        dmc.Title('Votes à la Chambre', order=4, mt='md'),
        dmc.Accordion([_ballot_block(b) for b in record.ballots], multiple=True,
                      variant='separated')
        if record.ballots else dmc.Text("Pas encore voté en séance plénière.", c='dimmed'),
        sources_line(votes_source, 'bulletins de vote publiés sur chd.lu (procurations)'),
        dmc.Accordion([dmc.AccordionItem([
            dmc.AccordionControl('Résumé du texte'),
            dmc.AccordionPanel(dcc.Markdown(record.summary or 'Pas de résumé.'))],
            value='resume')], mt='md'),
    ], gap='xs')


@callback(Output(PAGE_DOSSIER.id, CHILDREN), Input(URL, HREF))
def render_dossier_page(href: str) -> dmc.Stack | list:
    if not href or urlparse(href).path != PAGE_DOSSIER.url:
        return []
    number = parse_qs(urlparse(href).query).get(NUMBER_PARAM, [''])[0]
    with Session(engine) as session:
        dossiers = retrieve_dossiers_by_numbers(session, [number])
        if not dossiers:
            content = dmc.Alert(f'Dossier {number!r} introuvable.', color='red')
        else:
            imported = retrieve_latest_import(session, VOTES.number)
            votes_source = (f'CHD open data, jeu {VOTES.number}, importé le '
                            f'{imported.imported_at:%d.%m.%Y}' if imported
                            else f'CHD open data, jeu {VOTES.number}')
            content = _layout(dossier_record(session, dossiers[0]), votes_source)
    return dmc.Stack([display_app_header(),
                      dmc.Container(content, size='lg', py='lg'),
                      main_footer()])
