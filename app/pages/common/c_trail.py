"""
Legislative trail charts (#119, demo of 2026-11-27): one row per bill on a shared date axis,
one bar segment per period. French only.

- Phases between milestones are ordered: an ordinal one-hue ramp (dataviz validator, --ordinal).
- Who holds the bill is identity: categorical hues (validator: pass; aqua under 3:1 on the
  surface, so a days-per-holder table goes with the chart).
A period still under way is hatched, so 'open' is never color alone.
"""
from dataclasses import dataclass
from datetime import date
from enum import Enum

import dash_mantine_components as dmc
import plotly.graph_objects as go
from dash import dcc

from app.domain_model import BillHolder
from app.domain_model import TrailPhase
from app.methodo.legislative_trail import LegislativeTrail

PHASE_COLORS = {TrailPhase.AwaitingCouncil: '#86b6ef', TrailPhase.InCommission: '#3987e5',
                TrailPhase.AwaitingVote: '#1c5cab', TrailPhase.AwaitingPublication: '#0d366b'}
HOLDER_COLORS = {BillHolder.Council: '#2a78d6', BillHolder.Chamber: '#eb6834',
                 BillHolder.Government: '#1baf7a'}
_SURFACE = '#ffffff'
_MS_PER_DAY = 86_400_000
_ROW_PX = 40


@dataclass(frozen=True)
class Segment:
    row: str  # '8535'
    category: Enum  # a TrailPhase or a BillHolder
    start: date
    end: date
    is_open: bool

    @property
    def days(self) -> int:
        return (self.end - self.start).days


def phase_segments(row: str, trail: LegislativeTrail) -> list[Segment]:
    return [Segment(row, p.phase, p.start, p.end, p.is_open) for p in trail.phases]


def holder_segments(row: str, trail: LegislativeTrail) -> list[Segment]:
    return [Segment(row, h.holder, h.start, h.end, h.is_open) for h in trail.holders]


def timeline_chart(segments: list[Segment], colors: dict[Enum, str]) -> dcc.Graph:
    """Bars of periods per bill; hover gives the period, its dates and its length."""
    rows = list(dict.fromkeys(s.row for s in segments))
    figure = go.Figure()
    for category, color in colors.items():
        spans = [s for s in segments if s.category == category]
        if not spans:
            continue
        figure.add_trace(go.Bar(
            name=category.value, orientation='h',
            y=[s.row for s in spans], base=[s.start.isoformat() for s in spans],
            x=[max(s.days, 1) * _MS_PER_DAY for s in spans],
            marker={'color': color, 'line': {'color': _SURFACE, 'width': 2},
                    'pattern': {'shape': ['/' if s.is_open else '' for s in spans],
                                'bgcolor': color, 'fgcolor': _SURFACE, 'solidity': 0.3},
                    'cornerradius': 4},
            text=[f'{s.days} j' for s in spans], textposition='inside',
            insidetextanchor='middle', textangle=0, textfont={'color': _SURFACE},
            customdata=[[s.start.strftime('%d.%m.%Y'),
                         "aujourd'hui (en cours)" if s.is_open else s.end.strftime('%d.%m.%Y'),
                         s.days] for s in spans],
            hovertemplate=(f'<b>%{{y}}</b> — {category.value}<br>'
                           '%{customdata[0]} → %{customdata[1]}<br>'
                           '%{customdata[2]} jours<extra></extra>'),
        ))
    height_px = _ROW_PX * len(rows) + 120
    figure.update_layout(
        barmode='overlay', height=height_px, margin={'l': 10, 'r': 10, 't': 60, 'b': 30},
        plot_bgcolor=_SURFACE, paper_bgcolor=_SURFACE,
        legend={'orientation': 'h', 'y': 1.0, 'yanchor': 'bottom', 'x': 0,
                'title': {'text': 'Hachuré : en cours  '}, 'font': {'textcase': 'normal'}},
        uniformtext={'mode': 'hide', 'minsize': 10},
        xaxis={'type': 'date', 'showgrid': True, 'gridcolor': '#ececec', 'tickformat': '%m.%Y'},
        yaxis={'autorange': 'reversed', 'type': 'category'},
        bargap=0.35, hoverlabel={'bgcolor': _SURFACE},
    )
    return dcc.Graph(figure=figure, config={'displayModeBar': False},
                     style={'height': f'{height_px}px'})


def holder_days_table(segments: list[Segment]) -> dmc.Table:
    """Days per bill and holder: the chart's numbers as text."""
    rows = list(dict.fromkeys(s.row for s in segments))
    days = {(s.row, s.category): 0 for s in segments}
    for s in segments:
        days[(s.row, s.category)] += s.days
    head = dmc.TableThead(dmc.TableTr([dmc.TableTh('Dossier')]
                                      + [dmc.TableTh(h.value) for h in HOLDER_COLORS]))
    body = dmc.TableTbody([dmc.TableTr(
        [dmc.TableTd(row, fw=600)]
        + [dmc.TableTd(f'{days[(row, h)]} j' if (row, h) in days else '–') for h in HOLDER_COLORS])
        for row in rows])
    return dmc.Table([head, body], fz=12, striped=True, withTableBorder=True)
