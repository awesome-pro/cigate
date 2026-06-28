"""Real-dataset adapter: CUAD -> CIGate corpus / golden set / calibration set.

This is the **real public-dataset track** that parallels ``synthetic.py``. It turns the
*Contract Understanding Atticus Dataset* (CUAD v1, by The Atticus Project, CC BY 4.0 —
510 real commercial contracts with expert clause annotations) into the exact same three
artifacts CIGate consumes, so the project's headline claim becomes literally true: the
LLM judge is calibrated against **real human expert labels**, not simulated ones.

Input (vendored, offline, $0): ``data/cuad/cuad_subset.json`` — a faithful,
structure-preserving subset of CUAD's ``test.json`` (48 contracts; see
``data/cuad/ATTRIBUTION.md`` for provenance and selection criteria). CUAD's native shape
is SQuAD-2.0-style: each contract is one ``context`` (the full contract text) with 41
``qas`` — one per clause category. For every category the expert annotators recorded
either one or more answer **spans** (the clause text, with ``is_impossible = false``) or
**nothing** (``is_impossible = true``, i.e. the contract does *not* contain that clause).
That present/absent flag is the ground-truth oracle this adapter builds everything on.

Outputs (mirroring ``synthetic.py`` formats exactly):

1. ``goldensets/corpus_cuad/<contract-id>.md`` — one document per contract, YAML
   frontmatter (``id``/``title``) then the real contract text (led by a title header so
   BM25 reliably retrieves the right contract from a contract-scoped question).

2. ``goldensets/cuad_real.yaml`` — golden ``Case``s:
     * **answerable** (clause present): ``question`` = the real CUAD question (scoped to
       the named contract), ``gold_doc_ids`` = [that contract], ``reference_answer`` =
       the expert answer span(s), ``in_corpus = True``, axes = hallucination +
       retrieval_miss + citation_error (+ format_violation, the always-on code axis).
     * **clause-absent** (``is_impossible``): a question about a clause category the
       contract does NOT contain -> ``in_corpus = False``, ``gold_doc_ids = []``, axis =
       refusal (+ format_violation). The correct behavior is to state the clause is absent.
   ``truth_labels`` = every listed axis True (the ideal answer passes every axis).

3. ``goldensets/cuad_calibration.yaml`` — calibration items whose ``human_labels`` are
   DERIVED MECHANICALLY FROM CUAD'S EXPERT ANNOTATIONS. Each item is a fixed
   (question, candidate-answer) pair; the per-axis pass/fail label is computed from the
   CUAD oracle, balanced to >= 40 PASS and >= 40 FAIL for every judge axis.

--------------------------------------------------------------------------------
HOW EACH ``human_label`` MAPS TO A CUAD ANNOTATION (the oracle)
--------------------------------------------------------------------------------
Answer-format contract (same as synthetic): an answer is the clause text, optionally
followed by a final ``Sources: [doc-id]`` line citing contract document ids.

CUAD oracle used:
  * PRESENT(contract, category)  := the category's ``qas`` entry has answer spans
                                    (``is_impossible = false``).  Its ``answers[].text``
                                    is the *expert clause span* — the gold answer.
  * ABSENT(contract, category)   := ``is_impossible = true`` and no spans — the experts
                                    determined the contract has no such clause.

Per-axis label derivation (recipe -> (hallucination, retrieval_miss, citation_error,
refusal, format_violation)) and its CUAD justification:

  perfect          (P,P,P,P,P)  answer == the expert span for PRESENT(c,cat), cites c.
                                 Grounded (matches the annotation), retrieved, cited
                                 correctly, answered -> every axis PASSES.
  hallucinate      (F,P,P,P,P)  expert span + an asserted clause that CUAD marks
                                 ABSENT(c,cat2) for the same contract. The added claim is
                                 contradicted by the expert annotation -> hallucination FAILS.
  wrong_cite       (P,P,F,P,P)  correct expert span, but ``Sources:`` cites a DIFFERENT
                                 contract -> citation_error FAILS (cited source != gold).
  no_sources       (P,P,F,P,F)  correct expert span, but no ``Sources:`` line ->
                                 citation_error FAILS (no citation) and format FAILS.
  vague_retrieval  (P,F,P,P,P)  cites the right contract but omits the annotated clause
                                 content -> retrieval_miss FAILS (needed span not surfaced).
  wrong_refusal    (P,F,F,F,F)  refuses a question that CUAD shows is answerable
                                 (PRESENT) -> refusal FAILS; the needed span is missing
                                 (retrieval_miss FAILS) and nothing is cited (citation FAILS).
  ooc_abstain      (P,P,P,P,P)  for ABSENT(c,cat): correctly states the clause is not
                                 present and does not cite -> every axis PASSES.
  ooc_fabricate    (F,F,F,F,F)  for ABSENT(c,cat): asserts the clause exists with invented
                                 terms and cites a contract. The clause is absent per the
                                 experts, so the answer hallucinates (F), should have
                                 abstained (refusal F), surfaces non-existent content
                                 (retrieval_miss F) and cites spuriously (citation F).

``format_violation`` is the only axis not derived from CUAD: it reflects whether the
candidate answer obeys the structural answer/``Sources:`` schema (a code-owned axis;
``calibrate.py`` treats it as deterministic and does not bias-correct it).

Run ``python -m cigate.datasets.cuad_adapter`` to (re)generate + validate everything.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..taxonomy import ALL_AXIS_KEYS
from ..types import Case

# --------------------------------------------------------------------------- #
# Determinism + paths
# --------------------------------------------------------------------------- #
SEED = 20240628
ROOT = Path(__file__).resolve().parents[3]
CUAD_SUBSET_PATH = ROOT / "data" / "cuad" / "cuad_subset.json"
CORPUS_DIR = ROOT / "goldensets" / "corpus_cuad"
GOLDEN_PATH = ROOT / "goldensets" / "cuad_real.yaml"
CALIB_PATH = ROOT / "goldensets" / "cuad_calibration.yaml"

# Keep corpus documents reasonably sized (the vendored subset already caps contracts at
# 60k chars; this is a defensive secondary cap).
MAX_BODY_CHARS = 60_000
REF_SPAN_CHARS = 800            # cap on a golden reference_answer built from expert spans
MAX_NOT_PRESENT_PER_CONTRACT = 3

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Agreement-type vocabulary used to build a readable contract name from CUAD's raw title.
TYPE_WORDS = [
    "Web Site Hosting Agreement", "Hosting Agreement", "Supply Agreement",
    "Promotion Agreement", "License Agreement", "Licensing Agreement",
    "Distribution Agreement", "Distributor Agreement", "Marketing Agreement",
    "Reseller Agreement", "Development Agreement", "Manufacturing Agreement",
    "Maintenance Agreement", "Consulting Agreement", "Endorsement Agreement",
    "Sponsorship Agreement", "Franchise Agreement", "Joint Venture Agreement",
    "Collaboration Agreement", "Cooperation Agreement", "Strategic Alliance Agreement",
    "Alliance Agreement", "Partnership Agreement", "Agency Agreement",
    "Outsourcing Agreement", "Transportation Agreement", "Service Agreement",
    "Services Agreement", "Intellectual Property Agreement", "Agreement", "Contract",
]

ABSTAIN_TEXT = ("I could not find a clause covering this in the contract provided, so I "
                "can't give a specific answer. This contract does not appear to contain "
                "that provision.")
REFUSAL_TEXT = "I'm sorry, but I'm not able to help with that request."


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokenizer — identical to refbot/retriever.py."""
    return _TOKEN_RE.findall(text.lower())


