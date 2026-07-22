"""
PROTOTYPE -- throwaway page answering issue #16: how should a TopicAnalysisResult be
visualized in the frontend? Three structurally different variants, switchable via
?variant=A|B|C on this route. Renders a hardcoded fixture (see fixture.py), NOT live
pipeline output -- there is no data fetching here. Delete this whole directory once the
layout question is settled and the winner has been folded into a real page.

Run: docker compose up -d, then visit /prototype-topic-analysis?variant=A (or B / C).
"""
from urllib.parse import parse_qs
from urllib.parse import urlparse

import dash_mantine_components as dmc
from dash import callback
from dash import Input
from dash import Output
from ecodev_front import basic_layout
from ecodev_front import CHILDREN
from ecodev_front import HREF
from ecodev_front import Page
from ecodev_front import URL

from app.pages.common import display_app_header
from app.pages.common import main_footer
from app.pages.page_prototype_topic_analysis.fixture import TOPIC_ANALYSIS_FIXTURE

PAGE_PROTOTYPE_TOPIC_ANALYSIS = Page(
    module=__name__,
    name='prototype-topic-analysis',
    icon='iconoir:flask',
    title='PROTOTYPE -- Topic analysis visualization',
    description='',
    layout=basic_layout,
)

_VARIANTS = {
    'A': 'Evidence ledger (table-first)',
    'B': 'Narrative brief (prose-first)',
    'C': 'Scorecard (dashboard-first)',
}
_STATUS_COLOR = {'enacted': 'green', 'in progress': 'yellow', 'rejected': 'red'}


def _score_badge(score: float) -> dmc.Badge:
    color = 'green' if score >= 0.8 else 'yellow' if score >= 0.5 else 'gray'
    return dmc.Badge(f'{score:.2f}', color=color, variant='light')


def _variant_a(result: dict) -> dmc.Stack:
    """
    Table-first: commitments as a plain checklist, laws and ONH reports each as a dense
    table (status/score are the primary signal), analysis/gaps/conclusion pushed to the
    bottom as supporting text. Emphasizes the evidence over the LLM's prose judgment.
    """
    law_rows = [
        dmc.TableTr([
            dmc.TableTd(law['dossier_number']),
            dmc.TableTd(law['dossier_title']),
            dmc.TableTd(dmc.Badge(law['status'], color=_STATUS_COLOR.get(law['status'], 'gray'))),
            dmc.TableTd(_score_badge(law['relevance_score'])),
            dmc.TableTd(law['relevance_reasoning'], fz=12, c='dimmed'),
        ]) for law in result['matched_laws']
    ]
    onh_rows = [
        dmc.TableTr([
            dmc.TableTd(onh['title']),
            dmc.TableTd(onh['category']),
            dmc.TableTd(_score_badge(onh['relevance_score'])),
            dmc.TableTd(onh['summary'], fz=12, c='dimmed'),
        ]) for onh in result['matched_onh_reports']
    ]
    return dmc.Stack([
        dmc.Title(f"Topic: {result['topic']}", order=2),
        dmc.Title('Coalition commitments', order=4, mt='md'),
        dmc.List([dmc.ListItem(c) for c in result['coalition_commitments']]),
        dmc.Title('Matched laws', order=4, mt='md'),
        dmc.Table([
            dmc.TableThead(dmc.TableTr([dmc.TableTh(h) for h in
                                         ['Dossier', 'Title', 'Status', 'Score', 'Why']])),
            dmc.TableTbody(law_rows),
        ], striped=True, highlightOnHover=True),
        dmc.Title('Matched ONH reports', order=4, mt='md'),
        dmc.Table([
            dmc.TableThead(dmc.TableTr([dmc.TableTh(h) for h in
                                         ['Report', 'Category', 'Score', 'Summary']])),
            dmc.TableTbody(onh_rows),
        ], striped=True, highlightOnHover=True),
        dmc.Title('Analysis', order=4, mt='md'),
        dmc.Text(result['analysis_text'], fz=14),
        dmc.Title('Gaps identified', order=4, mt='md'),
        dmc.List([dmc.ListItem(g) for g in result['gaps_identified']], c='red'),
        dmc.Alert(result['conclusion'], title='Conclusion', color='blue', mt='md'),
    ], gap='xs')


def _variant_b(result: dict) -> dmc.Grid:
    """
    Prose-first: analysis_text reads as an article in the main column, conclusion as a
    lead call-out above it. Evidence (laws/ONH) demoted to a narrow citations sidebar.
    Emphasizes the LLM's judgment as the primary artifact, evidence as backup.
    """
    citations = [
        dmc.Text(f"[Law {law['dossier_number']}] {law['dossier_title']}", fz=12, fw=600)
        for law in result['matched_laws']
    ] + [
        dmc.Text(f"[ONH {onh['onh_id']}] {onh['title']}", fz=12, fw=600)
        for onh in result['matched_onh_reports']
    ]
    return dmc.Grid([
        dmc.GridCol([
            dmc.Title(f"Is Luxembourg delivering on: {result['topic']}?", order=2),
            dmc.Alert(result['conclusion'], color='blue', mt='sm', mb='lg'),
            dmc.Text(result['analysis_text'], fz=15, style={'lineHeight': 1.7}),
            dmc.Title('Gaps', order=5, mt='lg'),
            dmc.List([dmc.ListItem(g) for g in result['gaps_identified']]),
        ], span=8),
        dmc.GridCol([
            dmc.Title('Commitments', order=6),
            dmc.List([dmc.ListItem(c, fz=12) for c in result['coalition_commitments']], mb='md'),
            dmc.Title('Cited evidence', order=6),
            dmc.Stack(citations, gap=4),
        ], span=4, style={'borderLeft': '1px solid #e0e0e0', 'paddingLeft': '1rem'}),
    ])


