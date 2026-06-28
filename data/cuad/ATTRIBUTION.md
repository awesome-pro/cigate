# CUAD — Attribution & Provenance

This directory vendors a **subset** of the **Contract Understanding Atticus Dataset
(CUAD) v1**, a corpus of 510 real commercial contracts with expert clause
annotations created by **The Atticus Project**.

- **Dataset:** Contract Understanding Atticus Dataset (CUAD) v1
- **Creator / copyright holder:** The Atticus Project, Inc.
- **License:** Creative Commons Attribution 4.0 International (**CC BY 4.0**) —
  <https://creativecommons.org/licenses/by/4.0/>
- **Project homepage:** <https://www.atticusprojectai.org/cuad>
- **Paper:** Hendrycks, Burns, Chen, Ball. *CUAD: An Expert-Annotated NLP Dataset
  for Legal Contract Review.* NeurIPS 2021 Datasets & Benchmarks.
  <https://arxiv.org/abs/2103.06268>

## Source of the vendored data

- **Upstream archive:** `https://github.com/TheAtticusProject/cuad/raw/main/data.zip`
  (resolves to `https://raw.githubusercontent.com/TheAtticusProject/cuad/main/data.zip`)
- **Archive size:** 18,309,308 bytes
- **Archive SHA-256:** `f8161d18bea4e9c05e78fa6dda61c19c846fb8087ea969c172753bc2f45b999a`
- **File used from the archive:** `test.json` (SQuAD-2.0-style; the CUAD test split,
  102 contracts × 41 clause-category questions each, `version = aok_v1.0`).
- Also included for reference: `category_descriptions.csv` (the 41 CUAD clause
  category definitions), fetched from
  `https://github.com/TheAtticusProject/cuad/raw/main/category_descriptions.csv`.

## What is vendored here (and why)

`cuad_subset.json` is a faithful, structure-preserving subset of `test.json`:

- **48 contracts** selected deterministically: every contract from `test.json`
  with **>= 8 answerable clause categories** and a **context length between 2,000
  and 60,000 characters** (keeps documents reasonably sized while retaining enough
  annotated clauses), **sorted by title** for reproducibility.
- For each selected contract the full `context` (contract text) and **all 41**
  `qas` entries are preserved verbatim, including the expert answer spans
  (`answers[].text` / `answer_start`) and the `is_impossible` presence/absence
  flag for every clause category.
- Totals in the subset: **622** answerable (contract, category) annotations and
  **1,346** "clause-absent" (`is_impossible = true`) annotations.

The subset is vendored so the CIGate CUAD track runs fully **offline and at $0** —
`src/cigate/datasets/cuad_adapter.py` reads only this file; it never hits the
network at build or eval time.

## Modifications

No contract text or expert annotation was altered. CIGate's adapter only
*re-packages* this data into its own corpus / golden-set / calibration-set formats
(see `src/cigate/datasets/cuad_adapter.py`). The derived golden/calibration labels
are computed mechanically from CUAD's expert presence/absence flags and answer
spans; the mapping is documented in that adapter's module docstring.

## Citation

```
@article{hendrycks2021cuad,
  title={CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review},
  author={Hendrycks, Dan and Burns, Collin and Chen, Anya and Ball, Spencer},
  journal={NeurIPS},
  year={2021}
}
```

Per CC BY 4.0, this attribution must be retained in any redistribution.