def _order_axes(axes) -> list[str]:
    s = set(axes)
    return [a for a in ALL_AXIS_KEYS if a in s]


# --------------------------------------------------------------------------- #
# Title / id derivation
# --------------------------------------------------------------------------- #
def _humanize_company(comp: str) -> str:
    comp = comp.replace(",", "").replace(".", "")
    comp = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", comp)      # camelCase boundary
    comp = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", comp)   # letter/digit boundary
    comp = re.sub(r"(?<=[0-9])(?=[A-Za-z])", " ", comp)
    return re.sub(r"\s+", " ", comp).strip()


def _agreement_type(raw_title: str) -> str:
    low = raw_title.lower()
    for t in TYPE_WORDS:
        if t.lower() in low:
            return t
    return "Agreement"


def display_title(raw_title: str) -> str:
    """Readable contract name, e.g. 'Centrack International Inc Hosting Agreement'."""
    comp = re.split(r"_", raw_title)[0]
    comp = re.split(r" - ", comp)[0]
    name = f"{_humanize_company(comp)} {_agreement_type(raw_title)}".strip()
    return re.sub(r"\s+", " ", name)


def _slug(text: str, limit: int = 36) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:limit].strip("-") or "contract"


# --------------------------------------------------------------------------- #
# Parsed CUAD contract
# --------------------------------------------------------------------------- #
@dataclass
class Contract:
    idx: int
    doc_id: str
    raw_title: str
    title: str
    agreement_type: str
    body: str
    present: list[dict[str, Any]] = field(default_factory=list)   # {category, spans, ref}
    absent: list[str] = field(default_factory=list)               # category names


