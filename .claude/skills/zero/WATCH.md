# PR Watch mechanics (GitHub + Azure DevOps)

How zero watches **your own open PRs** for new activity (a reviewer comment, a
new commit pushed by someone else, or a review verdict), notifies you, and hands
the feedback to `review-pr`. This file is the concrete procedure; `SKILL.md`
defines when WATCH runs.

zero is the actor — it runs these commands and reads the output. Everything
degrades gracefully: a missing CLI/token for one platform never blocks the other,
and a failed notification channel never blocks the apply step.

## Config & prerequisites

Watch only acts on PRs **authored by you**. Identify "you":
- GitHub: the login that owns the token / `gh auth status`.
- Azure DevOps: `az account show` / the PAT's user.

Auth (read from env only — never print or commit a token):
| Platform | Needs | Check |
|----------|-------|-------|
| GitHub | `gh` on PATH **or** `GH_TOKEN`/`GITHUB_TOKEN` | `command -v gh`; `[ -n "$GH_TOKEN$GITHUB_TOKEN" ]` |
| Azure DevOps | `az` + `azure-devops` ext + `AZURE_DEVOPS_EXT_PAT` | `command -v az`; `az extension show -n azure-devops` |

Notification:
| Channel | Mechanism |
|---------|-----------|
| Email | `python .claude/skills/zero/notify_email.py "<subject>" "<body>"` (SMTP creds via env; exit 2 = no creds → skip) |
| Desktop | the `PushNotification` tool (zero calls it directly) |

If a platform has no auth, zero **says so** and watches only the platform(s) it can.

## State (so we only notify on NEW activity)

`dev/memory/zero/pr_watch_state.json` (gitignored). One entry per watched PR,
keyed `"<platform>:<repo>:<pr_number>"`:

```json
{
  "github:bijayshrestha0817/recover-folder-structure:42": {
    "title": "Add throttling",
    "last_commit_sha": "abc1234",
    "last_comment_id": 99887766,
    "last_review_id": 55443322,
    "last_checked": "2026-06-01T12:00:00Z"
  }
}
```

`dev/memory/zero/PR_WATCH.md` is the human-readable log (one dated block per poll:
what was new, who, what zero did). zero appends to it every poll.

**New activity** = any of: a comment id newer than `last_comment_id`, a review id
newer than `last_review_id`, or a head commit whose author is **not you** and whose
sha ≠ `last_commit_sha`. On first sighting of a PR, record state silently (no
notification — there is no "previous" to diff against) unless it already has
unaddressed reviewer comments.

## GitHub — list my PRs and detect new activity

```bash
OWNER_REPO=$(git remote get-url origin | sed -E 's#.*github.com[:/]##; s#\.git$##')
OWNER=${OWNER_REPO%%/*}; REPO=${OWNER_REPO##*/}

# My open PRs (gh)
gh pr list --author "@me" --state open --json number,title,headRefName,baseRefName,url

# Per PR <n>: comments / reviews / commits
gh api "repos/$OWNER/$REPO/pulls/<n>/comments" --paginate   # inline: id, path, line, body, user.login, created_at
gh api "repos/$OWNER/$REPO/pulls/<n>/reviews"  --paginate   # id, state, body, user.login, submitted_at
gh api "repos/$OWNER/$REPO/issues/<n>/comments" --paginate  # general discussion
gh api "repos/$OWNER/$REPO/pulls/<n>/commits"  --paginate   # sha, commit.author, author.login
```

curl fallback (token in env) is in `../review-pr/GITHUB.md` (§2–3) — reuse it; do
not duplicate. Unresolved-thread detection (GraphQL) also lives there.

## Azure DevOps — list my PRs and detect new activity

```bash
# One-time: az devops configure --defaults organization=https://dev.azure.com/<org> project=<project>
az repos pr list --creator @me --status active \
  --query "[].{id:pullRequestId,title:title,src:sourceRefName,tgt:targetRefName}" -o json

# Per PR <id>:
az repos pr show --id <id> --query "lastMergeSourceCommit.commitId"        # head commit
az devops invoke --area git --resource pullRequestThreads \
  --route-parameters project=<project> repositoryId=<repo> pullRequestId=<id> \
  --api-version 7.1 -o json    # threads[].comments[]: id, content, author.displayName, publishedDate
```

A thread/comment is "new" when its id/publishedDate is past `last_comment_id` /
`last_checked`. A commit is someone-else's when `commit.author` ≠ you.

## The poll (one pass)

For each platform that has auth:
1. List my open PRs.
2. For each PR, fetch comments + reviews + commits; compute the **new-activity** set
   against `pr_watch_state.json`.
3. Update the PR's state entry (`last_*` ids/sha, `last_checked`).

Collect all PRs that gained new activity this pass.

## Notify (email + desktop, both)

For each PR with new activity, build one short message:

```
PR #<n> "<title>" (<platform>) has new activity:
- <reviewer> commented on <file>:<line>: "<first line of comment>"
- <reviewer> requested changes
- new commit <sha> by <author>
<url>
```

Then notify on **both** channels (a failure on either is logged, not fatal):
- Email: `python .claude/skills/zero/notify_email.py "zero: PR #<n> has new feedback" "<message>"`
  (exit 2 → no creds, skip email and say so).
- Desktop: call the `PushNotification` tool with the same one-line summary.

## Apply (delegated, **wait-to-push** — never auto-push)

For each PR whose new activity includes **reviewer comments or a change request**:
1. Make sure the PR's branch is checked out (`git fetch` + checkout `headRefName`).
2. Invoke **`review-pr <n> --no-push`** — it combines auto-review + the human
   comments, applies fixes across the layers, and verifies (pytest + pre-commit),
   but **does not push or reply** (that is the `--no-push` contract).
3. Report to the user: what was applied, the verification result, and the exact
   command to ship (`review-pr <n>` without `--no-push`, or `commit-and-push`).
   **Pause for approval before any push/reply** — this is the chosen autonomy level.

New commits with **no** reviewer comments → notify only (nothing to implement).

## Scheduling (the recurring poll)

On-demand is just `zero watch`. For the background poll, register a routine with
the `schedule` skill (or `/loop`) that runs `zero watch` every N minutes, e.g.:

```
/schedule create --name "zero-pr-watch" --cron "*/15 * * * *" --prompt "zero watch"
```

The scheduled run does the poll + notify automatically; it still **stops before
pushing** and leaves the apply result for you to approve. Turn it off with the
`schedule` skill (delete the routine) or `zero watch stop`.

## Failure handling
- Missing CLI/token for a platform → skip that platform, watch the other, tell the user.
- A notify channel fails → log it, try the other channel, never block the apply step.
- Any API call fails mid-poll → record what succeeded, report the failure, do not
  corrupt `pr_watch_state.json` (write it only after a clean pass per PR).
- Never push or resolve threads in WATCH mode without explicit approval.
