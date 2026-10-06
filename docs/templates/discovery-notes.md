# Discovery notes — <scenario>

Fill this in **while talking to the stakeholder** (minutes ~10–20). Each block maps to a section of the PRD
that `/plan-create-prd` writes, so these notes *are* the PRD interview: pass this file in as its reference doc
and it only asks about gaps. Pick 5–6 questions, not all. Write answers as they're said; mark guesses
`ASSUMPTION`.

Save as `docs/discovery-notes.md`, then see `docs/runbook-kickoff.md` step 2. Usually you don't fill this by hand:
type into `docs/discovery-raw.md` during the call and `/discovery` writes this file from it.

---

## Scenario (paste the brief verbatim)

>

## 1. Problem → *Problem Statement*

- Who is the end user (a role, not "users")? What do they do today without this?
  -
- What does it cost when they get it wrong or slow today?
  -

## 2. Evidence → *Evidence*

- What tells us this is real: a quote, a ticket theme, a number? Or is it an assumption?
  -

## 3. Why build it → *Thesis*

- Why now? Why would they switch from how they cope today?
  -

## 4. The bet → *Hypothesis*

- What would the user do differently if this works? What one signal says "it's working"? What says "it isn't"?
  - RIGHT if:
  - WRONG if:

## 5. User and job → *Target User & JTBD*

- When does the user reach for this (the trigger)? Who is it explicitly **not** for?
  - When … I want to … so I can …
  - Not for:

## 6. Smallest proof → *MVP*

- What is the one end-to-end question flow that, if it works, proves the idea? What's Release 2?
  - MVP:
  - Release 2:

## 7. Success → *Success Metrics*

- What one metric says their life got easier? (metric · target · how measured)
  -

## 8. Out of scope → *Non-goals*

-

## 9. Constraints → feed `/plan-architecture` (not the PRD)

- **Data:** format, volume, update frequency, owner. May we use synthetic data for the prototype?
  -
- **Cost of a wrong answer:** sets guardrail strictness and whether every answer needs a citation.
  -
- **PII / regulatory:** HIPAA, FINRA, internal-only? Sets redaction and hosting.
  -
- **Audience and latency:** internal or client-facing? How fast must it answer?
  -
- **Trust:** what makes them use it: citations, confidence, escalation to a human?
  -
- **Existing systems:** must it sit next to something, or is greenfield fine today?
  -

## Open questions → *Open Questions*

- [ ]
