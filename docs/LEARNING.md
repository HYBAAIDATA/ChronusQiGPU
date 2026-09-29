# How PYTHIA learns

This is the formal learning system: what counts as learning, how it is
judged, where the intelligences' questions come from, and what each learner
has actually learned. The code is `mla1517_platform_v3.4/python/mla1517/learning.py`;
the curriculum is `mla1517_platform_v3.4/python/mla1517/seeds/questions.yaml`.

## What counts as learning

A learner has learned something when it predicts outcomes it has not yet
seen better than a named baseline that lacks its knowledge. Nothing else
counts: not confidence, not effort, not the number of patterns stored.

The judgement is **prequential** (A. P. Dawid, 1984). For every outcome:

1. The learner commits its forecast **before** the outcome exists, and the
   baseline commits its forecast at the same moment.
2. The outcome arrives and both are scored with the log score, a proper
   scoring rule: honest forecasts score best.
3. The difference, in **bits per outcome**, is the learning. Its running sum
   is the log-likelihood ratio of learner over baseline: the weight of
   evidence that learning happened.

In the live miner, forecasts are committed when a plan is built and scored
when its window finishes, before the world model learns from that window.

## The loop

```text
question (seeded)      what to look for, why, and the baseline to beat
   -> forecast         committed by the learner before the outcome
   -> outcome          measured
   -> score            log score, learner vs baseline, in bits
   -> status           open / not_yet / mastered / regressed
                       laws: holds / anomaly;  facts: answered / stale
   -> explanation      one sentence an operator can act on
   -> shared           knowledge fabric: question.<id>, learning.<id>
```

Status is earned and can be lost:

| Status | Meaning |
|---|---|
| `open` | nobody has answered yet |
| `not_yet` | evidence is coming in; skill is not established (too few outcomes, or no reliable edge over the baseline) |
| `mastered` | the lower 95% bound of skill is above zero over the whole record, **and** the recent record is still positive |
| `regressed` | was mastered, but recent forecasts no longer beat the baseline: the world moved, or the learner forgot |
| `holds` / `anomaly` | a law's exact 95% interval does / does not contain what the law predicts |
| `answered` / `stale` | a fact question's answer exists / its basis has since changed |

Mastered knowledge is still tested on every outcome, and recent outcomes
weigh more than old ones, so drift shows up as regression rather than as
silent error. Every learner's 90% intervals are also checked for coverage:
a learner that claims more certainty than it has is reported as
`overconfident`.

## Seeding: telling the intelligences what to look for

A learner that is not told what to look for will not find it, however
capable. Popper made the point by telling a class simply to "observe": the
class asked *what* to observe. Knowledge is therefore seeded as
**questions, not answers**, in `seeds/questions.yaml`:

```yaml
- id: window.invalidated
  kind: probability
  ask: Will the next window's work be invalidated before it finishes?
  why: Invalidated work is the stale loss the policy trades against overhead.
  learner: mining.world_model
  baseline: the fraction of windows invalidated so far
```

**Why YAML and not JSON.** The seeds are written and reviewed by people, in
pull requests. YAML takes comments and reads like a document; JSON is kept
for what machines write (the fabric journal is JSON Lines). The loader is
strict: an unknown key, a question without a reason, or a quantity question
without a baseline is refused. One trap it guards against: a bare `null:`
key is read by YAML as nothing at all, which is why the field is called
`baseline`.

Each question is published to the knowledge fabric (`question.<id>`), so
every intelligence can see what is being asked, and its status is published
beside it (`learning.<id>`). The statuses are also the ledger's memory: a
restarted miner restores its learning record from the fabric.

**To add a question:** add an entry by pull request. It must say what it
asks, why it matters, and either who answers and what baseline they must
beat, or which published fact answers it, or (for an open question) how it
could be answered.

## The seeded curriculum

