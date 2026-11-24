"""
Deputy page (#119, demo of 2026-11-27): how one deputy voted on every housing law, whether
present or by proxy, and the proxies they cast for absent colleagues. French only.
"""
from collections import Counter
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

from app.methodo.deputy_record import deputy_record
from app.methodo.deputy_record import DeputyRecord
from app.methodo.deputy_record import DeputyVote
from app.methodo.deputy_record import UnknownDeputyError
from app.pages.common import display_app_header
from app.pages.common import main_footer
from app.pages.common.c_accountability import choice_text
from app.pages.common.c_accountability import DEPUTY_PATH
from app.pages.common.c_accountability import dossier_url
from app.pages.common.c_accountability import HOUSING_COMMISSION
from app.pages.common.c_accountability import sources_line

PAGE_DEPUTE = Page(
    module=__name__,
    name='depute',
    icon='iconoir:user-circle',
    title='Député(e)',
    description="Les votes d'un(e) député(e) sur le logement",
    layout=basic_layout,
)

ID_PARAM = 'id'
assert PAGE_DEPUTE.url == DEPUTY_PATH


def _how(vote: DeputyVote) -> str:
    if vote.cast_by:
        return f'absent(e), vote exprimé par procuration par {vote.cast_by}'
    if vote.cast_for:
        return f'procuration : vote exprimé pour {vote.cast_for}'
    if vote.owner_unknown:
        return 'siège de procuration non résolu'
    return ''


def _vote_row(vote: DeputyVote) -> dmc.TableTr:
    return dmc.TableTr([
        dmc.TableTd(f'{vote.held_at:%d.%m.%Y}'),
        dmc.TableTd(dmc.Group([dmc.Anchor(n, href=dossier_url(n), fw=600)
                               for n in vote.dossier_numbers], gap=4)),
        dmc.TableTd(dmc.Text(vote.label, fz=13)),
        dmc.TableTd(choice_text(vote.choice)),
        dmc.TableTd(dmc.Text(_how(vote), fz=12, c='dimmed')),
    ])


def _layout(record: DeputyRecord) -> dmc.Stack:
    own = [v for v in record.votes if not v.cast_for]
    counts = Counter(v.choice for v in own)
    by_proxy = sum(bool(v.cast_by) for v in own)
    head = dmc.TableThead(dmc.TableTr([dmc.TableTh(h) for h in (
        'Date', 'Dossier', 'Vote', 'Choix', 'Modalité')]))
    return dmc.Stack([
        dmc.Title(f'{record.name} ({", ".join(record.political_groups) or "groupe inconnu"})',
                  order=2),
        dmc.Text('Commissions : ' + ('; '.join(record.commissions) or 'aucune'), fz=13),
        dmc.Title('Votes sur les projets de loi logement', order=4, mt='lg'),
        dmc.Text(f'{len(own)} votes : '
                 + ' · '.join(f'{c.value} {n}' for c, n in counts.most_common())
                 + f' — dont {by_proxy} exprimés par procuration', fz=13),
        dmc.Text(f'Projets examinés par la {HOUSING_COMMISSION} et de l\'Aménagement du '
                 'territoire.', fz=12, c='dimmed'),
        dmc.Table([head, dmc.TableTbody([_vote_row(v) for v in record.votes])],
                  striped=True, withTableBorder=True, verticalSpacing='xs'),
        sources_line('CHD open data, jeux 104 et 109',
                     'bulletins de vote publiés sur chd.lu (procurations)'),
    ], gap='xs')


@callback(Output(PAGE_DEPUTE.id, CHILDREN), Input(URL, HREF))
def render_deputy_page(href: str) -> dmc.Stack | list:
    if not href or urlparse(href).path != PAGE_DEPUTE.url:
        return []
    raw_id = parse_qs(urlparse(href).query).get(ID_PARAM, [''])[0]
    with Session(engine) as session:
        try:
            content = _layout(deputy_record(session, int(raw_id), HOUSING_COMMISSION))
        except (ValueError, UnknownDeputyError):
            content = dmc.Alert(f'Député(e) {raw_id!r} introuvable.', color='red')
    return dmc.Stack([display_app_header(),
                      dmc.Container(content, size='xl', py='lg'),
                      main_footer()])
