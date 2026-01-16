# Sharing Skills and MCP (Quick Guide)

## Skills (repo-shared)

Use `.claude/skills/` in this repo.
Each skill lives at `.claude/skills/<skill-name>/SKILL.md`.

Steps:
1) Add skill files under `.claude/skills/`.
2) Commit to repo so everyone gets the same skill set.
3) Other agents should load skills from repo before starting a task.

Notes:
- Skills are repo-scoped. Keep them small and focused.
- If your CLI does not auto-load repo skills, point it to `.claude/skills/`.

## MCP (machine-scoped)

MCP config is local to each machine/CLI.
It is NOT shared by git by default.

Steps:
1) Each teammate adds the MCP server to their local MCP config.
2) Use the same server names across the team.

Recommendation:
- Keep a short list of required MCP servers in this file.

## Copy MCP from another teammate

1) Ask them for their MCP server block (name + command + args).
2) Add the same block to your local MCP config.
3) Restart your CLI so it reloads the MCP list.

## Required MCP servers (edit as needed)

- (none)
