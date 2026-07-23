"""
Topic analysis page -- real route backed by the live `topic_analysis_pipeline`.

Folds in the scorecard/dashboard layout picked as the winning design by issue #16
(variant C of the throwaway prototype on `worktree-prototype-topic-analysis-viz-docling`).
The user types a topic and triggers the pipeline live; there is no cache of past runs yet,
so every submit re-runs the full analysis (individual dossier/ONH summaries are still
DB-cached inside the pipeline itself, see `summarizer.py`). The pipeline call is synchronous
inside the callback -- it can take a few minutes (see issue #11) -- with `dcc.Loading` as the
only feedback; there is no background-job infra in this app yet to do better.
"""
from urllib.parse import urlparse

import dash_mantine_components as dmc
from dash import callback
from dash import dcc
from dash import Input
from dash import Output
from dash import State
from ecodev_core import engine
from ecodev_core import logger_get
from ecodev_front import basic_layout
from ecodev_front import CHILDREN
from ecodev_front import HREF
from ecodev_front import Page
from ecodev_front import URL
from sqlmodel import Session

from app.methodo.analyzer import TopicAnalysisResult
from app.methodo.reranker import RankedLaw
from app.methodo.reranker import RankedOnh
from app.methodo.topic_analysis_pipeline import topic_analysis_pipeline
from app.pages.common import display_app_header
from app.pages.common import main_footer

log = logger_get(__name__)

PAGE_TOPIC_ANALYSIS = Page(
    module=__name__,
    name='topic-analysis',
    icon='iconoir:search',
    title='Topic analysis',
    description='Is Luxembourg delivering on its housing-policy commitments?',
    layout=basic_layout,
)

_STATUS_COLOR = {'enacted': 'green', 'in progress': 'yellow', 'rejected': 'red'}

_INPUT_ID = 'topic-analysis-input'
_SUBMIT_ID = 'topic-analysis-submit'
_RESULTS_ID = 'topic-analysis-results'


def _score_badge(score: float) -> dmc.Badge:
    color = 'green' if score >= 0.8 else 'yellow' if score >= 0.5 else 'gray'
    return dmc.Badge(f'{score:.2f}', color=color, variant='light')


def _law_card(law: RankedLaw) -> dmc.Card:
    return dmc.Card([
        dmc.Group([
            dmc.Badge(law.status, color=_STATUS_COLOR.get(law.status, 'gray'), size='sm'),
            _score_badge(law.relevance_score),
        ], justify='space-between'),
        dmc.Text(law.dossier_title, fw=600, fz=13, mt=6, lineClamp=2),
        dmc.Text(f'#{law.dossier_number}', fz=11, c='dimmed'),
    ], withBorder=True, radius='md', p='sm', w=220)


def _onh_card(onh: RankedOnh) -> dmc.Card:
    return dmc.Card([
        dmc.Group([dmc.Badge(onh.category, size='sm'), _score_badge(onh.relevance_score)],
                  justify='space-between'),
        dmc.Text(onh.title, fw=600, fz=13, mt=6, lineClamp=2),
    ], withBorder=True, radius='md', p='sm', w=220)


def _scorecard(result: TopicAnalysisResult) -> dmc.Stack:
    """
    Dashboard-first rendering of a TopicAnalysisResult: a verdict card up top (conclusion,
    condensed to a headline judgment plus average relevance as a proxy "delivery score"), then
    commitments/laws/ONH reports as scrollable rows of compact cards.
    """
    laws = result.matched_laws
    onh = result.matched_onh_reports
    avg_score = sum(law.relevance_score for law in laws) / len(laws) if laws else 0.0
    verdict = ('Partially delivering' if 0.3 < avg_score < 0.85 else
               'Delivering' if avg_score >= 0.85 else 'Not delivering')

    return dmc.Stack([
        dmc.Card([
            dmc.Text(result.topic.upper(), fz=12, c='dimmed'),
            dmc.Title(verdict, order=1, c='blue'),
            dmc.Progress(value=avg_score * 100, mt='sm', size='lg'),
            dmc.Text(result.conclusion, mt='sm', fz=14),
        ], withBorder=True, radius='lg', p='lg', mb='md'),

        dmc.Title('Coalition commitments', order=5),
        dmc.Group([dmc.Badge(c, variant='outline', size='lg')
                   for c in result.coalition_commitments], gap='xs', mb='md')
        if result.coalition_commitments else dmc.Text('No matching commitments found.', c='dimmed'),

        dmc.Title('Matched laws', order=5),
        dmc.ScrollArea(dmc.Group([_law_card(law) for law in laws], gap='sm', wrap='nowrap'),
                        type='auto', mb='md')
        if laws else dmc.Text('No matching laws found.', c='dimmed', mb='md'),

        dmc.Title('Matched ONH reports', order=5),
        dmc.ScrollArea(dmc.Group([_onh_card(o) for o in onh], gap='sm', wrap='nowrap'),
                        type='auto')
        if onh else dmc.Text('No matching ONH reports found.', c='dimmed'),

        dmc.Title('Gaps', order=5, mt='md'),
        dmc.Group([dmc.Badge(g, color='red', variant='light') for g in
                    result.gaps_identified], gap='xs')
        if result.gaps_identified else dmc.Text('No gaps flagged.', c='dimmed'),
    ], gap='xs')


@callback(Output(PAGE_TOPIC_ANALYSIS.id, CHILDREN),
          Input(URL, HREF))
def render_topic_analysis_page(href: str) -> dmc.Stack:
    """
    Renders the topic-input form; results are filled in by run_topic_analysis below.
    """
    if not href or PAGE_TOPIC_ANALYSIS.url not in urlparse(href).path:
        return []

    return dmc.Stack([
        display_app_header(),
        dmc.Container([
            dmc.Title('Topic analysis', order=2, mb='md'),
            dmc.Group([
                dmc.TextInput(id=_INPUT_ID,
                              placeholder='e.g. logement abordable',
                              style={'flex': 1}),
                dmc.Button('Analyze', id=_SUBMIT_ID, n_clicks=0),
            ], align='end', mb='lg'),
            dcc.Loading(dmc.Box(id=_RESULTS_ID), type='dot'),
        ], size='xl', py='lg'),
        main_footer(),
    ])


@callback(Output(_RESULTS_ID, CHILDREN),
          Input(_SUBMIT_ID, 'n_clicks'),
          State(_INPUT_ID, 'value'),
          prevent_initial_call=True)
def run_topic_analysis(n_clicks: int, topic: str | None) -> dmc.Stack | dmc.Alert:
    """
    Runs the topic-analysis pipeline live against the given topic and renders the result.
    """
    if not topic or not topic.strip():
        return dmc.Alert('Enter a topic to analyze.', color='yellow')

    topic = topic.strip()
    try:
        with Session(engine) as session:
            result = topic_analysis_pipeline(topic=topic, session=session)
    except Exception:
        log.exception(f"Topic analysis failed for '{topic}'")
        return dmc.Alert('Analysis failed -- check backend logs.', color='red', title='Error')

    return _scorecard(result)
