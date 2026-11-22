# OpenOrchestrate Playbook

Project: **pyne**
Owner: the person running this project
Autonomy: **autopilot**
Chief autonomy: **review**

## The team

- **Chief** (`oo-chief`) — Chief of Staff
- **Ops** (`oo-ops`) — Head of Operations
- **Checker** (`oo-checker`) — Quality Gate
- **Docs** (`oo-spec-1`) — Head of Docs
- **Deploy** (`oo-spec-2`) — Head of Deploy
- **Misc** (`oo-misc`) — General Desk

### Cooperate Identity and Design

_Owns brand identity and product design across the agency._

- **Identity** (`oo-identity`) — Identity Lead
- **Design** (`oo-design`) — Design Lead

## Operating principles

1. One bot, one domain, one name.
2. Rules live in the description, not in memory.
3. A check the bot can run before "done".
4. One front door that routes and never builds.
5. A board, not a group chat.
6. Skill first, routine second, silent when nothing changed.
7. Routines live on their own bot, never on the one you chat with.
8. Approvals expire: allow the action or stop at a draft.
9. Gate on the price of undo.
10. One shared computer is not six security zones.
11. Same answer every time? A script, not a model call.
12. Wake-ups times re-reads is your bill.

## Extras

extras: off.

Optional extras stay off until enabled. List with `oo extras list`. Init shortcut: `oo init --extra modern-web-guidance`.

## Optional skills

The public skill-pack catalog is **off** by default. Prefer `oo extras enable`
when a pack is an OO extra; otherwise `oo skills enable catalog/…`. Never
auto-install on `oo init`. Ask first before a network install.

## The board

Path: `.oo/board.md`

Five statuses: Todo, Working, Blocked, Ready for Review, Done.

A handoff contains: from, to, objective, artifacts, decisions, open questions, next gate.

## Ready for Review

A card in **Ready for Review** means the owner is done and the proof is attached. It is not Done: no checker has accepted it yet. It is not Working: the owner is not editing it. The owner moves it there; the Chief or Ops may move it only to delegate the review or resend it, never to claim the work. No proof, no Ready for Review.

**Delegate a review.** The Chief, Ops, or the card owner may delegate a Ready for Review card. The default reviewer is `oo-checker`, and the reviewer must be a configured checker. Delegation writes the reviewer in `Delegated To` and leaves `Owner` as the author; a board without a `Delegated To` column cannot delegate, so add the column first. Record one note: who delegated, what to check, and where the proof is. One owner per card; a delegation is a handoff, not a second owner.

**Review and Done.** Only a configured checker seat may move a card to Done, and only when the ledger holds a command proof this process ran. That checker must not be the card owner, and when `Delegated To` names a reviewer, only that reviewer may complete it. The companion's review-and-done action calls the same Done guard as the board; it never bypasses it. A checklist, screenshot, hash, or pasted output is context, not Done. If the proof is missing or failing, the checker sends the card back to Working with `FAILED` / `SAW` / `FIX`; after the same failure twice, set Blocked and tell the Chief.

**Resend to Chief.** If the review cannot proceed — wrong scope, a missing decision, or two failed attempts — the checker or the card owner reassigns the card to `oo-chief`, sets Working when a decision is needed or Blocked when work cannot continue, and records the reason on the card. The Chief sees it in the Ready for Review / attention queue, not only in chat.

**Stale RFR.** A card that sits in Ready for Review for more than **2 days** is stale. The standup and board sweep ping the owner, the checker, and the Chief with the card and the exact gap. The Friday receipt reports the stale-RFR count and the oldest card, with the fix: a decision, a reviewer, or a proof. Measure age from the card's `updated` date; a new proof or a status change resets it.

**Attention.** Ready for Review cards come first in `oo status`, the TUI, and the companion. One owner per card. Proof before Done. The companion's delegate-review, review-and-done, and resend-to-Chief actions follow this section; they do not add a second workflow.

**Triage.** An "already done" verdict is valid only when the verdict names a test or command that exercises **the card's exact claim**, and that check passes. A neighbouring capability, a similar-sounding setting, or a line number that happens to match is not evidence. With no such test, the verdict is "needs a check": the card goes to a seat, never to Done. A "blocked" verdict must name the missing external contract, not a feeling. **A checker's FAIL is void unless it quotes the artifact line it rejects.** If the quoted row is not in the artifact, the verdict is unsupported: the card returns to review, not to Working.

## The gate

- Ask first before spending money or buying anything.
- Ask first before changing permissions or logins.
- Ask first before running database migrations or destructive commands.
- Ask first before deploying to production.
- Ask first before deleting data.
- Ask first before messaging people outside my team.

When rules conflict, Ask first wins. Add an Allow rule only after the same action has been approved five times in a row.

## The clock

Routines are enabled. See `.oo/routines/`.

Every routine uses the same frame:

```text
Run at [time] or when [event] happens.
Input: [where it comes from]. Output: [format, location].
If nothing changed since the last run, say nothing.
If something needs me, send one message:
what happened, what you did, what you need from me.
If a step fails, say which step and stop.
Ask me before anything outside [approval list].
```

## Memory

Keep slow facts. Fetch fast ones.

| Place       | Holds                            | Written by     |
| ----------- | -------------------------------- | -------------- |
| Description | The job and the hard rules       | You            |
| Skill       | How to do a repeatable task      | Shared         |
| Memory      | Stable decisions and definitions | Slow to change |
| Live source | Status, price, plan, assignee    | Fetched        |
| Task state  | What this run is doing now       | The board      |

If being wrong about a fact could change an action, fetch it. Do not remember it.

Fix a recurring failure in this order: setup, check, skill or rule, memory.

## Friday receipt

For every routine: runs, passed, needed a human, repeated failures, cost per finished job. Keep, fix, or delete. Ask: would I notice if it disappeared tomorrow?
