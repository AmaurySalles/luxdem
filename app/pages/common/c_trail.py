"""
Legislative trail chart (#119, demo of 2026-11-27): one row per bill, one bar segment per
phase between milestones, on a shared date axis. French only.

Phases are ordered, so they take an ordinal one-hue ramp (validated with the dataviz
validator, --ordinal); a phase still under way is hatched, so 'open' is never color alone.
"""
from dataclasses import dataclass

import plotly.graph_objects as go
from dash import dcc

from app.domain_model import TrailPhase
from app.methodo.legislative_trail import LegislativeTrail

_PHASE_COLOR = {TrailPhase.AwaitingCouncil: '#86b6ef', TrailPhase.InCommission: '#3987e5',
                TrailPhase.AwaitingVote: '#1c5cab', TrailPhase.AwaitingPublication: '#0d366b'}
_SURFACE = '#ffffff'
_MS_PER_DAY = 86_400_000
_ROW_PX = 40


@dataclass(frozen=True)
class TrailRow:
    label: str  # '8535'
    trail: LegislativeTrail


def trail_chart(rows: list[TrailRow]) -> dcc.Graph:
    """Bars of phase durations per bill; hover gives the phase, its dates and its length."""
    figure = go.Figure()
    for phase, color in _PHASE_COLOR.items():
        spans = [(row.label, span) for row in rows for span in row.trail.phases
                 if span.phase == phase]
        if not spans:
            continue
        figure.add_trace(go.Bar(
            name=phase.value, orientation='h',
            y=[label for label, _ in spans],
            base=[span.start.isoformat() for _, span in spans],
            x=[max(span.days, 1) * _MS_PER_DAY for _, span in spans],
            marker={'color': color, 'line': {'color': _SURFACE, 'width': 2},
                    'pattern': {'shape': ['/' if span.is_open else '' for _, span in spans],
                                'bgcolor': color, 'fgcolor': _SURFACE, 'solidity': 0.3},
                    'cornerradius': 4},
            text=[f'{span.days} j' for _, span in spans],
            textposition='inside', insidetextanchor='middle', textangle=0,
            textfont={'color': _SURFACE},
            customdata=[[span.start.strftime('%d.%m.%Y'),
                         "aujourd'hui (en cours)" if span.is_open
                         else span.end.strftime('%d.%m.%Y'), span.days] for _, span in spans],
            hovertemplate=(f'<b>%{{y}}</b> — {phase.value}<br>'
                           '%{customdata[0]} → %{customdata[1]}<br>'
                           '%{customdata[2]} jours<extra></extra>'),
        ))
    height_px = _ROW_PX * len(rows) + 120
    figure.update_layout(
        barmode='overlay', height=height_px,
        margin={'l': 10, 'r': 10, 't': 60, 'b': 30},
        plot_bgcolor=_SURFACE, paper_bgcolor=_SURFACE,
        legend={'orientation': 'h', 'y': 1.0, 'yanchor': 'bottom', 'x': 0,
                'title': {'text': 'Hachuré : phase en cours  '},
                'font': {'textcase': 'normal'}},
        uniformtext={'mode': 'hide', 'minsize': 10},
        xaxis={'type': 'date', 'showgrid': True, 'gridcolor': '#ececec', 'tickformat': '%m.%Y'},
        yaxis={'autorange': 'reversed', 'type': 'category'},
        bargap=0.35, hoverlabel={'bgcolor': _SURFACE},
    )
    return dcc.Graph(figure=figure, config={'displayModeBar': False},
                     style={'height': f'{height_px}px'})
