"""
Module implementing the main page
"""
import dash_mantine_components as dmc
from dash import callback
from dash import Input
from dash import Output
from ecodev_front import basic_layout
from ecodev_front import CHILDREN
from ecodev_front import FOOTER_ID
from ecodev_front import HEADER_ID
from ecodev_front import HREF
from ecodev_front import Page
from ecodev_front import PATHNAME
from ecodev_front import URL

from app.constants import MAIN_PAGE_URL
from app.pages.common import display_app_header
from app.pages.common import main_footer
from app.pages.common.c_accountability import dossier_url
from app.pages.common.c_accountability import minister_url
from app.pages.page_ministre.page_ministre import DEFAULT_MINISTER


PAGE_MAIN = Page(
    module=__name__,
    name='main',
    icon='raphael:home',
    title='Main Page',
    description='',
    layout=basic_layout,
)


_EXAMPLE_DOSSIER = '8535'


def _entry_card(title: str, text: str, href: str) -> dmc.Anchor:
    return dmc.Anchor(dmc.Card([dmc.Text(title, fw=600, fz=16),
                                dmc.Text(text, fz=13, c='dimmed', mt=4)],
                               withBorder=True, radius='md', p='lg', h='100%'),
                      href=href, underline='never')


@callback(Output(PAGE_MAIN.id, CHILDREN),
          Output(HEADER_ID, CHILDREN),
          Output(FOOTER_ID, CHILDREN),
          Input(URL, PATHNAME),
          Input(URL, HREF))
def get_main_page(url_pathname: str, href: str) -> tuple[list[dmc.Box], list[dmc.Box], list[dmc.Box]]:
    """
    Renders the main page.
    """
    if not url_pathname == MAIN_PAGE_URL:
        return [], [], []

    page = dmc.Container(dmc.Stack([
        dmc.Title('Qui a soutenu quoi ?', order=2),
        dmc.Text("LuxDem relie chaque projet de loi sur le logement à son auteur, à la "
                 "commission qui l'a examiné, au vote de chaque député(e) — procurations "
                 "comprises — et à un verdict sourcé sur les engagements de l'accord de "
                 "coalition 2023-2028.", fz=15),
        dmc.SimpleGrid([
            _entry_card(f'{DEFAULT_MINISTER}, ministre du Logement',
                        'Ses projets de loi, leurs verdicts, les votes par parti et le '
                        'parcours de chaque texte.', minister_url(DEFAULT_MINISTER)),
            _entry_card(f'Exemple : projet de loi n° {_EXAMPLE_DOSSIER}',
                        'Logements abordables : verdict cité, vote séparé sur l\'article 44, '
                        'chaque vote et chaque procuration.', dossier_url(_EXAMPLE_DOSSIER)),
        ], cols={'base': 1, 'sm': 2}, mt='md'),
        dmc.Text('Chaque nom de député(e) mène à ses votes sur le logement.', fz=13,
                 c='dimmed'),
        dmc.Text('Sources : chd.lu et ses données ouvertes (data.public.lu), gouvernement.lu, '
                 "accord de coalition 2023-2028. Verdicts générés par un modèle ouvert, "
                 'chaque phrase renvoyant aux passages cités.', fz=11, c='dimmed', mt='lg'),
    ], gap='sm'), size='md', py='xl')
    return page, display_app_header(), main_footer()