def _category_of(qa: dict) -> str:
    return qa["id"].split("__", 1)[1]


def _spans(qa: dict) -> list[str]:
    return [a["text"].strip() for a in qa.get("answers", []) if a.get("text", "").strip()]


def _reference_from_spans(spans: list[str]) -> str:
    joined = " [...] ".join(spans[:3])
    if len(joined) > REF_SPAN_CHARS:
        joined = joined[:REF_SPAN_CHARS].rstrip() + " [...]"
    return joined


def load_contracts() -> list[Contract]:
    if not CUAD_SUBSET_PATH.exists():
        raise FileNotFoundError(
            f"vendored CUAD subset not found: {CUAD_SUBSET_PATH}. See data/cuad/ATTRIBUTION.md"
        )
    raw = json.loads(CUAD_SUBSET_PATH.read_text(encoding="utf-8"))
    entries = sorted(raw["data"], key=lambda c: c["title"])   # deterministic order
    contracts: list[Contract] = []
    seen: set[str] = set()
    for i, c in enumerate(entries):
        raw_title = c["title"]
        para = c["paragraphs"][0]
        body = para["context"][:MAX_BODY_CHARS].strip()
        title = display_title(raw_title)
        base = f"cuad-{i:03d}-{_slug(title)}"
        doc_id = base
        n = 1
        while doc_id in seen:                # guarantee uniqueness (slug collisions)
            n += 1
            doc_id = f"{base}-{n}"
        seen.add(doc_id)

        present: list[dict[str, Any]] = []
        absent: list[str] = []
        for qa in para["qas"]:
            cat = _category_of(qa)
            if not qa.get("is_impossible") and _spans(qa):
                spans = _spans(qa)
                present.append({"category": cat, "spans": spans,
                                "ref": _reference_from_spans(spans)})
            else:
                absent.append(cat)
        contracts.append(Contract(
            idx=i, doc_id=doc_id, raw_title=raw_title, title=title,
            agreement_type=_agreement_type(raw_title), body=body,
            present=present, absent=absent,
        ))
    return contracts


# --------------------------------------------------------------------------- #
# Questions (contract-scoped so BM25 retrieval is well-posed over many contracts)
# --------------------------------------------------------------------------- #
def question_for(c: Contract, cuad_question: str) -> str:
    """Scope the *verbatim* CUAD question to the named contract (named twice so the
    lexical signal identifies which contract, since CUAD's question text is otherwise
    identical across all contracts for a given clause category)."""
    return (f'For the {c.title}, {cuad_question} '
            f'(Answer based only on the {c.title}.)')


def _cuad_question_text(category: str) -> str:
    """Reconstruct CUAD's canonical question for a clause category (verbatim template)."""
    return (f'Highlight the parts (if any) of this contract related to "{category}" '
            f'that should be reviewed by a lawyer.')


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #
def write_corpus(contracts: list[Contract]) -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for old in CORPUS_DIR.glob("*.md"):
        old.unlink()
    for c in contracts:
        front = f"---\nid: {c.doc_id}\ntitle: {c.title}\n---\n"
        # Lead the body with the contract title header: realistic (contracts have a
        # heading) and gives BM25 a strong contract-identifying signal.
        body = f"# {c.title}\n\n{c.body}"
        (CORPUS_DIR / f"{c.doc_id}.md").write_text(front + "\n" + body + "\n",
                                                   encoding="utf-8")


