# Claude Code Reference — Checkpointing & Hooks

Part of the ShadesCaddie repo's `claude-code-docs/` reference bundle. Distilled from the
official Anthropic Claude Code documentation. This file covers two advanced topics:
**checkpointing** (undo/rewind, immediately useful) and **hooks** (automation, advanced).
The navigator reviews the relevant part of this file before writing any Claude Code
instruction that touches these features.

---

# PART 1 — CHECKPOINTING (undo / rewind)

Claude Code automatically tracks Claude's file edits, so you can undo changes and return
to a previous state. This is the safety net that makes ambitious changes safe.

## How it works
- Every user prompt creates a checkpoint automatically.
- Checkpoints persist across sessions (available in resumed conversations).
- Cleaned up with sessions after 30 days (configurable).

## Rewind menu
Run `/rewind`, or press `Esc` twice when the prompt input is empty, to open it. (If the
input has text, double-Esc clears it instead; the cleared text is saved to history.)

The menu lists each prompt you sent. Pick a point, then choose:
- **Restore code and conversation** — revert both to that point.
- **Restore conversation** — rewind the conversation, keep current code.
- **Restore code** — revert file changes, keep the conversation.
- **Summarize from here** — compress this message + everything after into a summary (free context; discard a side discussion, keep early context).
- **Summarize up to here** — compress everything before this message (keep recent work in full detail).
- **Never mind** — back out with no changes.

## Restore vs. summarize
- **Restore** undoes state (code, conversation, or both).
- **Summarize** compresses part of the conversation into an AI summary WITHOUT changing
  files on disk. Original messages are kept in the transcript so Claude can still
  reference them. Similar to `/compact`, but targeted to one side of a chosen message.

## When checkpointing helps KT's project
- Trying an alternative implementation without losing the working starting
