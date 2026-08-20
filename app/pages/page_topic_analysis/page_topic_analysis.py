"""
Topic analysis page -- real route backed by the live `topic_analysis_pipeline`.

Folds in the scorecard/dashboard layout picked as the winning design by issue #16
(variant C of the throwaway prototype on `worktree-prototype-topic-analysis-viz-docling`).
The user types a topic and triggers the pipeline live; there is no cache of past runs yet,
so every submit re-runs the full analysis (individual dossier/ONH summaries are still
DB-cached inside the pipeline itself, see `summarizer.py`). The pipeline runs for minutes,
so the submit callback only launches it (POST /api/analysis/topic, see app/routers/analysis.py)
and a dcc.Interval polls GET /api/analysis/topic/{run_id} until the backend background task
marks the run done or failed.
"""
from urllib.parse import urlparse

import dash_mantine_components as dmc
import requests
from dash import callback
from dash import dcc
from dash import Input
from dash import no_update
from dash import Output
from dash import State
from ecodev_core import logger_get
from ecodev_front import basic_layout
from ecodev_front import CHILDREN
from ecodev_front import HREF
from ecodev_front import Page
from ecodev_front import URL

from app.constants import FASTAPI_URL
from app.methodo.analyzer import TopicAnalysisResult
from app.methodo.reranker import RankedLaw
from app.methodo.reranker import RankedOnh
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
_RUN_STORE_ID = 'topic-analysis-run-store'
_POLL_INTERVAL_ID = 'topic-analysis-poll-interval'
_POLL_INTERVAL_MS = 3000


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


def _pending_placeholder(topic: str) -> dmc.Center:
    return dmc.Center(
        dmc.Stack([
            dmc.Loader(size='lg'),
            dmc.Text(f"Analyzing '{topic}' -- this can take a few minutes...", c='dimmed'),
        ], align='center'),
        h=200,
    )


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
    Renders the topic-input form; results are filled in by launch_topic_analysis/poll_topic_analysis below.
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
            dcc.Store(id=_RUN_STORE_ID, storage_type='session'),
            dcc.Interval(id=_POLL_INTERVAL_ID, interval=_POLL_INTERVAL_MS, disabled=True, n_intervals=0),
            dmc.Box(id=_RESULTS_ID),
        ], size='xl', py='lg'),
        main_footer(),
    ])


@callback(Output(_RESULTS_ID, CHILDREN),
          Output(_RUN_STORE_ID, 'data'),
          Output(_POLL_INTERVAL_ID, 'disabled'),
          Output(_POLL_INTERVAL_ID, 'n_intervals'),
          Input(_SUBMIT_ID, 'n_clicks'),
          State(_INPUT_ID, 'value'),
          prevent_initial_call=True)
def launch_topic_analysis(n_clicks: int, topic: str | None):
    """
    Launches the topic-analysis pipeline on the backend (POST /api/analysis/topic) and starts
    polling for its result; the pipeline itself runs out-of-request, see app/routers/analysis.py.
    """
    if not topic or not topic.strip():
        return dmc.Alert('Enter a topic to analyze.', color='yellow'), None, True, 0

    topic = topic.strip()
    try:
        response = requests.post(f'{FASTAPI_URL}/api/analysis/topic', json={'topic': topic}, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        log.exception(f"Failed to launch topic analysis for '{topic}'")
        return (dmc.Alert('Could not reach the analysis backend -- check it is running.',
                           color='red', title='Error'), None, True, 0)

    if not payload.get('success'):
        return (dmc.Alert(payload.get('error') or 'Failed to launch analysis.',
                           color='red', title='Error'), None, True, 0)

    return _pending_placeholder(topic), payload['run_id'], False, 0


@callback(Output(_RESULTS_ID, CHILDREN, allow_duplicate=True),
          Output(_POLL_INTERVAL_ID, 'disabled', allow_duplicate=True),
          Input(_POLL_INTERVAL_ID, 'n_intervals'),
          State(_RUN_STORE_ID, 'data'),
          prevent_initial_call=True)
def poll_topic_analysis(n_intervals: int, run_id: int | None):
    """
    Polls the backend for the launched run's status and renders the scorecard once done.
    """
    if not run_id:
        return no_update, no_update

    try:
        response = requests.get(f'{FASTAPI_URL}/api/analysis/topic/{run_id}', timeout=10)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        log.exception(f'Failed to poll topic analysis run {run_id}')
        return no_update, no_update

    status = payload['status']
    if status == 'done':
        return _scorecard(TopicAnalysisResult.model_validate(payload['result'])), True
    if status == 'failed':
        return (dmc.Alert(payload.get('error') or 'Analysis failed -- check backend logs.',
                           color='red', title='Error'), True)
    return no_update, no_update
