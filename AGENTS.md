# Poster Agent Autonomous Operating Policy

## Artifact & Path Policy (MANDATORY for all agents)

1. NEVER write, copy, or save any file outside the project root. This includes
   IDE session folders, agent "brain"/workspace caches, home directories, and
   any other tool's private storage.
2. Never hardcode absolute paths (Windows drive letters like `C:\Users\...` or
   `/home/...`). All paths must be relative to the project root, or come from
   a CLI flag / config value.
3. All pipeline artifacts belong in `runs/{run_id}/`. A pipeline may copy
   final deliverables to a user-specified `--artifact-dir` / config dir ONLY.
4. Agent instruction files must never instruct you to persist artifacts in
   agent-specific directories.