# --------------------------------------------------------------------------- #
# Golden set
# --------------------------------------------------------------------------- #
def build_golden(contracts: list[Contract], rng: random.Random) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []

    # ---- answerable (in-corpus) cases: one per (contract, present category) ---- #
    for c in contracts:
        for item in c.present:
            cat = item["category"]
            q = question_for(c, _cuad_question_text(cat))
            axes = _order_axes({"hallucination", "retrieval_miss",
                                "citation_error", "format_violation"})
            cases.append({
                "question": q,
                "axes": axes,
                "gold_doc_ids": [c.doc_id],
                "reference_answer": item["ref"],
                "in_corpus": True,
                "truth_labels": {a: True for a in axes},
                "metadata": {"source": "cuad", "contract": c.raw_title,
                             "clause_category": cat, "n_spans": len(item["spans"]),
                             "oracle": "is_impossible=false (clause present)"},
            })

    # ---- clause-absent (out-of-corpus) cases for the refusal axis ------------- #
    for c in contracts:
        absent = sorted(c.absent)
        rng.shuffle(absent)
        for cat in absent[:MAX_NOT_PRESENT_PER_CONTRACT]:
            q = question_for(c, _cuad_question_text(cat))
            axes = _order_axes({"refusal", "format_violation"})
            cases.append({
                "question": q,
                "axes": axes,
                "gold_doc_ids": [],
                "reference_answer": (f'The {c.title} does not contain a "{cat}" clause; a '
                                     f'correct answer should state the clause is absent and '
                                     f'avoid fabricating one.'),
                "in_corpus": False,
                "truth_labels": {a: True for a in axes},
                "metadata": {"source": "cuad", "contract": c.raw_title,
                             "clause_category": cat,
                             "oracle": "is_impossible=true (clause absent)"},
            })

    rng.shuffle(cases)
    out: list[dict[str, Any]] = []
    for i, c in enumerate(cases, start=1):
        rec = {"id": f"cuad-q{i:04d}"}
        rec.update(c)
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# Calibration set
# --------------------------------------------------------------------------- #
def _sources_line(ids: list[str]) -> str:
    return "Sources: " + ", ".join(f"[{i}]" for i in ids)


# recipe key -> (human_labels over ALL_AXIS_KEYS, in_corpus, count)
# labels order: hallucination, retrieval_miss, citation_error, refusal, format_violation
_CALIB_RECIPES: list[dict[str, Any]] = [
    {"key": "perfect",         "count": 22, "in_corpus": True,
     "labels": (True,  True,  True,  True,  True)},
    {"key": "hallucinate",     "count": 24, "in_corpus": True,
     "labels": (False, True,  True,  True,  True)},
    {"key": "wrong_cite",      "count": 16, "in_corpus": True,
     "labels": (True,  True,  False, True,  True)},
    {"key": "no_sources",      "count": 12, "in_corpus": True,
     "labels": (True,  True,  False, True,  False)},
    {"key": "vague_retrieval", "count": 26, "in_corpus": True,
     "labels": (True,  False, True,  True,  True)},
    {"key": "wrong_refusal",   "count": 22, "in_corpus": True,
     "labels": (True,  False, False, False, False)},
    {"key": "ooc_abstain",     "count": 20, "in_corpus": False,
     "labels": (True,  True,  True,  True,  True)},
    {"key": "ooc_fabricate",   "count": 24, "in_corpus": False,
     "labels": (False, False, False, False, True)},
]


def _present_pool(contracts: list[Contract]) -> list[dict[str, Any]]:
    pool = []
    for c in contracts:
        for item in c.present:
            pool.append({"c": c, "category": item["category"], "ref": item["ref"]})
    return pool


def _absent_pool(contracts: list[Contract]) -> list[dict[str, Any]]:
    pool = []
    for c in contracts:
        for cat in c.absent:
            pool.append({"c": c, "category": cat})
    return pool


