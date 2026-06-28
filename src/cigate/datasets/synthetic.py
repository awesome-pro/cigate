"""Deterministic synthetic dataset for CIGate.

This module builds — from a single fixed seed, with **no** wall-clock / unseeded
randomness — a realistic *contract & insurance policy support* benchmark:

1. ``goldensets/corpus/<doc_id>.md``       ~50 policy/contract clause documents
   (YAML frontmatter ``id``/``title`` then 3-4 short paragraphs of clause text
   with concrete numbers so questions have strong lexical overlap with their
   source doc — BM25 reliably retrieves the gold doc from the question keywords).

2. ``goldensets/synthetic_contract.yaml``  ~300 golden cases (the ``Case`` schema).
   Stratified across the five failure-mode axes; ~80% in-corpus, ~20% not.

3. ``goldensets/holdout_calibration.yaml`` ~200 calibration cases, each a FIXED
   (question, answer) pair with expert ``human_labels`` per axis. For every axis
   both classes (truly-passes / truly-fails) are well represented (>=40 each) so
   the judge's per-axis sensitivity/specificity is estimable.

Run ``python -m cigate.datasets.synthetic`` to regenerate everything; the tail of
``main()`` validates the output (schema round-trip, BM25 gold-hit-rate, balance).

--------------------------------------------------------------------------------
Answer-format contract assumed by the calibration ``human_labels`` (so the labels
are internally consistent with a plausible code-axis checker):

    <answer text, one or more lines>

    Sources: [doc-id-1], [doc-id-2]

* ``format_violation`` PASS  <=> a final line with the exact prefix ``Sources:``
  followed by one or more ``[doc-id]`` bracket tokens, and a non-empty answer.
  (A lowercase ``sources:`` header, a missing line, etc. -> FAIL.)
* ``citation_error``   PASS  <=> a ``[doc-id]`` token is present AND equals the
  gold doc id (wrong id / missing / malformed -> FAIL).
* ``retrieval_miss``   PASS  <=> the answer actually contains the needed grounded
  fact (a vague non-answer that omits it -> FAIL).
* ``hallucination``    PASS  <=> the answer asserts no claim absent from the gold
  doc (an invented benefit/number -> FAIL).
* ``refusal``          PASS  <=> answers an answerable (in-corpus) question, or
  abstains on an out-of-corpus one (wrong refusal / failure to abstain -> FAIL).
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..taxonomy import ALL_AXIS_KEYS
from ..types import Case

# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
SEED = 20240628
ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = ROOT / "goldensets" / "corpus"
GOLDEN_PATH = ROOT / "goldensets" / "synthetic_contract.yaml"
CALIB_PATH = ROOT / "goldensets" / "holdout_calibration.yaml"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenizer shared by the corpus index and queries."""
    return _TOKEN_RE.findall(text.lower())


def _order_axes(axes) -> list[str]:
    """Canonical (taxonomy) ordering for a set of axis keys."""
    s = set(axes)
    return [a for a in ALL_AXIS_KEYS if a in s]


