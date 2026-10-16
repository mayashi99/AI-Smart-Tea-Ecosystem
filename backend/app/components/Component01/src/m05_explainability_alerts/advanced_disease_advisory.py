"""Step 50B — extended tea leaf advisory for the historical research prototype.

A *rules-based* educational/estate-scouting plan, NOT an AI-selected treatment,
verified plant diagnosis, severity estimator, chemical recommendation or prescription.

It reuses the unmodified Step 50 disease-advisory templates.  The input severity is
explicitly a qualitative *user-reported field assessment*, never calculated from
CNN confidence, Grad-CAM++, image area or arbitrarily selected incidence cutoffs.

Every plan requires qualified tea agronomist review before operational use.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from disease_advisory import available_advisory_classes, build_disease_advisory

ADVANCED_ADVISORY_VERSION = '50B.1.0'
FieldAssessment = Literal['not_assessed', 'officer_observation', 'agronomist_review_reported']
Severity = Literal['low', 'moderate', 'high']


class AdvancedAdvisoryRequest(BaseModel):
    """Field context provided by a human; never inferred from an uploaded photo."""

    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    disease_name: str = Field(..., min_length=1, max_length=80,
                              description='One of the five CNN classes; may also be selected manually')
    field_assessment: FieldAssessment = 'not_assessed'
    severity_level: Severity | None = Field(
        None, description='Human-assessed qualitative severity, NOT derived from image/CNN/percentages')
    block_id: str | None = Field(None, min_length=1, max_length=64,
                                 description='User-reported plantation block identifier')
    inspected_bushes: int | None = Field(None, ge=1, le=1_000_000)
    symptomatic_bushes: int | None = Field(None, ge=0, le=1_000_000)
    observation_notes: str | None = Field(None, max_length=500)

    @model_validator(mode='after')
    def check_context(self):
        if (self.inspected_bushes is None) != (self.symptomatic_bushes is None):
            raise ValueError('Provide both inspected_bushes and symptomatic_bushes, or neither')
        if (self.inspected_bushes is not None
                and self.symptomatic_bushes > self.inspected_bushes):
            raise ValueError('symptomatic_bushes cannot exceed inspected_bushes')
        if self.severity_level is not None and self.field_assessment == 'not_assessed':
            raise ValueError('Set field_assessment before entering a human-assessed severity_level')
        # Do not accept any remotely asserted severity for a CNN "healthy" result.
        # A conflict should be inspected, not treated as a validated disease label.
        if self.disease_name.lower().replace('_', ' ').replace('-', ' ').strip() == 'healthy' and self.severity_level is not None:
            raise ValueError('Healthy image label cannot carry a disease severity; request a field recheck')
        return self


# Case-specific *field-scouting* guidance, deliberately avoiding unverified
# chemical efficacy claims, doses, diagnostic certainty, and treatment thresholds.
_PER_CLASS = {
    'brown blight': {
        'field_differential': 'Confirm brown leaf lesions on multiple plants; distinguish from injury, other leaf spots and nutrient stress with an agronomist.',
        'management_actions': [
            'Mark affected bushes and document symptom appearance and distribution.',
            'Review estate-approved field hygiene and handling of symptomatic plant material.',
            'Have field staff assess wet-leaf duration, canopy ventilation and shade using local agronomic guidance.',
            'Recheck marked plants for new lesions before considering an intervention.',
        ],
        'expert_treatment_question': 'After field diagnosis, does current TRI tea guidance indicate any control intervention for this pattern and estate context?',
        'watch_for': ['new lesions on marked leaves', 'new symptomatic bushes nearby', 'rain or persistent leaf wetness'],
    },
    'grey leaf': {
        'field_differential': 'Check multiple leaves for grey or discoloured patches; distinguish possible leaf spots from scorch, nutrient problems and physical damage.',
        'management_actions': [
            'Record affected leaves, bushes and block locations with dated photos.',
            'Review sanitation and avoid carrying potentially symptomatic debris between blocks without estate guidance.',
            'Assess shade, airflow, drainage and recent weather together with field staff.',
            'Monitor identified bushes for change; seek diagnosis rather than using image colour alone.',
        ],
        'expert_treatment_question': 'What cause is confirmed in the field, and which current TRI-approved tea management protocol applies?',
        'watch_for': ['expansion of grey areas', 'new bushes showing symptoms', 'plant stress or poor drainage'],
    },
    'red rust': {
        'field_differential': 'Ask a specialist to confirm reddish-orange patches and distinguish red rust from other damage or stress.',
        'management_actions': [
            'Map affected bushes and note leaf age, shade and plant vigour.',
            'Review canopy and plant-health practices with the estate agronomist.',
            'Apply estate-approved hygiene and monitoring procedures only; do not use unverified home remedies.',
            'Compare follow-up photographs to see whether affected patches progress.',
        ],
        'expert_treatment_question': 'Has the causal organism been confirmed, and is a tea-specific treatment recommended under the current TRI protocol?',
        'watch_for': ['new reddish patches', 'poor vigour in affected bushes', 'change in distribution across the block'],
    },
    'red spider mite': {
        'field_differential': 'Use a hand lens to look for mites, eggs and mite injury; distinguish mite infestation from other causes of leaf bronzing.',
        'management_actions': [
            'Sample several bushes, especially around the observed patch, and record active mite/predator observations.',
            'Avoid unnecessary broad-spectrum pesticide use that could disrupt beneficial predatory organisms.',
            'Ask estate staff to assess plant stress and current scouting evidence using the TRI integrated pest management approach.',
            'Reinspect marked bushes; treatment decisions require pest confirmation and a locally applicable action threshold.',
        ],
        'expert_treatment_question': 'Are active mites confirmed, has a tea-specific action threshold been reached, and what registered approach is permitted?',
        'watch_for': ['active mites/eggs', 'leaf bronzing or damage progression', 'natural predator presence', 'new affected bushes'],
    },
    'healthy': {
        'field_differential': 'A healthy-looking photo cannot establish that a whole bush or plantation block is disease-free.',
        'management_actions': [
            'Continue routine estate scouting and retain records of observations.',
            'Inspect other leaves and nearby bushes if symptoms were reported elsewhere.',
            'Do not apply any pesticide solely because a model returned healthy.',
        ],
        'expert_treatment_question': 'Are there field symptoms that contradict this image screening result and require professional inspection?',
        'watch_for': ['new visible symptoms', 'contradictory field observations'],
    },
}


FOLLOW_UP = {
    None: {
        'priority': 'FIELD_CONFIRMATION_FIRST',
        'timing': 'Next estate scouting visit or sooner if visible symptoms are spreading; set exact interval locally.',
        'actions': ['Verify the suspected cause in person.', 'Mark representative bushes and take dated comparison photos.'],
    },
    'low': {
        'priority': 'ROUTINE_MONITORING',
        'timing': 'Next estate-approved inspection interval; timing must be set by local field staff.',
        'actions': ['Reinspect the same marked bushes.', 'Compare symptom distribution and record whether new bushes are affected.'],
    },
    'moderate': {
        'priority': 'PRIORITY_FIELD_REVIEW',
        'timing': 'Arrange a priority field follow-up; the exact date is determined by an estate agronomist.',
        'actions': ['Extend sampling to nearby bushes.', 'Compare with the previous observation and consult a field specialist.'],
    },
    'high': {
        'priority': 'PROMPT_EXPERT_ESCALATION',
        'timing': 'Request prompt estate agronomist review; no automatic spray instructions are issued.',
        'actions': ['Check the extent of symptoms in the block and adjacent areas.', 'Document progression and obtain expert diagnosis before treatment.'],
    },
}


def build_advanced_disease_advisory(
    disease_name: str, *, field_assessment: FieldAssessment = 'not_assessed',
    severity_level: Severity | None = None, block_id: str | None = None,
    inspected_bushes: int | None = None, symptomatic_bushes: int | None = None,
    observation_notes: str | None = None,
) -> dict:
    """Build an extended informational plan with validated user-entered context."""
    request = AdvancedAdvisoryRequest(
        disease_name=disease_name, field_assessment=field_assessment,
        severity_level=severity_level, block_id=block_id,
        inspected_bushes=inspected_bushes, symptomatic_bushes=symptomatic_bushes,
        observation_notes=observation_notes,
    )
    basic = build_disease_advisory(request.disease_name)
    class_name = basic['predicted_class']
    extra = deepcopy(_PER_CLASS[class_name])

    # User-entered incidence is displayed as an observation only. It is not a
    # diagnostic severity percentage and does not trigger pesticide decisions.
    incidence = (round(100 * request.symptomatic_bushes / request.inspected_bushes, 2)
                 if request.inspected_bushes is not None else None)
    level = request.severity_level
    plan = deepcopy(FOLLOW_UP[level])
    if class_name == 'healthy':
        plan = deepcopy(FOLLOW_UP[None])
        plan['priority'] = 'ROUTINE_SCOUTING_OR_FIELD_RECHECK'
        plan['actions'] = ['Continue routine scouting.', 'Seek expert review if field symptoms contradict the photo.']
    elif request.field_assessment == 'not_assessed':
        # Even if a caller tries another enum by bypassing Pydantic, force the
        # confirmation-first display for image-only paths.
        plan = deepcopy(FOLLOW_UP[None])

    mismatch = bool(class_name == 'healthy' and request.symptomatic_bushes is not None
                    and request.symptomatic_bushes > 0)
    chemical = deepcopy(basic['chemical_guidance'])
    chemical['automatic_treatment_authorized'] = False
    chemical['expert_review_required'] = class_name != 'healthy'
    chemical['decision_requirements'] = [
        'Confirm the causal pest/disease and whether any chemical control is justified.',
        'Use current TRI guidance and current Sri Lankan ROP tea-crop registered label information.',
        'Check label-approved target, rates, PHI/REI, residue limits, PPE and worker safety.',
        'Obtain and record the decision of a qualified tea agronomist before operational use.',
    ]

    return {
        'advanced_advisory_version': ADVANCED_ADVISORY_VERSION,
        'disease_name': class_name,
        'title': f'{basic["title"]} — Field Action Plan',
        'advisory_type': 'RULE_BASED_EDUCATIONAL_IPM_AND_FIELD_SCOUTING',
        'machine_diagnosis_verified': False,
        'agronomist_approval_verified_by_system': False,
        'field_validation_completed': False,
        'field_assessment_status': request.field_assessment,
        'field_assessment_is_user_reported': request.field_assessment != 'not_assessed',
        'field_context': {
            'block_id': request.block_id,
            'inspected_bushes': request.inspected_bushes,
            'symptomatic_bushes': request.symptomatic_bushes,
            'observed_incidence_percent': incidence,
            'observation_notes': request.observation_notes,
        },
        'severity_assessment': {
            'level': level,
            'source': 'USER_REPORTED_FIELD_ASSESSMENT' if level else 'NOT_ASSESSED',
            'auto_calculated': False,
            'clinical_or_agronomic_threshold_validated': False,
            'note': 'Severity is a user-provided field assessment, not CNN softmax, Grad-CAM++ or lesion-area estimation.',
        },
        'field_confirmation_steps': basic['immediate_checks'],
        'differential_check': extra['field_differential'],
        'management_actions': extra['management_actions'],
        'non_chemical_actions': basic['non_chemical_actions'],
        'chemical_control': chemical,
        'follow_up_plan': {
            **plan,
            'watch_for': extra['watch_for'],
            'record_fields': ['date', 'block_id', 'disease_name', 'inspected_bushes',
                              'symptomatic_bushes', 'photos', 'observed_changes'],
        },
        'expert_treatment_question': extra['expert_treatment_question'],
        'expert_escalation': basic['escalation'],
        'field_image_disagreement': mismatch,
        'field_image_disagreement_note': (
            'The photo screened healthy but symptomatic bushes were reported; request field diagnosis.'
            if mismatch else None
        ),
        'safety_warnings': basic['warnings'],
        'official_reference_urls': basic['official_reference_urls'],
        'expert_review_status': basic['expert_review_status'],
        'not_for_automatic_pesticide_use': True,
        'source_advisory_version': basic['advisory_version'],
    }


def supported_classes() -> list[str]:
    return available_advisory_classes()
