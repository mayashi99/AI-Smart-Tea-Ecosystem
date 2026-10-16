"""Step 50 — conservative, auditable tea leaf management advisory.

Rule-based guidance only. NOT a validated diagnosis or pesticide prescription.
The classification is taken from the existing five-class Step47 CNN.

Official general reference points (not evidence for every individual suggestion):
 - Tea Research Institute, Plant Pathology: https://www.tri.lk/plant-pathology/
 - Tea Research Institute, Entomology: https://www.tri.lk/entomology-and-nematology/
 - Tea Research Institute, IPM: https://www.tri.lk/major-research-areas/
 - Sri Lanka Registrar of Pesticides: https://doa.gov.lk/rop-home-3/

The per-class scouting suggestions are a research prototype and must be reviewed by
qualified tea agronomists before being used in operational estate instructions.
"""
from __future__ import annotations

from copy import deepcopy
import re

ADVISORY_VERSION = '50.1.0'

TRI_PATHOLOGY = 'https://www.tri.lk/plant-pathology/'
TRI_ENTOMOLOGY = 'https://www.tri.lk/entomology-and-nematology/'
TRI_IPM = 'https://www.tri.lk/major-research-areas/'
ROP = 'https://doa.gov.lk/rop-home-3/'
ROP_DOWNLOADS = 'https://doa.gov.lk/rop-downloads/'

GLOBAL_SAFETY = [
    'Image-based classification is a screening result, not a confirmed field diagnosis.',
    'Inspect plants and the surrounding block before taking any treatment action.',
    'Do not choose a pesticide, mixing rate or spray schedule based only on this CNN output.',
    'For any pesticide, obtain current TRI advice and confirm Sri Lankan registration, approved tea-crop label, target pest or disease, pre-harvest interval (PHI), restricted-entry interval (REI), residue rules and worker safety requirements.',
]

# These are deliberately high-level *scouting/management considerations*, not
# disease-specific chemical application protocols or unverified product lists.
_DATA = {
    'brown blight': {
        'title': 'Brown Blight — Management Advisory',
        'category': 'leaf_disease_pattern',
        'immediate_checks': [
            'Inspect multiple leaves and nearby bushes to confirm whether similar brown lesions occur.',
            'Record affected plant locations and recent leaf damage, heavy rainfall or prolonged leaf wetness.',
            'Ask a tea agronomist to differentiate brown blight from other leaf spots, injury or nutrient stress.',
        ],
        'non_chemical_actions': [
            'Follow local estate hygiene and pruning guidance; avoid moving potentially affected plant material between blocks.',
            'Review canopy ventilation, shade and wet-leaf conditions with field staff.',
            'Reinspect the same marked bushes to see whether lesions are increasing.',
        ],
        'chemical_category_to_review': 'Fungicide suitability only after field identification and TRI/ROP verification',
        'source_urls': [TRI_PATHOLOGY, TRI_IPM, ROP],
    },
    'grey leaf': {
        'title': 'Grey Leaf — Management Advisory',
        'category': 'leaf_disease_pattern',
        'immediate_checks': [
            'Look for grey or discoloured areas on several leaves and check for look-alike damage.',
            'Record whether affected leaves are scattered or concentrated in specific estate blocks.',
            'Request field confirmation before attributing the symptoms to a particular pathogen.',
        ],
        'non_chemical_actions': [
            'Review field sanitation practices and avoid unnecessary movement of symptomatic plant material.',
            'Check shade, drainage and air circulation as part of routine field assessment.',
            'Continue monitoring marked bushes and record any new symptoms.',
        ],
        'chemical_category_to_review': 'Fungicide suitability only after field identification and TRI/ROP verification',
        'source_urls': [TRI_PATHOLOGY, TRI_IPM, ROP],
    },
    'red rust': {
        'title': 'Red Rust — Management Advisory',
        'category': 'leaf_disease_pattern',
        'immediate_checks': [
            'Inspect leaf surfaces and nearby bushes for comparable reddish-orange patches.',
            'Have a qualified field specialist confirm the suspected red-rust symptoms and rule out other causes.',
            'Map affected bushes and note weather, shade and growth conditions.',
        ],
        'non_chemical_actions': [
            'Review canopy health and shade management with estate staff.',
            'Use estate-approved sanitation and plant-care procedures rather than unverified home remedies.',
            'Monitor whether affected patches expand over subsequent inspections.',
        ],
        'chemical_category_to_review': 'No chemical recommendation without verified causal diagnosis and current tea-specific TRI/ROP advice',
        'source_urls': [TRI_PATHOLOGY, TRI_IPM, ROP],
    },
    'red spider mite': {
        'title': 'Red Spider Mite — Integrated Pest Management',
        'category': 'mite_pest_pattern',
        'immediate_checks': [
            'Inspect upper and lower leaf surfaces using a hand lens for active mites or eggs.',
            'Sample several bushes to distinguish an isolated sighting from an active outbreak.',
            'Record the affected estate block and request expert identification before treatment.',
        ],
        'non_chemical_actions': [
            'Consider conservation of naturally occurring mite predators as part of integrated pest management.',
            'Avoid unnecessary broad-spectrum pesticide use that could disturb beneficial organisms.',
            'Monitor marked leaves and follow current Tea Research Institute IPM recommendations.',
        ],
        'chemical_category_to_review': 'Mite-control products only if a field specialist confirms the pest, action threshold and current tea-label approval',
        'source_urls': [TRI_ENTOMOLOGY, TRI_IPM, ROP],
    },
    'healthy': {
        'title': 'Healthy-Looking Leaf — Routine Monitoring',
        'category': 'no_detected_symptom_in_image',
        'immediate_checks': [
            'Continue routine inspection; a single photograph cannot establish whole-plant health.',
            'Check other leaves and neighbouring bushes when symptoms have been reported.',
        ],
        'non_chemical_actions': [
            'Continue normal plantation hygiene and monitoring practices.',
            'Record new symptoms and request field review if visible damage appears.',
            'Avoid pesticide applications on the basis of this healthy-looking image.',
        ],
        'chemical_category_to_review': 'No chemical treatment indicated by this image result',
        'source_urls': [TRI_IPM, ROP],
    },
}