# --------------------------------------------------------------------------- #
# Corpus specification
# --------------------------------------------------------------------------- #
# (product, aspect-slug, category, title-part, distinctive subject phrase)
DOC_SPECS: list[tuple[str, str, str, str, str]] = [
    # ---- auto ----
    ("auto", "collision-deductible", "deductible", "Collision Coverage Deductible", "collision coverage deductible"),
    ("auto", "comprehensive-deductible", "deductible", "Comprehensive Coverage Deductible", "comprehensive coverage deductible"),
    ("auto", "liability-limit", "liability", "Bodily Injury Liability Limits", "bodily injury liability limit"),
    ("auto", "premium", "premium", "Premium and Payment Schedule", "monthly premium payment"),
    ("auto", "claims-process", "claims", "Accident Claims Process", "accident claims process"),
    ("auto", "cancellation", "cancellation", "Policy Cancellation", "policy cancellation terms"),
    ("auto", "roadside-rider", "rider", "Roadside Assistance Rider", "roadside assistance rider"),
    ("auto", "exclusions", "exclusions", "Coverage Exclusions", "auto coverage exclusions"),
    ("auto", "renewal", "renewal", "Policy Renewal Terms", "policy renewal terms"),
    ("auto", "gap-rider", "rider", "Gap Insurance Rider", "gap insurance loan rider"),
    # ---- home ----
    ("home", "dwelling-coverage-limit", "limit", "Dwelling Coverage Limit", "dwelling coverage limit"),
    ("home", "deductible", "deductible", "All-Perils Deductible", "all-perils deductible"),
    ("home", "premium", "premium", "Premium and Payment Schedule", "monthly premium payment"),
    ("home", "exclusions", "exclusions", "Coverage Exclusions", "home coverage exclusions"),
    ("home", "claims-process", "claims", "Property Damage Claims Process", "property damage claims process"),
    ("home", "water-backup-rider", "rider", "Water Backup Rider", "water backup sewer rider"),
    ("home", "cancellation", "cancellation", "Policy Cancellation", "policy cancellation terms"),
    ("home", "replacement-cost", "limit", "Replacement Cost Coverage", "replacement cost coverage limit"),
    ("home", "scheduled-jewelry-rider", "rider", "Scheduled Jewelry Rider", "scheduled jewelry valuables rider"),
    # ---- health ----
    ("health", "deductible", "deductible", "Annual Deductible", "annual medical deductible"),
    ("health", "copay", "copay", "Office Visit Copay", "office visit copay"),
    ("health", "coverage-limit", "limit", "Annual Coverage Limit", "annual coverage limit"),
    ("health", "waiting-period", "waiting", "Pre-existing Condition Waiting Period", "pre-existing condition waiting period"),
    ("health", "exclusions", "exclusions", "Coverage Exclusions", "health coverage exclusions"),
    ("health", "premium", "premium", "Premium and Payment Schedule", "monthly premium payment"),
    ("health", "claims-process", "claims", "Medical Claims Reimbursement", "medical claims reimbursement process"),
    ("health", "prescription-rider", "rider", "Prescription Drug Rider", "prescription drug formulary rider"),
    ("health", "out-of-pocket-max", "oopmax", "Out-of-Pocket Maximum", "annual out-of-pocket maximum"),
    # ---- life ----
    ("life", "premium", "premium", "Premium and Payment Schedule", "monthly premium payment"),
    ("life", "grace-period", "grace", "Premium Grace Period", "premium grace period"),
    ("life", "coverage-limit", "limit", "Death Benefit Coverage Amount", "death benefit coverage amount"),
    ("life", "exclusions", "exclusions", "Coverage Exclusions", "life coverage exclusions"),
    ("life", "beneficiary", "claims", "Beneficiary Claim Process", "beneficiary death claim process"),
    ("life", "term-renewal", "renewal", "Term Renewal Conditions", "term renewal conditions"),
    ("life", "accidental-death-rider", "rider", "Accidental Death Benefit Rider", "accidental death benefit rider"),
    ("life", "cancellation", "cancellation", "Policy Cancellation and Surrender", "policy cancellation and surrender"),
    # ---- renters ----
    ("renters", "personal-property-limit", "limit", "Personal Property Coverage Limit", "personal property coverage limit"),
    ("renters", "liability-limit", "liability", "Personal Liability Limits", "personal liability limit"),
    ("renters", "deductible", "deductible", "Claims Deductible", "renters claims deductible"),
    ("renters", "premium", "premium", "Premium and Payment Schedule", "monthly premium payment"),
    ("renters", "exclusions", "exclusions", "Coverage Exclusions", "renters coverage exclusions"),
    ("renters", "claims-process", "claims", "Theft and Damage Claims Process", "theft and damage claims process"),
    ("renters", "cancellation", "cancellation", "Policy Cancellation", "policy cancellation terms"),
    # ---- travel ----
    ("travel", "trip-cancellation", "cancellation", "Trip Cancellation Coverage", "trip cancellation coverage"),
    ("travel", "medical-coverage-limit", "limit", "Emergency Medical Coverage Limit", "emergency medical coverage limit"),
    ("travel", "baggage-limit", "limit", "Baggage Loss Coverage Limit", "baggage loss coverage limit"),
    ("travel", "exclusions", "exclusions", "Coverage Exclusions", "travel coverage exclusions"),
    ("travel", "claims-process", "claims", "Travel Claims Process", "travel claims reimbursement process"),
    ("travel", "premium", "premium", "Premium and Payment Schedule", "trip premium cost"),
    ("travel", "waiting-period", "waiting", "Coverage Waiting Period", "coverage effective waiting period"),
]

EXCLUSIONS_BY_PRODUCT: dict[str, list[str]] = {
    "auto": ["racing or speed contests", "intentional damage", "normal wear and tear",
             "commercial ride-share use", "mechanical breakdown"],
    "home": ["flood and surface water", "earth movement and earthquake", "gradual mold",
             "neglect and lack of maintenance", "war and nuclear hazard"],
    "health": ["cosmetic procedures", "experimental treatments", "self-inflicted injury",
               "non-prescribed supplements", "elective overseas surgery"],
    "life": ["death by suicide within the first two years", "illegal-act fatalities",
             "undisclosed hazardous occupations", "act-of-war casualties", "material misrepresentation"],
    "renters": ["flood and surface water", "earthquake damage", "bed-bug infestation",
                "intentional acts", "business inventory loss"],
    "travel": ["pre-existing medical conditions", "extreme adventure sports",
               "travel against official advisories", "intoxication-related incidents", "lost cash"],
}


