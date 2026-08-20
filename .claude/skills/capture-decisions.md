# Skill: capture-decisions

Capture technical decisions made since the last DECISIONS.md entry and write new entries to that file.

## Steps

### 1. Find the anchor point

Read `.claude/DECISIONS.md`. The entries are ordered newest-first. Find the most recent entry's:
- **Date** (in the `## YYYY-MM` heading)
- **Commit ID** if one is present (look for lines like `**Commit**: \`abc1234\``)

If no commit ID is recorded, use the date to bound the git log and transcript queries.

### 2. Collect commits since the anchor

Run:
```bash
git log --oneline --since="YYYY-MM-01"
```
or, if a commit ID was found:
```bash
git log --oneline <commit_id>..HEAD
```

Exclude pure chore commits (formatting, typo fixes, dependency bumps with no rationale). Focus on commits that changed behaviour, added features, fixed non-obvious bugs, or made trade-off decisions.

### 3. Read the diffs for each significant commit

For each commit worth capturing:
```bash
git show <commit_id> --stat
git show <commit_id>
```

Read enough to understand **what changed**. Note what you still cannot answer from the diff alone — specifically: *why this approach rather than an alternative?*

### 4. Find relevant Claude conversation transcripts

Transcripts for this project are stored as JSONL files in:
```
~/.claude/projects/-Users-shmiggit-Documents-projects-luxdem/
```

**Find sessions that overlap the commit window:**
```bash
ls -lt ~/.claude/projects/-Users-shmiggit-Documents-projects-luxdem/*.jsonl
```
Sessions modified since the anchor date are candidates.

**Extract user and assistant messages from each candidate session:**
```bash
python3 -c "
import json, sys
for line in open(sys.argv[1]):
    obj = json.loads(line)
    if obj.get('type') in ('user', 'assistant'):
        role = obj['type']
        content = obj.get('message', {}).get('content', '')
        if isinstance(content, list):
            content = ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
        if content.strip():
            print(f'[{role}] {content[:300]}')
" ~/.claude/projects/-Users-shmiggit-Documents-projects-luxdem/<session>.jsonl | head -200
```

**What to look for in transcripts:**
- User messages explaining a constraint ("I want to avoid X", "the reason is Y", "this is a one-off batch")
- Assistant messages presenting alternatives and trade-offs that the user chose between
- User corrections or redirections that reveal a preference or requirement
- Any explicit "why" phrased by either side

### 5. Resolve gaps by asking the user

For each commit or change where the **why** is still unclear after reading both the diff and the transcripts, ask the user directly:

> "Commit `<hash>` changed `<files>` — I can see what changed but not why this approach was chosen over alternatives. Can you explain the reasoning?"

Do not guess at motivations or fill in a vague "why" that isn't supported by evidence. A short honest note ("reason not recorded") is better than a fabricated rationale.

### 6. Write new DECISIONS.md entries

Prepend new sections to `.claude/DECISIONS.md` using this format:

```markdown
## YYYY-MM — Short title of the decision

**Commit**: `<short_hash>` — "commit message" (`git show <short_hash>`)

**Decision**: One sentence stating what was chosen or changed.

**Why**: The motivation — constraint, bug, performance issue, trade-off. Be specific. Reference the problem it solved, not just what was done.

**Alternatives considered** *(omit if none were surfaced)*: What else was evaluated and why it was rejected.

**Implications**: What future work this enables, constrains, or depends on. Flag anything that will surprise a future reader of the code.

---
```

If multiple commits belong to the same decision, list all hashes. If the reason came from a transcript rather than a commit message, note it implicitly in the **Why** — no need to cite the session ID.

### 7. Confirm before writing

Summarise the proposed entries to the user and confirm before writing to the file, unless the user already said "just write it."

## Notes

- Do not duplicate entries already in DECISIONS.md.
- Omit commits whose purpose is self-evident from the code and adds no non-obvious rationale.
- Keep each entry concise — the **Why** is the most important field; it is what will not be recoverable from git later.
- If the repo has no git history (e.g. fresh clone with no commits), skip steps 2–3 and rely on transcripts and user input only.
- Transcripts can be large. Read the first 200 lines to get context; deep-read only if a specific decision needs clarification.
