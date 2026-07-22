"""
PROTOTYPE FIXTURE -- throwaway data for the topic-analysis visualization prototype (issue #16).

Reconstructed from the narrative description of the "logement abordable" run captured in
issue #11 (no raw JSON was saved there) -- shape matches TopicAnalysisResult /
RankedLaw / RankedOnh in app/methodo/analyzer.py + reranker.py (feat/docling branch),
duplicated here as plain dicts so this prototype doesn't depend on that in-progress branch.
Not real pipeline output. Delete this whole directory once the layout question is settled.
"""

TOPIC_ANALYSIS_FIXTURE = {
    'topic': 'logement abordable',
    'coalition_commitments': [
        "Accroitre l'offre de logements abordables via le Pacte logement 2.0",
        'Encadrer les loyers pour limiter la hausse des prix locatifs',
        'Mobiliser le foncier public pour la construction de logements abordables',
        "Renforcer les aides a l'accession a la propriete pour les menages a revenus modestes",
        'Developper des dispositifs de type bail emphyteotique / rent-to-own',
        "Lutter contre la retention speculative de terrains constructibles",
    ],
    'matched_laws': [
        {
            'dossier_number': '8589',
            'dossier_title': 'Projet de loi portant modification du Pacte logement',
            'status': 'enacted',
            'summary': ('Revises the 2008 Pacte logement, tying municipal subsidies to '
                        'affordable-housing quotas in new developments and simplifying the '
                        'public land mobilization procedure.'),
            'relevance_score': 1.0,
            'relevance_reasoning': ('Direct implementation of the affordable-housing-supply and '
                                     'public-land-mobilization commitments; enacted, not proposed.'),
        },
        {
            'dossier_number': '8322',
            'dossier_title': "Projet de loi relative a l'encadrement des loyers",
            'status': 'in progress',
            'summary': ('Proposes a reference-rent-index cap on new leases in high-pressure '
                        'communes, with a landlord notification and appeal mechanism.'),
            'relevance_score': 0.9,
            'relevance_reasoning': 'Matches the rent-control commitment directly; still pending vote.',
        },
        {
            'dossier_number': '8410',
            'dossier_title': "Projet de loi relative a l'aide au logement",
            'status': 'enacted',
            'summary': ('Raises income thresholds and subsidy caps for the existing rental and '
                        'ownership assistance schemes.'),
            'relevance_score': 0.75,
            'relevance_reasoning': ('Supports the ownership-assistance commitment but is a '
                                     'parametric update, not a new instrument.'),
        },
        {
            'dossier_number': '8201',
            'dossier_title': 'Projet de loi sur la mobilisation des terrains constructibles',
            'status': 'rejected',
            'summary': ('Would have introduced a progressive tax on undeveloped buildable land '
                        'held beyond five years; withdrawn after committee opposition.'),
            'relevance_score': 0.6,
            'relevance_reasoning': ('Directly targeted land speculation but never enacted -- a '
                                     'failed attempt, not a delivered commitment.'),
        },
        {
            'dossier_number': '8556',
            'dossier_title': "Projet de loi portant reglement des comptes de l'exercice 2023",
            'status': 'enacted',
            'summary': 'Routine annual state budget settlement law; no housing-specific provisions.',
            'relevance_score': 0.2,
            'relevance_reasoning': ('Surfaced by semantic search on a shared budget-line reference '
                                     'only; not substantively about housing policy.'),
        },
    ],
    'matched_onh_reports': [
        {
            'onh_id': 38,
            'title': "Note 38 -- L'accessibilite financiere du logement au Luxembourg",
            'category': 'etude',
            'summary': ('Finds that 41% of the bottom income quartile spends over 40% of '
                        'disposable income on housing costs, above the recognised affordability '
                        'threshold, with the gap widest for renters under 35.'),
            'relevance_score': 0.95,
            'relevance_reasoning': ('Primary quantitative baseline for judging whether '
                                     'affordability commitments are being met.'),
        },
        {
            'onh_id': 24,
            'title': 'Note 24 -- Evolution des prix du logement 2015-2023',
            'category': 'etude',
            'summary': ('Tracks an 8-year house-price index rise of 62%, outpacing wage growth by '
                        'roughly 3x over the same period.'),
            'relevance_score': 0.8,
            'relevance_reasoning': ('Contextualizes the pressure the coalition commitments are '
                                     'meant to respond to, though not policy-specific.'),
        },
        {
            'onh_id': 31,
            'title': 'Observatoire -- Bilan annuel du logement locatif social 2023',
            'category': 'bilan',
            'summary': ('Reports 1,240 new social rental units delivered in 2023 against an '
                        'annual target of 2,000, a 62% delivery rate.'),
            'relevance_score': 0.7,
            'relevance_reasoning': ('Direct delivery-rate evidence against the housing-supply '
                                     'commitment.'),
        },
    ],
    'analysis_text': (
        "The government's response to affordable-housing commitments shows real but incomplete "
        'progress. The enacted Pacte logement revision (dossier 8589) operationalizes the '
        'supply and public-land-mobilization commitments, and ONH Note 38 confirms the scale of '
        'need it is meant to address: 41% of the poorest quartile already exceeds the recognised '
        'housing-cost-to-income threshold. Rent control (dossier 8322) remains in progress, so '
        'the price-stability commitment is not yet delivered, only proposed. The land-speculation '
        'tax (dossier 8201) was rejected in committee, leaving that lever unaddressed despite ONH '
        'Note 24 showing an 8-year price rise far outpacing wages. Delivery against the social '
        'rental supply target is running behind schedule (62% of the 2023 goal, per the ONH '
        'annual bilan). No enacted or proposed law yet establishes a rent-to-own or bail '
        'emphyteotique mechanism, despite it being an explicit coalition commitment.'
    ),
    'gaps_identified': [
        'Rent-to-own / bail emphyteotique framework has no corresponding law, enacted or proposed.',
        ('Land-speculation tax was rejected, leaving the buildable-land-hoarding commitment '
         'unaddressed.'),
        'Social rental delivery is running at 62% of its 2023 target per the ONH annual bilan.',
    ],
    'conclusion': (
        'Partially delivering: the government has enacted structural supply-side reform and is '
        'advancing rent control, but critical frameworks like rent-to-own and anti-speculation '
        'measures remain absent from enacted laws, and delivery against its own social-housing '
        'targets is behind schedule.'
    ),
}