# --------------------------------------------------------------------------- #
# Fact + body + reference builders, keyed by category
# --------------------------------------------------------------------------- #
def _facts(category: str, rng: random.Random, product: str) -> dict[str, Any]:
    if category == "deductible":
        amt = rng.choice([250, 500, 750, 1000, 1500, 2000])
        return {"amount": amt, "aggregate": amt * rng.choice([3, 4, 5])}
    if category == "premium":
        m = rng.choice([29, 42, 58, 75, 96, 118, 145, 180])
        return {"monthly": m, "annual": m * 12, "late_fee": rng.choice([15, 25, 35]),
                "grace_days": rng.choice([10, 15, 30])}
    if category == "limit":
        lim = rng.choice([25_000, 50_000, 100_000, 250_000, 300_000, 500_000, 1_000_000])
        return {"limit": lim, "sublimit": int(lim * rng.choice([0.10, 0.20, 0.25]))}
    if category == "liability":
        pp = rng.choice([25_000, 50_000, 100_000])
        return {"per_person": pp, "per_accident": pp * rng.choice([2, 3]),
                "property": rng.choice([25_000, 50_000, 100_000])}
    if category == "copay":
        return {"copay": rng.choice([15, 25, 35, 50]), "coinsurance": rng.choice([10, 20, 30])}
    if category == "oopmax":
        return {"oop_max": rng.choice([3000, 5000, 7500, 9000]), "coinsurance": rng.choice([10, 20, 30])}
    if category == "grace":
        return {"grace_days": rng.choice([15, 30, 31, 60]), "reinstate_fee": rng.choice([25, 40, 50])}
    if category == "waiting":
        return {"waiting_days": rng.choice([30, 60, 90, 180])}
    if category == "claims":
        return {"file_days": rng.choice([30, 60, 90]), "settle_days": rng.choice([15, 30, 45])}
    if category == "cancellation":
        return {"notice_days": rng.choice([10, 20, 30]), "fee": rng.choice([25, 50])}
    if category == "renewal":
        return {"term": rng.choice([6, 12]), "rate_change": rng.choice([3, 5, 8]),
                "notice_days": rng.choice([30, 45])}
    if category == "rider":
        return {"rider_cost": rng.choice([5, 8, 12, 15]), "rider_limit": rng.choice([500, 1000, 2500, 5000])}
    if category == "exclusions":
        ex = EXCLUSIONS_BY_PRODUCT[product]
        return {"excl": ex[:3], "excl_all": ex}
    raise ValueError(f"unknown category {category!r}")


def _money(x: int) -> str:
    return f"${x:,}"


