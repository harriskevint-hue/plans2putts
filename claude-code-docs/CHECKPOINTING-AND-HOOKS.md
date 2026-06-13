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
- Trying an alternative implementation without losing the working starting point.
- Recovering quickly from a change that broke something.
- Iterating on a feature while keeping a known-good fallback.

## Important limitations
- **Bash-command file changes are NOT tracked.** `rm`, `mv`, `cp` run via the Bash tool
  can't be undone by rewind. Only direct file edits through Claude's editing tools are tracked.
- **External changes not tracked** (manual edits outside Claude Code, other sessions).
- **Not a replacement for Git.** Checkpoints = session-level "local undo." Git = permanent
  history and collaboration. Use both. Commit working states to Git regularly.

---

# PART 2 — HOOKS (automation — advanced)

Hooks are user-defined actions (shell command, HTTP request, MCP tool call, LLM prompt,
or subagent) that run automatically at specific points in Claude Code's lifecycle. They
give DETERMINISTIC control: the action always happens, instead of relying on the model to
choose to do it. Used for: auto-formatting after edits, blocking dangerous/edits to
protected files, running tests automatically, notifications, injecting context, enforcing
project rules.

> KT is a non-programmer; hooks require editing JSON settings and often shell scripts.
> We use them only with a clear, stated reason and KT's sign-off. This section is the
> reference for when that happens.

## Where hooks are configured (scope)
| Location | Scope | Committed/shared? |
|---|---|---|
| `~/.claude/settings.json` | all your projects | no (personal machine) |
| `.claude/settings.json` | this project | yes (commit to repo) |
| `.claude/settings.local.json` | this project | no (gitignored) |
| Managed policy settings | org-wide | admin-controlled |
| Plugin `hooks/hooks.json` | when plugin enabled | yes (with plugin) |
| Skill/agent frontmatter | while component active | yes |

Run `/hooks` to browse configured hooks (read-only; edit JSON or ask Claude to change).
Set `"disableAllHooks": true` to turn all off without removing them.

## Configuration shape (three levels of nesting)
1. A **hook event** (e.g. `PreToolUse`, `PostToolUse`, `Stop`).
2. A **matcher group** to filter when it fires (e.g. only the `Bash` tool, or `Edit|Write`).
3. One or more **hook handlers** (the command/HTTP/etc. that runs).