| Question | Kind | Answered by |
|---|---|---|
| `window.elapsed`: how long will the next window take? | quantity | world model vs "previous window's time per hash" |
| `window.invalidated`: will the next window be invalidated? | probability | world model vs "fraction invalidated so far" |
| `shares.follow.work`: does anything find shares faster than the work predicts? | law | `Poisson(hashes × (target+1)/2²⁵⁶)`, tested every cycle |
| `route.opencl.rate`: what does the OpenCL route really sustain? | fact | the world model's measured route |
| `policy.levers`: does any lever beat the learned policy? | fact | the discovery worker's campaign |
| `device.sag`: does the device slow within a window? | fact | the world model: marginal time per hash across the window sizes it has measured |
| `precompute.depth`: will a plan be ready when the executor needs one? | probability | the policy's depth model vs "fraction of windows that found a plan ready" |
| `recovery.effect`: which recoveries restore throughput? | fact | measured hash rate over the windows before and after each verified recovery |
| `policy.promotion`: has a candidate earned its place? | fact | the promotion gate (below) |

These three were open questions in the first version of the ledger; each
now has a learner. An open question is still the right way to add
something nobody can answer yet: it tells the next learner where to start.

## The learners, honestly

| Learner | On the live path | Judged by |
|---|---|---|
| Mining world model (route `o` and `H`, invalidation and job-churn rates, plan latency) | yes | `window.elapsed`, `window.invalidated` |
| Operating policy (window, precompute depth) | yes; decides from the world model | through the world model's forecasts; the simulator bench |
| Hashrate governor (share yield) | yes | `shares.follow.work` |
| Active Discovery Engine (theory of lever effects) | discovery worker, on a simulated twin | replication and surprise against its own theory |
| Salamander's skill grafts | repair stage (guidance) | provenance verification before each new graft |
| `Intelligence/pythia_learning.py`, `pythia_memory.py` curriculum | no | evidence tests of their own (below) |

That last learner used to trust itself. Its curriculum advanced on a
confidence computed from the length of a plan, and a pattern became a
"germ-line" memory after three sightings next to a share. Both now need
evidence:

- **Mastery** is the Wilson 95% lower bound of the recorded success rate,
  over at least five attempts.
- **Germ-line** needs an exact one-sided binomial test against the base rate
  of every other pattern, Bonferroni-corrected, re-judged at every
  consolidation. Under the share law a pattern's shares are at the base
  rate, so in practice nothing passes: which is the correct answer.

## The promotion gate

A self-improving player keeps its current best version until a candidate
beats it in play (Silver et al., 2017). Here a candidate is a set of
operating levers the discovery worker found in the twin, and it must win
twice (`mla1517/mining/promotion.py`):

