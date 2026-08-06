# Debate: Figure 1 branching redesign

**Decision:** Should Figure 1 use an explicit accepted-versus-blocked/revised branching schematic (A), or retain the current compact three-card strip with a single intervention mark (B)?
**Round:** 1 adversarial review
**Side A (main agent):** Use the explicit branches, rename the field to `agent-reported state`, and label high scarcity as a worked example. This should make the intervention and denominator path readable without relying on the caption.
**Side B (adversarial agent):** Challenge whether the branches add clarity or instead overstate the protocol, create visual density, or confuse the conceptual example with the full experiment.

---

## Round 1

### Side A - proposed design

The figure will keep the WAGF/GitHub visual register: white rounded cards, sparse serif labels, line-art icons, one pale-yellow semantic band, and restrained red for intervention. The left card will show one agent answer containing a proposed action and an `agent-reported state`, with `high scarcity` visibly marked as an example. The center validator card will split the path into an ordinary accepted output and a red `blocked -> revised answer` path. The right card will show the reported conformance rate, with the same state field feeding the denominator. This makes the reader's causal reading explicit: output -> validation -> either retained or revised output -> conditional metric. The caption will state that the example is conceptual and that the quantitative anchor values are reported elsewhere.

### Side B - adversarial agent

The proposed fork risks turning a conceptual measurement diagram into an
unearned protocol trace. First, “accepted” versus “blocked -> revised” sounds
exhaustive and terminal, but the setup permits ERROR rejection, repeated
retries, and a domain default after exhaustion. It also does not establish that
the revised answer, rather than the last-proposed or recorded action, is what
Table 1 uses. Repair: label the paths “passes” versus “re-prompt (possibly
repeated; default if exhausted)” and identify the downstream item as the
“record used for statistic,” with the caption naming the recorded attempt.

Second, the arrow from blocked output to a changed denominator invites a causal
mediation claim the evidence does not identify. It implies that the rule itself
changes the reported appraisal, while world/action feedback, retry selection,
and post-treatment composition remain alternatives; the first-attempt
appraisal is unavailable. Repair: use a dashed or conditional connection and
say “can alter the set of decisions counted,” framing this as an
estimand/measurement pathway rather than a demonstrated mechanism.

Third, “agent-reported state” is broad: readers may confuse an authored
appraisal with simulator-recorded world state. “High scarcity” is not general
WAGF language, and the actual norm requires high scarcity plus high coping;
showing only scarcity can be read as the full antecedent. Repair: identify the
label as an irrigation example and leave the full conjunction to the caption.

Finally, at 0.80 linewidth, duplicating accepted and revised outputs adds text,
arrows, and endpoints to an already small design. Recommendation: use a
constrained hybrid—retain the compact strip, adding only a minimal passes /
re-prompt fork, with the caption specifying the attempt and estimand.

---

## Synthesis

The adversarial review rejects a full two-output flowchart. Its strongest point
is scope control: the figure should show an evaluation pathway, not assert that
every rejection is terminal or that the revised attempt is a uniquely
identified causal mediator. The accepted design is therefore a constrained
hybrid: keep one compact answer card and the continuous state/denominator
strip; add only a black `passes` route and a red `blocked -> re-prompt` return
route. The caption must identify high scarcity as an illustrative irrigation
example, distinguish the agent-authored field from simulator-recorded state,
and state that the pathway can alter which decisions are counted. Confidence:
high for the visual simplification, medium for the exact wording until the
recorded-attempt convention is rechecked in the evidence release.