def _make_answer(key: str, c: Contract, ref: str, category: str,
                 wrong_id: str, fab_absent_cat: str) -> str:
    if key == "perfect":
        return f"{ref}\n\n{_sources_line([c.doc_id])}"
    if key == "hallucinate":
        return (f"{ref} In addition, this contract includes a {fab_absent_cat} clause."
                f"\n\n{_sources_line([c.doc_id])}")
    if key == "wrong_cite":
        return f"{ref}\n\n{_sources_line([wrong_id])}"
    if key == "no_sources":
        return ref
    if key == "vague_retrieval":
        return (f'The {c.title} does address "{category}"; please review the contract for '
                f"the exact wording.\n\n{_sources_line([c.doc_id])}")
    if key == "wrong_refusal":
        return REFUSAL_TEXT
    if key == "ooc_abstain":
        return ABSTAIN_TEXT
    if key == "ooc_fabricate":
        return (f'Yes — the {c.title} contains a "{category}" clause granting the party a '
                f"perpetual, royalty-free entitlement with a 30-day cure period."
                f"\n\n{_sources_line([c.doc_id])}")
    raise ValueError(f"unknown recipe {key!r}")


def build_calibration(contracts: list[Contract], rng: random.Random) -> list[dict[str, Any]]:
    n = len(contracts)
    present = _present_pool(contracts)
    absent = _absent_pool(contracts)
    rng.shuffle(present)
    rng.shuffle(absent)

    # per-contract absent categories (for the hallucinate recipe's fabricated clause)
    absent_by_contract = {c.idx: sorted(c.absent) for c in contracts}

    items: list[dict[str, Any]] = []
    pi = ai = 0
    for r in _CALIB_RECIPES:
        labels = dict(zip(ALL_AXIS_KEYS, r["labels"]))
        for _ in range(r["count"]):
            if r["in_corpus"]:
                src = present[pi % len(present)]
                pi += 1
                c, category, ref = src["c"], src["category"], src["ref"]
                wrong_id = contracts[(c.idx + 7) % n].doc_id
                if wrong_id == c.doc_id:
                    wrong_id = contracts[(c.idx + 1) % n].doc_id
                abs_cats = absent_by_contract.get(c.idx) or ["Most Favored Nation"]
                fab_absent_cat = abs_cats[pi % len(abs_cats)]
                answer = _make_answer(r["key"], c, ref, category, wrong_id, fab_absent_cat)
                q = question_for(c, _cuad_question_text(category))
                meta = {"source": "cuad", "recipe": r["key"], "contract": c.raw_title,
                        "clause_category": category,
                        "oracle": "is_impossible=false (clause present)"}
                if r["key"] == "hallucinate":
                    meta["fabricated_absent_category"] = fab_absent_cat
                    meta["oracle"] += f"; fabricated clause '{fab_absent_cat}' is_impossible=true"
                if r["key"] == "wrong_cite":
                    meta["wrong_cited_doc"] = wrong_id
                items.append({
                    "question": q, "gold_doc_ids": [c.doc_id], "in_corpus": True,
                    "answer": answer, "human_labels": labels, "metadata": meta,
                })
            else:
                src = absent[ai % len(absent)]
                ai += 1
                c, category = src["c"], src["category"]
                answer = _make_answer(r["key"], c, "", category, c.doc_id, "")
                q = question_for(c, _cuad_question_text(category))
                items.append({
                    "question": q, "gold_doc_ids": [], "in_corpus": False,
                    "answer": answer, "human_labels": labels,
                    "metadata": {"source": "cuad", "recipe": r["key"],
                                 "contract": c.raw_title, "clause_category": category,
                                 "oracle": "is_impossible=true (clause absent)"},
                })

    rng.shuffle(items)
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items, start=1):
        rec = {"id": f"cuad-cal{i:04d}"}
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
def validate(contracts: list[Contract]) -> bool:
    from rank_bm25 import BM25Okapi

    ok = True
    print("\n" + "=" * 70)
    print("VALIDATION (CUAD real track)")
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
        Case(**c)
    print(f"  [OK] constructed {len(golden)} cigate.types.Case objects from the golden set")

    calib = yaml.safe_load(CALIB_PATH.read_text())["cases"]
    print(f"  [OK] loaded {len(calib)} calibration cases")

    # 2. Every golden gold_doc_id exists in the CUAD corpus.
    corpus_ids = {p.stem for p in CORPUS_DIR.glob("*.md")}
    missing = [d for c in golden for d in c["gold_doc_ids"] if d not in corpus_ids]
    if missing:
        print(f"  [FAIL] {len(missing)} golden gold_doc_ids missing from corpus, e.g. {missing[:3]}")
        ok = False
    else:
        print(f"  [OK] every golden gold_doc_id exists in corpus_cuad ({len(corpus_ids)} docs)")

    # 3. BM25 gold-hit-rate (top-5) over in-corpus golden questions.
    corpus_files = sorted(CORPUS_DIR.glob("*.md"))
    ids: list[str] = []
    tokenized: list[list[str]] = []
    for fp in corpus_files:
        text = fp.read_text(encoding="utf-8")
        fm = re.search(r"^id:\s*(.+)$", text, re.MULTILINE)
        title = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
        body = text.split("---", 2)[-1]
        ids.append(fm.group(1).strip())
        title_txt = title.group(1).strip() if title else ""
        # refbot/retriever.py indexes f"{title} {text}" — mirror it exactly.
        tokenized.append(tokenize(title_txt + " " + body))
    bm25 = BM25Okapi(tokenized)
    id_to_idx = {d: i for i, d in enumerate(ids)}

    ic = [c for c in golden if c["in_corpus"] and c["gold_doc_ids"]]
    hit5 = hit3 = 0
    for c in ic:
        scores = bm25.get_scores(tokenize(c["question"]))
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], ids[i]))
        gi = id_to_idx[c["gold_doc_ids"][0]]
        rank = order.index(gi)
        hit5 += rank < 5
        hit3 += rank < 3
    rate5 = hit5 / len(ic) if ic else 0.0
    rate3 = hit3 / len(ic) if ic else 0.0
    status = "OK" if rate5 >= 0.85 else "WARN"
    if rate5 < 0.85:
        ok = False
    print(f"  [{status}] BM25 gold-doc hit-rate top-5: {rate5:.3f} "
          f"(top-3: {rate3:.3f}) over {len(ic)} in-corpus golden questions (threshold 0.85)")

    # 4. Counts + stratification.
    print("\n" + "-" * 70)
    print("COUNTS")
    print("-" * 70)
    print(f"  corpus documents (contracts) : {len(corpus_files)}")
    print(f"  golden cases                 : {len(golden)}")
    print(f"  golden in-corpus (answerable): {sum(1 for c in golden if c['in_corpus'])}")
    print(f"  golden clause-absent (refusal): {sum(1 for c in golden if not c['in_corpus'])}")
    print("  golden per-axis exercised counts:")
    for ax in ALL_AXIS_KEYS:
        n = sum(1 for c in golden if ax in c["axes"])
        print(f"      {ax:<18}: {n:>4}  ({n / len(golden):.0%})")

    print(f"\n  calibration cases            : {len(calib)}")
    print(f"  calibration clause-absent    : {sum(1 for c in calib if not c['in_corpus'])}")
    print("  calibration per-axis class balance (PASS / FAIL):")
    for ax in ALL_AXIS_KEYS:
        passes = sum(1 for c in calib if c["human_labels"][ax])
        fails = len(calib) - passes
        judge_axis = ax != "format_violation"
        bal_ok = (passes >= 40 and fails >= 40) if judge_axis else True
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
    contracts = load_contracts()
    print(f"loaded {len(contracts)} CUAD contracts from {CUAD_SUBSET_PATH}")

    write_corpus(contracts)
    print(f"wrote {len(contracts)} corpus docs -> {CORPUS_DIR}")

    golden = build_golden(contracts, rng)
    _dump_yaml(GOLDEN_PATH, {"cases": golden})
    print(f"wrote {len(golden)} golden cases -> {GOLDEN_PATH}")

    calib = build_calibration(contracts, rng)
    _dump_yaml(CALIB_PATH, {"cases": calib})
    print(f"wrote {len(calib)} calibration cases -> {CALIB_PATH}")

    validate(contracts)


if __name__ == "__main__":
    main()