Example — run Prettier after every file edit (`.claude/settings.json`):
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": "jq -r '.tool_input.file_path' | xargs npx prettier --write" }
        ]
      }
    ]
  }
}
```

## Hook events (when each fires)
Once per session: `SessionStart`, `SessionEnd`, `Setup`.
Once per turn: `UserPromptSubmit`, `UserPromptExpansion`, `Stop`, `StopFailure`.
Every tool call: `PreToolUse`, `PermissionRequest`, `PermissionDenied`, `PostToolUse`,
`PostToolUseFailure`, `PostToolBatch`.
Other: `Notification`, `MessageDisplay`, `SubagentStart`, `SubagentStop`, `TaskCreated`,
`TaskCompleted`, `TeammateIdle`, `InstructionsLoaded`, `ConfigChange`, `CwdChanged`,
`FileChanged`, `WorktreeCreate`, `WorktreeRemove`, `PreCompact`, `PostCompact`,
`Elicitation`, `ElicitationResult`.

Most useful for a project like this:
- `PostToolUse` (matcher `Edit|Write`) — format or lint after edits.
- `PreToolUse` (matcher `Bash`) — block dangerous commands before they run.
- `Stop` — verify work (e.g. tests pass) before Claude finishes a turn.
- `Notification` — desktop alert when Claude needs input.
- `SessionStart` (matcher `compact`) — re-inject context after compaction.

## Matcher rules
- `"*"`, `""`, or omitted = match all.
- Only letters/digits/`_`/`|` = exact string or `|`-separated list (`Edit|Write`).
- Any other character = JavaScript regex (`mcp__memory__.*` matches all tools from the
  `memory` MCP server; `.*` suffix is required to match a whole server).
- The `if` field (permission-rule syntax like `Bash(git *)` or `Edit(*.ts)`) filters more
  narrowly by tool name AND arguments, so the hook process only spawns on a match.

## Hook input/output (command hooks)
- Input: event JSON arrives on **stdin** (`session_id`, `cwd`, `hook_event_name`,
  `tool_name`, `tool_input`, etc.). Each event documents its own extra fields.
- Output via exit code:
  - **Exit 0** = no objection; action proceeds (normal permission flow still applies).
    For `UserPromptSubmit`/`UserPromptExpansion`/`SessionStart`, stdout is added to Claude's context.
  - **Exit 2** = blocking error; stderr is fed back to Claude as feedback. Effect depends
    on event (`PreToolUse` blocks the tool, `UserPromptSubmit` rejects the prompt, etc.).
    NOTE: only exit 2 blocks — exit 1 is treated as a non-blocking error and the action proceeds.
  - **Any other code** = non-blocking error; action proceeds; stderr noted in transcript.
- For finer control, exit 0 and print a JSON object to stdout instead. Do not mix: JSON is
  ignored if you exit 2.

### Structured JSON output (key fields)
- Universal: `continue` (false = stop entirely), `stopReason`, `suppressOutput`,
  `systemMessage`, `terminalSequence` (desktop notification/bell, no `/dev/tty`).
- `PreToolUse` decision (inside `hookSpecificOutput`): `permissionDecision` =
  `"allow"` | `"deny"` | `"ask"` | `"defer"`, plus `permissionDecisionReason`,
  optional `updatedInput` (rewrite tool args), `additionalContext`.
  Precedence when multiple hooks disagree: deny > defer > ask > allow.
- `PostToolUse`: top-level `decision: "block"` + `reason`; `additionalContext`;
  `updatedToolOutput` (only changes what Claude sees — tool already ran).
- `Stop`/`SubagentStop`: `decision: "block"` + `reason` (keeps Claude working), or
  `hookSpecificOutput.additionalContext` for non-error guidance. `stop_hook_active`
  guards against infinite loops; Claude Code overrides after 8 consecutive blocks.
- `PermissionRequest`: `hookSpecificOutput.decision.behavior` = `"allow"`/`"deny"`,
  optional `updatedInput`, `updatedPermissions`.
- `additionalContext`: injects a string into Claude's context as a system reminder.
  Write it as factual statements ("This repo uses bun test"), not imperative commands,
  to avoid prompt-injection defenses. For static rules, prefer CLAUDE.md instead.

## Five hook handler types
- `command` — run a shell command (most common). Exec form (`args` present, no shell,
  no quoting needed — best for path placeholders) vs. shell form (`args` absent, supports
  pipes/`&&`). On Windows set `"shell": "powershell"` to use PowerShell.
- `http` — POST event JSON to a URL; response body uses the same JSON output format.
  Cannot block via status code alone; return 2xx with a deny decision to block.
- `mcp_tool` — call a tool on an already-connected MCP server.
- `prompt` — single-turn LLM (Haiku by default) returns `{"ok": true/false, "reason": ...}`.
  For judgment calls rather than deterministic rules.
- `agent` — EXPERIMENTAL; spawns a subagent with tool access (Read/Grep/Glob, up to 50
  turns) to verify conditions before deciding. Prefer command hooks for production.

## Path placeholders
- `${CLAUDE_PROJECT_DIR}` — project root.
- `${CLAUDE_PLUGIN_ROOT}` — a plugin's install dir.
- `${CLAUDE_PLUGIN_DATA}` — a plugin's persistent data dir.
Prefer exec form (`args`) when referencing these; in shell form, wrap in double quotes.

## Async hooks
Add `"async": true` to a command hook to run it in the background without blocking Claude
(e.g. long test suites). Async hooks can't block or return decisions; output is delivered
on the next turn via `additionalContext`. `asyncRewake: true` wakes Claude on exit code 2
even when idle.

## Security (important)
- Hooks run with YOUR full user permissions — they can modify/delete any file you can.
- Review and test every hook before adding it.
- Quote shell variables (`"$VAR"`), block path traversal (`..`), use absolute paths,
  skip sensitive files (`.env`, `.git/`, keys).
- A `PreToolUse` deny hook fires before permission-mode checks, so it can enforce policy
  even in bypass mode. But a hook returning `"allow"` does NOT override deny rules from
  settings — hooks can tighten, not loosen.

## Common ready-to-use patterns
- **Notify when Claude needs input** — `Notification` hook running `osascript`/`notify-send`/PowerShell.
- **Auto-format after edits** — `PostToolUse` + `Edit|Write` + Prettier.
- **Block edits to protected files** — `PreToolUse` + `Edit|Write` + a script that exits 2
  when the path matches `.env`, `package-lock.json`, `.git/`, etc.
- **Re-inject context after compaction** — `SessionStart` + matcher `compact` + an echo of
  key conventions (or use CLAUDE.md for static context).
- **Auto-approve a specific prompt** — `PermissionRequest` + narrow matcher + JSON
  `decision.behavior: "allow"`. Keep the matcher narrow; never `.*`.

## Debugging hooks
- `/hooks` — confirm a hook is registered under the right event.
- Test manually: `echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | ./my-hook.sh; echo $?`
- `claude --debug-file /tmp/claude.log` then `tail -f /tmp/claude.log` for full execution detail.
- Common gotchas: matcher case-sensitive; script not executable (`chmod +x`); `jq` not
  installed; shell profile printing text that corrupts JSON output (guard echoes with
  `if [[ $- == *i* ]]`); Stop hook hitting the 8-block cap (check `stop_hook_active`).