def _body(category: str, prod: str, subj: str, f: dict[str, Any]) -> str:
    """Return 3-4 short paragraphs that repeat the product + subject + numbers."""
    if category == "deductible":
        p = [
            f"This section of your {prod} insurance policy defines the {subj}. The {subj} "
            f"is the amount you pay out of pocket on a covered {prod} claim before your "
            f"coverage begins to pay.",
            f"Your {subj} is {_money(f['amount'])} per claim. You are responsible for the "
            f"first {_money(f['amount'])} of every covered {prod} loss, and the {subj} "
            f"applies separately to each incident.",
            f"An annual aggregate cap of {_money(f['aggregate'])} limits the total {subj} "
            f"you can pay across all {prod} claims in one policy year. Selecting a higher "
            f"{subj} lowers your premium; a lower {subj} raises it.",
        ]
    elif category == "premium":
        p = [
            f"This section explains the {subj} for your {prod} insurance policy, including "
            f"billing amounts, due dates, and late-payment handling.",
            f"Your {subj} is {_money(f['monthly'])} per month, or {_money(f['annual'])} "
            f"billed annually. Payment for your {prod} policy is due on the first of each "
            f"billing cycle.",
            f"A late fee of {_money(f['late_fee'])} applies if the {subj} is not received "
            f"within {f['grace_days']} days of the due date. Continued non-payment of the "
            f"{prod} premium may lead to lapse of coverage.",
        ]
    elif category == "limit":
        p = [
            f"This section sets the {subj} under your {prod} insurance policy — the maximum "
            f"amount payable for a covered {prod} loss.",
            f"Your {subj} is {_money(f['limit'])}. This is the most your {prod} policy will "
            f"pay for covered losses, after any applicable deductible.",
            f"A per-occurrence sub-limit of {_money(f['sublimit'])} applies to certain "
            f"categories within the {subj}. Amounts above the {subj} are your "
            f"responsibility unless a rider increases the {prod} coverage.",
        ]
    elif category == "liability":
        p = [
            f"This section describes the {subj} on your {prod} insurance policy, which "
            f"covers injuries and damage you are legally responsible for.",
            f"Your {subj} is {_money(f['per_person'])} per person and "
            f"{_money(f['per_accident'])} per accident for bodily injury, plus "
            f"{_money(f['property'])} for property damage under the {prod} policy.",
            f"Claims that exceed the {subj} are your personal responsibility. You may raise "
            f"the {subj} on your {prod} policy at renewal for an additional premium.",
        ]
    elif category == "copay":
        p = [
            f"This section explains the {subj} for your {prod} insurance plan and the "
            f"cost-sharing that applies to routine care.",
            f"Your {subj} is {_money(f['copay'])} per office visit. After you meet your "
            f"deductible, the {prod} plan pays covered charges subject to "
            f"{f['coinsurance']}% coinsurance.",
            f"The {subj} applies to in-network providers; out-of-network visits under the "
            f"{prod} plan may carry a higher {subj} and additional coinsurance.",
        ]
    elif category == "oopmax":
        p = [
            f"This section defines the {subj} for your {prod} insurance plan — the most you "
            f"pay in a year before the plan covers everything else.",
            f"Your {subj} is {_money(f['oop_max'])} per policy year. Once your covered "
            f"deductibles, copays, and {f['coinsurance']}% coinsurance reach the {subj}, "
            f"the {prod} plan pays 100% of further covered costs.",
            f"Premiums and non-covered services do not count toward the {subj}. The {subj} "
            f"resets at the start of each {prod} policy year.",
        ]
    elif category == "grace":
        p = [
            f"This section explains the {subj} for your {prod} insurance policy and how to "
            f"keep coverage active after a missed payment.",
            f"Your {subj} is {f['grace_days']} days from the premium due date. During the "
            f"{subj}, your {prod} coverage remains in force while you bring the account "
            f"current.",
            f"If payment is not made by the end of the {subj}, the {prod} policy lapses. "
            f"Reinstatement after the {subj} requires a {_money(f['reinstate_fee'])} fee "
            f"and may require new evidence of insurability.",
        ]
    elif category == "waiting":
        p = [
            f"This section describes the {subj} under your {prod} insurance policy — the "
            f"period before certain benefits become payable.",
            f"Your {subj} is {f['waiting_days']} days from the policy effective date. "
            f"Claims arising during the {subj} are not covered by the {prod} policy.",
            f"After the {subj} has elapsed, full {prod} benefits apply. The {subj} is "
            f"waived only where required by law or stated in your declarations.",
        ]
    elif category == "claims":
        p = [
            f"This section explains the {subj} for your {prod} insurance policy and the "
            f"documentation required to receive payment.",
            f"You must file a {prod} claim within {f['file_days']} days of the incident as "
            f"part of the {subj}. Provide a completed claim form, supporting receipts, and "
            f"any police or incident reports.",
            f"Once documentation is complete, the {subj} settles covered {prod} claims "
            f"within {f['settle_days']} days. Disputed amounts may be appealed in writing.",
        ]
    elif category == "cancellation":
        p = [
            f"This section explains the {subj} for your {prod} insurance policy, including "
            f"notice, refunds, and any fees.",
            f"To cancel, the {subj} require {f['notice_days']} days' written notice. A "
            f"{_money(f['fee'])} cancellation fee applies to your {prod} policy, and any "
            f"unearned premium is refunded on a pro-rata basis.",
            f"The insurer may also invoke the {subj} for non-payment or material "
            f"misrepresentation, with {f['notice_days']} days' notice on the {prod} policy.",
        ]
    elif category == "renewal":
        p = [
            f"This section describes the {subj} for your {prod} insurance policy and how "
            f"coverage continues at the end of each term.",
            f"Under the {subj}, your {prod} policy renews automatically for a {f['term']}-"
            f"month term. Any premium change at renewal is limited to {f['rate_change']}% "
            f"unless your risk profile changes.",
            f"You will receive {f['notice_days']} days' advance notice before the {subj} "
            f"take effect, giving you time to adjust or decline the {prod} renewal.",
        ]
    elif category == "rider":
        p = [
            f"This optional {subj} can be added to your {prod} insurance policy to extend "
            f"protection beyond the base coverage.",
            f"The {subj} costs {_money(f['rider_cost'])} per month and adds up to "
            f"{_money(f['rider_limit'])} of additional benefit to your {prod} policy.",
            f"The {subj} is subject to the same deductible and exclusions as the "
            f"underlying {prod} coverage unless your declarations state otherwise.",
        ]
    elif category == "exclusions":
        ex = f["excl_all"]
        p = [
            f"This section lists the {subj} — losses your {prod} insurance policy does not "
            f"cover.",
            f"The {subj} include {ex[0]}, {ex[1]}, {ex[2]}, {ex[3]}, and {ex[4]}. No "
            f"benefits are payable under the {prod} policy for losses caused by these "
            f"excluded perils.",
            f"Some of the {subj} can be bought back through an endorsement. Review your "
            f"{prod} declarations to confirm which {subj} apply to your coverage.",
        ]
    else:
        raise ValueError(f"unknown category {category!r}")
    return "\n\n".join(p)