def _variant_c(result: dict) -> dmc.Stack:
    """
    Dashboard-first: a big verdict card up top (conclusion, condensed to a headline judgment
    plus average relevance as a proxy "delivery score"), then commitments/laws/ONH reports
    as scrollable rows of compact cards rather than tables or prose. Most visual, least text.
    """
    laws = result['matched_laws']
    onh = result['matched_onh_reports']
    avg_score = sum(l['relevance_score'] for l in laws) / len(laws)
    verdict = 'Partially delivering' if 0.3 < avg_score < 0.85 else (
        'Delivering' if avg_score >= 0.85 else 'Not delivering')

    def law_card(law):
        return dmc.Card([
            dmc.Group([
                dmc.Badge(law['status'], color=_STATUS_COLOR.get(law['status'], 'gray'), size='sm'),
                _score_badge(law['relevance_score']),
            ], justify='space-between'),
            dmc.Text(law['dossier_title'], fw=600, fz=13, mt=6, lineClamp=2),
            dmc.Text(f"#{law['dossier_number']}", fz=11, c='dimmed'),
        ], withBorder=True, radius='md', p='sm', w=220)

    def onh_card(o):
        return dmc.Card([
            dmc.Group([dmc.Badge(o['category'], size='sm'), _score_badge(o['relevance_score'])],
                      justify='space-between'),
            dmc.Text(o['title'], fw=600, fz=13, mt=6, lineClamp=2),
        ], withBorder=True, radius='md', p='sm', w=220)

    return dmc.Stack([
        dmc.Card([
            dmc.Text(result['topic'].upper(), fz=12, c='dimmed'),
            dmc.Title(verdict, order=1, c='blue'),
            dmc.Progress(value=avg_score * 100, mt='sm', size='lg'),
            dmc.Text(result['conclusion'], mt='sm', fz=14),
        ], withBorder=True, radius='lg', p='lg', mb='md'),
        dmc.Title('Coalition commitments', order=5),
        dmc.Group([dmc.Badge(c, variant='outline', size='lg') for c in
                    result['coalition_commitments']], gap='xs', mb='md'),
        dmc.Title('Matched laws', order=5),
        dmc.ScrollArea(dmc.Group([law_card(l) for l in laws], gap='sm', wrap='nowrap'),
                        type='auto', mb='md'),
        dmc.Title('Matched ONH reports', order=5),
        dmc.ScrollArea(dmc.Group([onh_card(o) for o in onh], gap='sm', wrap='nowrap'), type='auto'),
        dmc.Title('Gaps', order=5, mt='md'),
        dmc.Group([dmc.Badge(g, color='red', variant='light') for g in
                    result['gaps_identified']], gap='xs'),
    ], gap='xs')


_RENDERERS = {'A': _variant_a, 'B': _variant_b, 'C': _variant_c}


def _switcher(current: str) -> dmc.Affix:
    """
    Fixed bottom-centre pill: prev/current/next, each a plain link that sets ?variant=.
    Full page reload on click -- fine for a throwaway prototype.
    """
    keys = list(_VARIANTS)
    idx = keys.index(current)
    prev_key = keys[idx - 1]
    next_key = keys[(idx + 1) % len(keys)]
    return dmc.Affix(
        dmc.Group([
            dmc.Anchor(dmc.Text('<', fw=700), href=f'?variant={prev_key}'),
            dmc.Text(f'{current} -- {_VARIANTS[current]}', fw=600, fz=13),
            dmc.Anchor(dmc.Text('>', fw=700), href=f'?variant={next_key}'),
        ], gap='md', p='8px 16px'),
        position={'bottom': 20, 'left': '50%'},
        style={'transform': 'translateX(-50%)', 'background': '#222', 'color': 'white',
               'borderRadius': '999px', 'boxShadow': '0 2px 10px rgba(0,0,0,0.3)', 'zIndex': 1000},
    )


@callback(Output(PAGE_PROTOTYPE_TOPIC_ANALYSIS.id, CHILDREN),
          Input(URL, HREF))
def render_prototype_page(href: str) -> dmc.Stack:
    """
    Renders whichever variant ?variant= asks for (default A) plus the switcher.
    """
    if not href or PAGE_PROTOTYPE_TOPIC_ANALYSIS.url not in urlparse(href).path:
        return []

    query = parse_qs(urlparse(href).query)
    variant = query.get('variant', ['A'])[0].upper()
    if variant not in _RENDERERS:
        variant = 'A'

    return dmc.Stack([
        display_app_header(),
        dmc.Container(_RENDERERS[variant](TOPIC_ANALYSIS_FIXTURE), size='xl', py='lg'),
        _switcher(variant),
        main_footer(),
    ])