def available_advisory_classes() -> list[str]:
    """Return classes in Step47 model order (do not change without class audit)."""
    return ['brown blight', 'grey leaf', 'healthy', 'red rust', 'red spider mite']


def build_disease_advisory(predicted_class: str) -> dict:
    """Return a safe recommendation template for a known *predicted* class.

    Raises ValueError for unknown classes. Never runs image inference or uses
    model confidence to recommend chemical treatment.
    """
    if not isinstance(predicted_class, str):
        raise ValueError('predicted_class must be a string')
    key = re.sub(r'\s+', ' ', predicted_class.replace('_', ' ').replace('-', ' ').strip()).lower()
    if key not in _DATA:
        raise ValueError('Unknown advisory class. Choose one of: ' + ', '.join(available_advisory_classes()))

    item = deepcopy(_DATA[key])
    chemical_status = 'NOT_INDICATED' if key == 'healthy' else 'EXPERT_AND_REGISTRATION_CHECK_REQUIRED'
    return {
        'advisory_version': ADVISORY_VERSION,
        'predicted_class': key,
        'title': item['title'],
        'category': item['category'],
        'advisory_type': 'GENERAL_IPM_INFORMATION_ONLY',
        'diagnosis_verified': False,
        'requires_field_confirmation': key != 'healthy',
        'immediate_checks': item['immediate_checks'],
        'non_chemical_actions': item['non_chemical_actions'],
        'chemical_guidance': {
            'status': chemical_status,
            'category_to_review': item['chemical_category_to_review'],
            'recommended_products': [],
            'active_ingredients': [],
            'dosage': None,
            'application_schedule': None,
            'approval_note': (
                'No pesticide recommended for a healthy-looking image.' if key == 'healthy'
                else 'A qualified tea agronomist must first confirm the problem and check current Sri Lankan tea-approved products and labels. No chemical or dose is auto-prescribed.'
            ),
            'official_checklist': [
                'Tea Research Institute current recommendation',
                'Office of Registrar of Pesticides current registered product and permitted tea-crop use',
                'Correct target organism and site, label rate and application instructions',
                'PHI, REI, tea residue/MRL and worker PPE/safety requirements',
            ],
            'registration_reference_url': ROP_DOWNLOADS,
        },
        'escalation': ('If symptoms spread quickly or field inspection disagrees with the image prediction, consult the Tea Research Institute or a qualified tea agronomist.'),
        'warnings': list(GLOBAL_SAFETY),
        'official_reference_urls': item['source_urls'],
        'expert_review_status': 'TEMPLATE_PENDING_ESTATE_AGRONOMIST_REVIEW',
        'field_validated': False,
    }
