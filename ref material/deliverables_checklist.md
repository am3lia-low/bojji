# Deliverables Checklist

Extracted from the GovTech Data Scientist Technical Assessment (AI Track) PDF.
Every item below is stated or implied in the assessment document.

---

## A. The solution itself

- [ ] **Dockerised solution**
- [ ] **Comprehensive instructions enabling full deployment and execution**
- [ ] **Runs from the README on a clean machine** — verify literally, on a machine
      that has never seen the project
- [ ] **Significant AI integration** — not simply an API call inside a standard
      web application
- [ ] **Functional within free-tier resource limits.** If paid infrastructure is
      required for production scale, note that in the documentation
- [ ] **State any technical limitations** and describe potential enhancements if
      those constraints were removed

---

## B. Evaluation

- [ ] **Select a specific evaluation methodology** (benchmarking, LLM-as-judge,
      human evaluation, ablation, or comparison)
- [ ] **Justify the choice with a clear rationale in the README**
- [ ] Note: soundness of methodology is prioritised over magnitude of results

---

## C. Data documentation

- [ ] **Provenance** of all data used
- [ ] **Creation or processing methods**
- [ ] **Licensing**
- [ ] **Privacy considerations**
- [ ] **Compliance with source licensing and robots.txt**
- [ ] If personal information is present: ethical implications and appropriate
      handling procedures
- [ ] If synthetic data is used: **a defence for its use**, and evidence it was
      generated meaningfully and with high fidelity

---

## D. README — the primary artifact

Must document:

- [ ] **Objectives**
- [ ] **Rationale**
- [ ] **Implementation**
- [ ] **Results**
- [ ] **Execution instructions**
- [ ] **Limitations**
- [ ] **Demo video URL**

---

## E. Deployment considerations section (150–250 words, in the README)

- [ ] **Target user and environment**
- [ ] **Projected inference costs or compute footprint at scale**
- [ ] **Key performance monitoring metrics post-deployment**
- [ ] **An assessment of one specific potential deployment risk**

Note: implementation of these considerations is explicitly not required.

---

## F. Development narrative

- [ ] **Iterations**
- [ ] **Discarded strategies**
- [ ] **Tool selection rationale**
- [ ] **Decision-making justification**

---

## G. Model selection justification

- [ ] Justified on **operational requirements** — data privacy, latency, task
      suitability, fine-tuning needs, cost-at-scale economics
- [ ] **Not** justified on invalid grounds — free, cool, had it lying around
- [ ] Local vs API is irrelevant in itself; only the justification matters

---

## H. Demo video

- [ ] **3 to 5 minutes**
- [ ] Shows the application **in operation**
- [ ] Loom or screen recording
- [ ] **URL included in the README**

---

## I. Coding agent transparency

- [ ] **A section at the end of the README** on how coding agents were used
- [ ] **All coding agent session and chat logs uploaded to the repository**
      (e.g. jsonl from `~/.claude/projects/`)
- [ ] **Their location indicated in the README**

> ⚠️ Set up log capture **before writing any code**. These accumulate as you work
> and cannot be reconstructed afterwards.

---

## J. Submission protocol

- [ ] **Private GitHub repository**
- [ ] **`@govsg-ds-hiring` invited as a collaborator**
- [ ] **Repository anonymous** regarding the specific organisation or role —
      check repo name, README, and commit messages
- [ ] **Repository unchanged throughout the evaluation period** — no commits after
      submission
- [ ] **URL submitted via the recruitment portal** per HR instructions
- [ ] Deadline: **five days from receipt**. Time of submission is not a factor

---

## K. Critical non-compliance indicators — actively avoid

| Indicator | Guard |
|---|---|
| **Lack of reproducibility** | Test Docker on a clean machine; ensure a no-paid-key path works |
| **Code–writeup mismatch** | Write README claims only after results exist; never describe unbuilt features |
| **Insufficient technical justification** | Document *why* for every decision as you make it — you must defend these in interview |
| **Unsubstantiated model selection** | Justify on operational grounds only |
| **Substandard code quality** | Review all agent-generated code; type hints, docstrings, tests on the router |
| **Recycling a past project** | Fresh build; disclose prior related work proactively in the development narrative |

---

## L. Evaluation weighting (for prioritisation)

| Dimension | Weight | What it rewards |
|---|---|---|
| Problem framing & creativity | 20% | Worth solving; interesting or non-obvious angle |
| Technical execution | 25% | Runs from README on a clean machine; code quality |
| **Evaluation & effectiveness** | **30%** | Sound methodology; honest about limitations |
| Data thinking | 15% | Provenance, licensing, representativeness, resourcefulness |
| Communication | 10% | Writeup accurately describes what the code does |