def _reference(category: str, prod: str, subj: str, f: dict[str, Any]) -> str:
    if category == "deductible":
        return (f"Your {prod} policy's {subj} is {_money(f['amount'])} per claim, with an "
                f"annual aggregate cap of {_money(f['aggregate'])}.")
    if category == "premium":
        return (f"Your {prod} policy's {subj} is {_money(f['monthly'])} per month "
                f"({_money(f['annual'])} per year), with a {_money(f['late_fee'])} late fee "
                f"after the due date.")
    if category == "limit":
        return (f"Your {prod} policy's {subj} is {_money(f['limit'])}, with a "
                f"{_money(f['sublimit'])} per-occurrence sub-limit.")
    if category == "liability":
        return (f"Your {prod} policy's {subj} is {_money(f['per_person'])} per person and "
                f"{_money(f['per_accident'])} per accident, plus {_money(f['property'])} "
                f"for property damage.")
    if category == "copay":
        return (f"Your {prod} policy's {subj} is {_money(f['copay'])} per office visit, "
                f"followed by {f['coinsurance']}% coinsurance after the deductible.")
    if category == "oopmax":
        return (f"Your {prod} policy's {subj} is {_money(f['oop_max'])} per year; once you "
                f"reach it, the plan pays 100% of covered costs.")
    if category == "grace":
        return (f"Your {prod} policy's {subj} is {f['grace_days']} days, after which a "
                f"{_money(f['reinstate_fee'])} reinstatement fee applies.")
    if category == "waiting":
        return (f"Your {prod} policy's {subj} is {f['waiting_days']} days from the "
                f"effective date before benefits begin.")
    if category == "claims":
        return (f"Under your {prod} policy you must file a claim within {f['file_days']} "
                f"days, and covered claims settle within {f['settle_days']} days.")
    if category == "cancellation":
        return (f"Your {prod} policy's {subj} require {f['notice_days']} days' written "
                f"notice, with a {_money(f['fee'])} fee and a pro-rated premium refund.")
    if category == "renewal":
        return (f"Your {prod} policy's {subj}: it renews for a {f['term']}-month term with "
                f"up to a {f['rate_change']}% rate change and {f['notice_days']} days' "
                f"notice.")
    if category == "rider":
        return (f"The {subj} on your {prod} policy costs {_money(f['rider_cost'])} per "
                f"month and adds up to {_money(f['rider_limit'])} in additional benefit.")
    if category == "exclusions":
        e = f["excl"]
        return (f"Your {prod} policy's {subj} include {e[0]}, {e[1]}, and {e[2]}, which "
                f"are not covered.")
    raise ValueError(f"unknown category {category!r}")


# --------------------------------------------------------------------------- #
# Question phrasings (shared; {subj} + {prod} guarantee lexical overlap)
# --------------------------------------------------------------------------- #
PHRASINGS: list[str] = [
    "What is the {subj} for my {prod} insurance policy?",
    "How much is the {subj} under my {prod} policy?",
    "Can you explain the {subj} on my {prod} insurance?",
    "I need details about the {subj} for my {prod} coverage.",
    "What does my {prod} policy say about the {subj}?",
    "Could you tell me the {subj} in my {prod} insurance plan?",
]

FABRICATIONS: list[str] = [
    "In addition, a one-time $250 loyalty credit is automatically applied to every claim you file.",
    "Note that this coverage also includes unlimited free worldwide towing at no charge.",
    "You are also entitled to a guaranteed 15% cash-back rebate at the end of each policy year.",
    "This benefit additionally waives all future deductibles after your first claim.",
    "The policy further guarantees same-day payout by instant bank transfer on every claim.",
    "An extra $5,000 concierge allowance is included for each member of your household.",
]

# Out-of-corpus subjects (clearly NOT covered by any corpus doc), with apparent product.
OOC_SUBJECTS: list[tuple[str, str]] = [
    ("pet dental cleaning coverage", "health"),
    ("cyber identity-theft reimbursement", "home"),
    ("drone hobbyist liability coverage", "renters"),
    ("flood inundation damage rider", "home"),
    ("earthquake structural collapse rider", "home"),
    ("wedding event cancellation coverage", "travel"),
    ("cryptocurrency wallet theft reimbursement", "renters"),
    ("rideshare commercial-use coverage", "auto"),
    ("mold remediation allowance", "home"),
    ("professional malpractice liability coverage", "life"),
    ("classic-car agreed-value coverage", "auto"),
    ("surrogacy and fertility treatment coverage", "health"),
    ("kidnap-and-ransom evacuation coverage", "travel"),
    ("home-based business inventory coverage", "renters"),
    ("electric-vehicle battery replacement coverage", "auto"),
    ("pandemic trip-interruption coverage", "travel"),
    ("identity-restoration concierge service", "home"),
    ("dependent college tuition protection rider", "life"),
]

ABSTAIN_TEXT = ("I couldn't find this in the available policy documents, so I can't give a "
                "specific answer. Please check with your insurer for confirmation.")
REFUSAL_TEXT = "I'm sorry, but I'm not able to help with that request."


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class Doc:
    id: str
    title: str
    product: str
    aspect: str
    category: str
    subject: str
    body: str
    facts: dict[str, Any]
    reference: str
    questions: list[str] = field(default_factory=list)


