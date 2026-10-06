---
name: discovery
description: Sort freeform discovery notes typed during a stakeholder call into the discovery-notes template, without inventing anything, and list the sections still empty. Use after (or midway through) the discovery conversation, e.g. "/discovery" or "/discovery docs/discovery-raw.md".
argument-hint: "[raw notes file, default docs/discovery-raw.md]"
---

# Discovery $ARGUMENTS

Turn the raw notes into `docs/discovery-notes.md`, the input to `/plan-create-prd`. You are a clerk: you sort,
you don't author.

## Inputs

- Raw notes: `$ARGUMENTS`, or `docs/discovery-raw.md` if empty. Stop and say so if it's missing or has no notes.
- Target structure: `docs/templates/discovery-notes.md`. Follow its headings exactly, in order.

## Tags in the raw file

- `?` at line start → **Open questions** as `- [ ] …`
- `A:` at line start → wherever it fits, suffixed `ASSUMPTION`
- `"` at line start → verbatim quote; put it in **2. Evidence** (and also where its content fits, if obvious)
- Untagged → the section it answers. Text after `Brief:` → the **Scenario** blockquote, verbatim.

## Rules

1. **Never invent.** Every bullet you write traces to a raw line. Keep the stakeholder's wording; fix only typos
   and fragments enough to read. No added numbers, targets, or conclusions.
2. If you place a line by inference (it implies an answer rather than stating it), mark it `ASSUMPTION`.
3. One raw line may land in two sections if it clearly answers both; don't split hairs otherwise.
4. Lines that fit no section go under a final `## Unsorted` section. Never drop a line.
5. Empty sections keep their heading and question, with the answer bullet `- (not discussed)`.
6. Drop the template's instruction paragraph at the top; keep the `# Discovery notes — <scenario>` title with the
   scenario name filled in if the brief names it.

## Output

1. If `docs/discovery-notes.md` exists, ask before overwriting it. Never modify the raw file.
2. Write `docs/discovery-notes.md`.
3. Reply in chat with only:
   - **Gaps:** the empty sections, each with the one question worth asking now (from the template's prompts).
     Flag the hypothesis's WRONG condition first if missing; `/plan-create-prd` insists on it.
   - **Assumptions:** count, and any you made by inference (not tagged `A:`).
   - **Unsorted:** count of lines, if any.
   - Next step: `/plan-create-prd <one-line idea> · docs/discovery-notes.md`
