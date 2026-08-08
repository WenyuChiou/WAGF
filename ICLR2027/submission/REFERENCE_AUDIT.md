# Reference verification audit

Updated 2026-08-08 after the bibliography expansion. The audit follows the
project's verify-references workflow: source existence, title, all authors,
venue/year metadata, claim-level support, and an auditable locator. I used
publisher or proceedings pages where available and arXiv pages only for works
without a stable proceedings record.

## Verification matrix

| Key | Source and metadata result | Claim support in this manuscript | Locator | Verdict |
| --- | --- | --- | --- | --- |
| rebedea2023nemo | ACL Anthology, EMNLP Demo 2023, pp. 431--445, DOI 10.18653/v1/2023.emnlp-demo.40; title/authors exact | Runtime programmable rails can inspect/control LLM output | Abstract: programmable rails at runtime | VERIFIED |
| wang2026agentspec | ICSE 2026, DOI 10.1145/3744916.3764546; title/authors exact; arXiv identifier retained | Runtime constraints can be specified and enforced | ICSE abstract: triggers, predicates, enforcement mechanisms | VERIFIED |
| kapoor2024agents | arXiv:2407.01502 and arXiv DOI; title/authors exact | Agent benchmarks can mislead when metrics, holdouts, cost, and reproducibility are under-specified | Abstract: shortcomings in accuracy-only and reproducibility practice | VERIFIED (preprint signal) |
| liu2023agentbench | ICLR 2024 proceedings; arXiv:2308.03688; all 22 authors corrected to the published record | Agent evaluation can be multi-dimensional and interactive | ICLR abstract: eight interactive environments | VERIFIED |
| ma2024agentboard | NeurIPS 2024 Datasets and Benchmarks, vol. 37, DOI 10.52202/079017-2365; all authors exact | Process/progress diagnostics reveal more than final success alone | Abstract: fine-grained progress rate for multi-round agents | VERIFIED |
| zhou2024webarena | ICLR 2024 proceedings; arXiv:2307.13854; all authors exact | Realistic environments can check long-horizon task outcomes | ICLR abstract: functional correctness in realistic websites | VERIFIED |
| jimenez2024swebench | ICLR 2024 proceedings; arXiv:2310.06770; all authors exact | Repository tasks use executable fail-to-pass outcomes | ICLR abstract: code edits evaluated against issue-linked tests | VERIFIED |
| yao2025taubench | ICLR 2025 proceedings; arXiv:2406.12045; all four authors exact | Tool-agent-user interaction can include domain policy and state-change checks | ICLR abstract: APIs, policy guidelines, final database state | VERIFIED |
| zhu2025abc | NeurIPS 2025 Datasets and Benchmarks, vol. 38, DOI 10.52202/085713-5547; all authors exact | Benchmark setup and reward design can distort agent scores | Abstract: under/over-estimation and Agentic Benchmark Checklist | VERIFIED |
| bean2025construct | NeurIPS 2025 Datasets and Benchmarks, vol. 38; arXiv:2511.04703; authors/title updated to the published record | Construct validity asks whether a benchmark measures the intended phenomenon | Abstract: systematic review of benchmark constructs and metrics | VERIFIED |
| rosenbaum1984adjustment | JRSS Series A 147(5), 656--666, 1984, DOI 10.2307/2981697; title/author/pages exact | Conditioning on a post-treatment variable can bias an adjustment | Abstract: concomitant affected by treatment | VERIFIED |
| yao2023react | ICLR 2023 proceedings; arXiv:2210.03629; authors/title exact | Agent behavior can be organized as interleaved reasoning and action | ICLR abstract: acting with external sources and environments | VERIFIED |
| shinn2023reflexion | NeurIPS 2023, vol. 36, DOI 10.52202/075280-0377; authors corrected to published record | Feedback can be part of a repeated agent loop | Abstract: verbal feedback and subsequent decisions | VERIFIED |
| wu2023autogen | arXiv:2308.08155; title/authors exact; technical-report exception | Multi-agent conversation extends tool/feedback loops | Abstract: agents converse to accomplish tasks | VERIFIED |
| yang2024sweagent | NeurIPS 2024, vol. 37, DOI 10.52202/079017-1601; authors/title exact | Interface design can change agent behavior and performance | Abstract: agent-computer interface affects software tasks | VERIFIED |

## Cross-file checks

- The manuscript cites 15 distinct keys, and all 15 keys occur in the
  bibliography.
- No bibliography entry is currently uncited.
- The introduction uses the new references for context and gap construction;
  none is used as evidence for the WAGF numerical results.
- The only preprint-only sources are kapoor2024agents and wu2023autogen;
  yao2023react, zhou2024webarena, jimenez2024swebench, and
  yao2025taubench retain arXiv identifiers but are cited as ICLR papers.
- The bibliography is now targeted rather than padded. Fifteen sources cover
  agent evaluation, runtime enforcement, interactive environments, feedback
  loops, construct validity, and benchmark rigor. A venue-specific related-work
  expansion can be added later only if it changes the gap or comparison.

## Remaining check at upload

Re-run the static bibliography check and the TeX build after any author-list or
venue metadata change. Do not add a citation merely because it is a popular
agent framework; every new source needs a claim sentence and a source locator.