def build_corpus(rng: random.Random) -> list[Doc]:
    docs: list[Doc] = []
    seen: set[str] = set()
    for product, aspect, category, title_part, subject in DOC_SPECS:
        doc_id = f"{product}-{aspect}-001"
        if doc_id in seen:
            raise ValueError(f"duplicate doc id {doc_id}")
        seen.add(doc_id)
        facts = _facts(category, rng, product)
        body = _body(category, product, subject, facts)
        reference = _reference(category, product, subject, facts)
        questions = [p.format(subj=subject, prod=product) for p in PHRASINGS]
        docs.append(Doc(
            id=doc_id,
            title=f"{product.capitalize()} Insurance — {title_part}",
            product=product,
            aspect=aspect,
            category=category,
            subject=subject,
            body=body,
            facts=facts,
            reference=reference,
            questions=questions,
        ))
    return docs


def write_corpus(docs: list[Doc]) -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    # Clean stale .md so re-runs are reproducible.
    for old in CORPUS_DIR.glob("*.md"):
        old.unlink()
    for d in docs:
        front = f"---\nid: {d.id}\ntitle: {d.title}\n---\n"
        (CORPUS_DIR / f"{d.id}.md").write_text(front + "\n" + d.body + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Golden set
# --------------------------------------------------------------------------- #
# In-corpus content-axis patterns (besides the always-on format_violation).
# Counts chosen so per-axis golden totals match the target stratification.
IC_PATTERN_COUNTS: list[tuple[tuple[str, ...], int]] = [
    (("citation_error",), 25),
    (("hallucination",), 20),
    (("retrieval_miss",), 15),
    (("hallucination", "citation_error"), 40),
    (("retrieval_miss", "citation_error"), 30),
    (("hallucination", "retrieval_miss"), 30),
    (("refusal", "citation_error"), 10),
    ((), 70),
]
OOC_PATTERN_COUNTS: list[tuple[tuple[str, ...], int]] = [
    (("refusal",), 30),
    (("hallucination", "refusal"), 30),
]


def _ooc_question_pool(rng: random.Random) -> list[dict[str, str]]:
    pool: list[dict[str, str]] = []
    for subj, prod in OOC_SUBJECTS:
        for phrasing in PHRASINGS:
            pool.append({"question": phrasing.format(subj=subj, prod=prod), "product": prod})
    rng.shuffle(pool)
    return pool


def build_golden(docs: list[Doc], rng: random.Random,
                 ooc_pool: list[dict[str, str]]) -> list[dict[str, Any]]:
    # All (doc, question-index) pairs; shuffle and take 240 for in-corpus cases.
    all_pairs = [(d, qi) for d in docs for qi in range(len(PHRASINGS))]
    rng.shuffle(all_pairs)
    ic_pairs = all_pairs[:240]

    ic_patterns: list[tuple[str, ...]] = []
    for pat, n in IC_PATTERN_COUNTS:
        ic_patterns += [pat] * n
    rng.shuffle(ic_patterns)
    assert len(ic_patterns) == len(ic_pairs) == 240

    ooc_patterns: list[tuple[str, ...]] = []
    for pat, n in OOC_PATTERN_COUNTS:
        ooc_patterns += [pat] * n
    rng.shuffle(ooc_patterns)
    ooc_questions = ooc_pool[:len(ooc_patterns)]  # 60
    assert len(ooc_patterns) == len(ooc_questions) == 60

    cases: list[dict[str, Any]] = []

    # In-corpus cases
    for (doc, qi), pat in zip(ic_pairs, ic_patterns):
        axes = _order_axes(set(pat) | {"format_violation"})
        cases.append({
            "question": doc.questions[qi],
            "axes": axes,
            "gold_doc_ids": [doc.id],
            "reference_answer": doc.reference,
            "in_corpus": True,
            "truth_labels": {a: True for a in axes},
            "metadata": {"product": doc.product, "aspect": doc.aspect},
        })

    # Out-of-corpus cases
    for q, pat in zip(ooc_questions, ooc_patterns):
        axes = _order_axes(set(pat) | {"refusal", "format_violation"})
        cases.append({
            "question": q["question"],
            "axes": axes,
            "gold_doc_ids": [],
            "reference_answer": ("This question is not addressed by the available policy "
                                 "documents; a correct answer should state that the "
                                 "information is not covered and avoid guessing."),
            "in_corpus": False,
            "truth_labels": {a: True for a in axes},
            "metadata": {"product": q["product"], "aspect": "out_of_corpus"},
        })

    rng.shuffle(cases)
    for i, c in enumerate(cases, start=1):
        c_with_id = {"id": f"q{i:04d}"}
        c_with_id.update(c)
        cases[i - 1] = c_with_id
    return cases


# --------------------------------------------------------------------------- #
# Calibration set
# --------------------------------------------------------------------------- #
# Each recipe -> (answer-builder, human_labels over all 5 axes, in_corpus, count).
# Labels order: hallucination, retrieval_miss, citation_error, refusal, format_violation.
def _sources_line(ids: list[str]) -> str:
    return "Sources: " + ", ".join(f"[{i}]" for i in ids)


def _calib_recipes() -> list[dict[str, Any]]:
    return [
        # ---- in-corpus recipes ----
        {"key": "perfect", "count": 26, "in_corpus": True,
         "labels": (True, True, True, True, True),
         "answer": lambda d, w, fab: f"{d.reference}\n\n{_sources_line([d.id])}"},
        {"key": "hallucinate", "count": 22, "in_corpus": True,
         "labels": (False, True, True, True, True),
         "answer": lambda d, w, fab: f"{d.reference} {fab}\n\n{_sources_line([d.id])}"},
        {"key": "wrong_cite", "count": 20, "in_corpus": True,
         "labels": (True, True, False, True, True),
         "answer": lambda d, w, fab: f"{d.reference}\n\n{_sources_line([w])}"},
        {"key": "no_sources", "count": 18, "in_corpus": True,
         "labels": (True, True, False, True, False),
         "answer": lambda d, w, fab: f"{d.reference}"},
        {"key": "vague_retrieval", "count": 20, "in_corpus": True,
         "labels": (True, False, True, True, True),
         "answer": lambda d, w, fab: (f"Your {d.product} policy does address the {d.subject}; "
                                      f"please review your policy documents for the specific "
                                      f"figures.\n\n{_sources_line([d.id])}")},
        {"key": "wrong_refusal", "count": 28, "in_corpus": True,
         "labels": (True, False, False, False, False),
         "answer": lambda d, w, fab: REFUSAL_TEXT},
        {"key": "bad_format", "count": 18, "in_corpus": True,
         "labels": (True, True, True, True, False),
         "answer": lambda d, w, fab: f"{d.reference}\n\nsources: [{d.id}]"},
        {"key": "halluc_badcite", "count": 16, "in_corpus": True,
         "labels": (False, True, False, True, True),
         "answer": lambda d, w, fab: f"{d.reference} {fab}\n\n{_sources_line([w])}"},
        # ---- out-of-corpus recipes ----
        {"key": "ooc_abstain", "count": 16, "in_corpus": False,
         "labels": (True, True, True, True, True),
         "answer": lambda d, w, fab: ABSTAIN_TEXT},
        {"key": "ooc_fabricate", "count": 16, "in_corpus": False,
         "labels": (False, False, False, False, True),
         "answer": lambda d, w, fab: (f"Yes, your {d['product']} policy includes this benefit, "
                                      f"with a $1,500 limit and a 30-day waiting period."
                                      f"\n\n{_sources_line([d['cite']])}")},
    ]


def build_calibration(docs: list[Doc], rng: random.Random,
                      ooc_pool: list[dict[str, str]]) -> list[dict[str, Any]]:
    n = len(docs)
    # Calibration in-corpus (doc, qi) pairs — independent shuffle from the golden set.
    all_pairs = [(d, qi) for d in docs for qi in range(len(PHRASINGS))]
    rng.shuffle(all_pairs)

    recipes = _calib_recipes()
    ic_total = sum(r["count"] for r in recipes if r["in_corpus"])
    ooc_total = sum(r["count"] for r in recipes if not r["in_corpus"])
    ic_pairs = all_pairs[:ic_total]
    # OOC questions for calibration come *after* the 60 used by the golden set.
    ooc_qs = ooc_pool[60:60 + ooc_total]
    assert len(ooc_qs) == ooc_total, "not enough out-of-corpus questions in the pool"

    items: list[dict[str, Any]] = []
    ic_i = 0
    ooc_i = 0
    fab_i = 0
    for r in recipes:
        for _ in range(r["count"]):
            labels = dict(zip(ALL_AXIS_KEYS, r["labels"]))
            if r["in_corpus"]:
                doc, qi = ic_pairs[ic_i]
                ic_i += 1
                wrong_id = docs[(docs.index(doc) + 7) % n].id
                if wrong_id == doc.id:
                    wrong_id = docs[(docs.index(doc) + 1) % n].id
                fab = FABRICATIONS[fab_i % len(FABRICATIONS)]
                fab_i += 1
                answer = r["answer"](doc, wrong_id, fab)
                items.append({
                    "question": doc.questions[qi],
                    "gold_doc_ids": [doc.id],
                    "in_corpus": True,
                    "answer": answer,
                    "human_labels": labels,
                })
            else:
                q = ooc_qs[ooc_i]
                ooc_i += 1
                # spurious citation for the fabricate recipe: any real corpus doc id
                spurious = docs[(ooc_i * 13) % n].id
                proxy = {"product": q["product"], "cite": spurious}
                answer = r["answer"](proxy, None, None)
                items.append({
                    "question": q["question"],
                    "gold_doc_ids": [],
                    "in_corpus": False,
                    "answer": answer,
                    "human_labels": labels,
                })

    rng.shuffle(items)
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items, start=1):
        rec = {"id": f"cal{i:04d}"}
        rec.update(it)
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# YAML emission
# --------------------------------------------------------------------------- #
def _dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=True,
                       default_flow_style=False, width=4096)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate(docs: list[Doc]) -> bool:
    from rank_bm25 import BM25Okapi  # imported here so generation has no hard dep

    ok = True
    print("\n" + "=" * 70)
    print("VALIDATION")
    print("=" * 70)

    # 1. Schema round-trip for the golden set.
    golden = yaml.safe_load(GOLDEN_PATH.read_text())["cases"]
    case_fields = {"id", "question", "axes", "gold_doc_ids", "reference_answer",
                   "in_corpus", "truth_labels", "metadata"}
    for c in golden:
        extra = set(c) - case_fields
        if extra:
            print(f"  [FAIL] golden case {c.get('id')} has extra keys: {extra}")
            ok = False
            break
        Case(**c)  # raises on schema mismatch
    print(f"  [OK] constructed {len(golden)} cigate.types.Case objects from the golden set")

    calib = yaml.safe_load(CALIB_PATH.read_text())["cases"]
    print(f"  [OK] loaded {len(calib)} calibration cases (plain dicts)")

    # 2. BM25 gold-hit-rate over in-corpus golden questions.
    corpus_files = sorted(CORPUS_DIR.glob("*.md"))
    ids: list[str] = []
    tokenized: list[list[str]] = []
    for fp in corpus_files:
        text = fp.read_text(encoding="utf-8")
        fm = re.search(r"^id:\s*(.+)$", text, re.MULTILINE)
        title = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
        body = text.split("---", 2)[-1]
        doc_id = fm.group(1).strip()
        title_txt = title.group(1).strip() if title else ""
        ids.append(doc_id)
        # weight the title by repeating it
        tokenized.append(tokenize(title_txt + " " + title_txt + " " + body))
    bm25 = BM25Okapi(tokenized)
    id_to_idx = {d: i for i, d in enumerate(ids)}

    ic_cases = [c for c in golden if c["in_corpus"] and c["gold_doc_ids"]]
    hits = 0
    for c in ic_cases:
        scores = bm25.get_scores(tokenize(c["question"]))
        top3 = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:3]
        gold_idx = id_to_idx[c["gold_doc_ids"][0]]
        if gold_idx in top3:
            hits += 1
    rate = hits / len(ic_cases) if ic_cases else 0.0
    status = "OK" if rate >= 0.85 else "FAIL"
    if rate < 0.85:
        ok = False
    print(f"  [{status}] BM25 gold-doc top-3 hit-rate: {rate:.3f} "
          f"({hits}/{len(ic_cases)} in-corpus golden questions; threshold 0.85)")

    # 3. Counts + per-axis stratification.
    print("\n" + "-" * 70)
    print("COUNTS")
    print("-" * 70)
    print(f"  corpus documents       : {len(corpus_files)}")
    print(f"  golden cases           : {len(golden)}")
    print(f"  golden out-of-corpus   : {sum(1 for c in golden if not c['in_corpus'])}")
    print(f"  golden in-corpus       : {sum(1 for c in golden if c['in_corpus'])}")
    print("  golden per-axis exercised counts:")
    for ax in ALL_AXIS_KEYS:
        n = sum(1 for c in golden if ax in c["axes"])
        print(f"      {ax:<18}: {n:>4}  ({n / len(golden):.0%})")

    print(f"\n  calibration cases      : {len(calib)}")
    print(f"  calibration OOC        : {sum(1 for c in calib if not c['in_corpus'])}")
    print("  calibration per-axis class balance (PASS / FAIL):")
    for ax in ALL_AXIS_KEYS:
        passes = sum(1 for c in calib if c["human_labels"][ax])
        fails = len(calib) - passes
        bal_ok = passes >= 40 and fails >= 40
        flag = "OK" if bal_ok else "FAIL"
        if not bal_ok:
            ok = False
        print(f"      {ax:<18}: {passes:>4} / {fails:<4}  [{flag}]")

    print("\n" + "=" * 70)
    print("RESULT:", "ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
    print("=" * 70)
    return ok


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> None:
    rng = random.Random(SEED)
    docs = build_corpus(rng)
    write_corpus(docs)
    print(f"wrote {len(docs)} corpus docs -> {CORPUS_DIR}")

    ooc_pool = _ooc_question_pool(rng)

    golden = build_golden(docs, rng, ooc_pool)
    _dump_yaml(GOLDEN_PATH, {"cases": golden})
    print(f"wrote {len(golden)} golden cases -> {GOLDEN_PATH}")

    calib = build_calibration(docs, rng, ooc_pool)
    _dump_yaml(CALIB_PATH, {"cases": calib})
    print(f"wrote {len(calib)} calibration cases -> {CALIB_PATH}")

    validate(docs)


if __name__ == "__main__":
    main()