1. **Twin round** (discovery worker): replayed on eight fresh paired seeds,
   never the seeds it was found on (a finding chosen as the best of many is
   flattered on those: the winner's curse). It must win an exact one-sided
   sign test at 5% (`promotion.candidate`).
2. **Shadow round** (live miner): the candidate decides beside the running
   policy for every window, without acting. Where both chose window sizes
   the miner has measured, each choice is worth its measured valid hashes
   per second. Decisions are pooled into epochs of 64, and the candidate
   must again win the sign test over the epochs (`promotion.status`).

Only then are its levers applied. A lever may only tighten the operator's
bounds (a shorter responsiveness envelope, a lower window ceiling); nothing
learned can widen them, and no lever touches SHA256d, targets or
submission.

## Where the principles come from

These are the ideas the system follows. The attributions are to published
work; nothing here claims to speak for anyone.

- **Questions before observation.** Karl Popper, *Conjectures and
  Refutations* (1963), ch. 1: observation needs a chosen object, a task and
  a problem. This is the seed file.
- **Prequential judgement.** A. P. Dawid, "Statistical theory: the
  prequential approach", *JRSS A* 147 (1984): judge a forecaster only on
  forecasts made before the outcome. This is the scoring.
- **"Not yet."** Carol Dweck, *Mindset* (2006): ability grows with effort
  and feedback, and mistakes are information. Here that means a `not_yet`
  status, a `regressed` status that sends a learner back to learning rather
  than hiding its failure, and recorded expected failures (the strong-sag
  case) kept visible until they are fixed.
- **Learning from outcomes, and explaining it.** Donald Michie's MENACE
  (1961) learned noughts and crosses from win/loss outcomes alone; the
  world model's count-based Gamma posteriors are the same idea in
  continuous form. Michie's criteria for machine learning (1988) ask more:
  *strong* learning gives an account a person can read, and *ultra-strong*
  learning improves the person's own performance. Every status here
  carries an explanation for that reason.
- **Reuse what was computed.** Michie's "memo functions" (*Nature*, 1968):
  keep results rather than recompute them. The precompute queue is its
  operational form, and the depth rule below says how much keeping pays.
- **Grafting from known sources.** Anne McLaren's embryo-transfer and
  chimera work: tissue from a known origin, placed whole, watched until it
  takes. This is Salamander's skill grafting
  (`Intelligence/skill_graft.py`). The fabric is the chimera: one body of
  knowledge from intelligences of different origins.
- **Learning from grounded experience.** David Silver's work (AlphaGo,
  AlphaZero; "Reward is enough", 2021, with Singh, Precup and Sutton; "Welcome
  to the Era of Experience", 2025, with Sutton). Learning comes from the
  system's own stream of experience with grounded outcomes, including
  simulated experience (the discovery twin). In AlphaZero-style training a
  new policy replaced the old only after winning an evaluation; that gate is
  the recommended next step here.
- **Integration without losing differentiation.** Giulio Tononi's
  integrated information theory is about systems whose parts are both
  specialised and richly interdependent. The fabric binds facts across
  intelligences (a derived fact decoheres with its source), while each
  intelligence keeps its own authority. Nothing here computes Φ.
- **Knowing what cannot be learned.** Roger Penrose's arguments on the
  limits of computation (*The Emperor's New Mind*, 1989) concern
  understanding, not mining. The practical lesson taken here is narrower:
  hold proven limits as knowledge. The share law is one. It is tested
  rather than assumed, and learning is not spent against it.
- **How people learn.**
  - Retrieval practice: testing strengthens memory (Roediger and Karpicke,
    2006). Here every outcome re-tests the learner.
  - Forgetting and spacing (Ebbinghaus, 1885): the recent record decays.
  - Calibration, from metacognition research: the coverage check.

## Precompute depth: job churn sets it

Every new job drains the precomputed plan queue. With `d` plans queued, a
window of `W` seconds, and plan build latency `l` (90th percentile and
mean), the seconds lost per window are:

```text
C(d) = max(0, l90 - d * W)  +  lambda_jobs * W * d * l_mean
       executor waiting         planning discarded by new jobs
```

The operating policy picks the `d` that minimises `C`. One more queued plan
saves at most `W` of waiting and costs `lambda_jobs * W * l_mean` of
discarded planning, so extra depth pays only while `lambda_jobs * l_mean < 1`.
In other words, a new job must arrive less often than one plan takes to
build.

With jobs every tens of seconds and plans in milliseconds, the depth is the
wait-free minimum `ceil(l90 / W)`. Only a storm of new jobs with slow
planning pushes the depth lower.

Two things were missing before this change:

- **Plan latency was never measured.** The world model therefore had no data
  to compute a depth from.
- **The policy's depth was never applied to the queue.** The controller's
  reactive rule set it instead: shrink after waste, grow after starvation.

Now plan latency is measured on every build, and in model mode the policy is
the single authority over depth. The old formula also asked for one plan
beyond the wait-free minimum; that extra plan only ever waited to be
discarded.

## Next steps

- **Choosing what to study next:** pick the question whose answer would
  change a decision most (expected information gain), not the one easiest
  to answer.
