---
name: parallax
description: Keep the registry of research leads of a project (leads.yaml, INBOX.md, journal) that Parallax displays and edits. Use it whenever a research session is opened, closed or triaged, or when a new idea comes in ("IDEA: …").
---

# Parallax — guide for agents

> If the project repository contains an `AGENTS.md`, its rules take precedence over this guide (it is what non-Claude agents read).

Parallax keeps the state of a research project in **a single data file**, `leads.yaml`. It renders a self-contained HTML page from it: importance × chance matrix, tree, journal + inbox, task list, sortable list, and project-specific views.

The researcher must see at a glance what has been explored, what matters, and what is likely to work. They must also be able to drop an idea on you without friction. **Your role:** keep the registry exact and up to date, and never let a conversation lose its thread.

## Files (in the project repository)

| File | Role | Who writes |
|---|---|---|
| `leads.yaml` | registry: project, leads, journal | agents, validated by the human |
| `INBOX.md` | raw ideas, one `- ` bullet each | the human or an agent, untriaged |
| `notes/…` | detailed notes, proofs | agents and the human |
| `parallax.html` | **generated** snapshot, never edit by hand | `parallax.py build` |
| `*.js` listed in `project.extensions` | project-specific views | agents |

From the registry's folder:

```bash
python3 <module>/parallax.py serve           # open Parallax (browser, editable)
python3 <module>/parallax.py build           # write the parallax.html snapshot
python3 <module>/parallax.py check           # validate without writing
python3 <module>/parallax.py check --git     # + refuse leads or journal entries deleted since HEAD
```

Rebuild `parallax.html` **after every change** to the registry or the inbox, not only when closing a session.

Recommended guardrail: a versioned `pre-commit` hook (`.githooks/pre-commit`, enabled with `git config core.hooksPath .githooks`) that runs `parallax.py check --git`.

`<module>` is the folder of this SKILL.md. Dependency: `python3 -m pip install --user pyyaml`. **Always** run `check` after changing the registry and fix every error. Fix warnings too, unless the human chose to keep them.

## Schema of `leads.yaml`

```yaml
project:
  title: …                      # required
  description: …                # LaTeX $…$ accepted everywhere
  inbox: INBOX.md               # default
  output: parallax.html         # default
  owner: A.B.                   # the human in charge; author of journal entries created from Parallax
  top: 3                        # number of "Do now" cards
  views: [matrix, tree, journal, list]   # tab order; extension ids allowed
  extensions: [views/my_view.js]         # paths relative to the registry
  scales:                       # optional labels
    importance: {1: …, 2: …, 3: …}
    chance: {1: …, 2: …, 3: …}
statuses:                       # optional: override or add {label, color, active, ring}
leads:
  - id: d1-karlin               # required: lower case, digits, dashes; never changes
    title: …                    # required
    short: …                    # short label (matrix, breadcrumbs)
    type: lead                  # lead (default) | theme (grouping, no ratings)
    parent: <id>                # position in the tree
    status: idea                # idea | ongoing | done | stopped (blocked, paused or abandoned: say which at the start of obstacle)
    importance: 2               # 1..3
    chance: 2                   # 1..3
    effort: M                   # S (hours) | M (days) | L (weeks)
    validated: false            # false until the human has validated the ratings
    why: …                      # one-sentence justification of the ratings
    summary: …
    established: [ … ]
    obstacle: …
    next: …                     # next concrete action (required while active)
    stop: …                     # stopping criterion (required for idea/ongoing)
    docs: [relative paths]      # "notes/x.md#Section title", "notes/y.pdf#page=4"
    tags: [ … ]
    updated: 2026-11-23
    assignee: claude            # agent working on the lead (optional)
    pinned: true                # the human's choice: forced into "Do now"
    todo:                       # the lead's tasks ("Tasks" view)
      - {text: …, done: false, who: A.B.}   # who: optional (agent or human) — badge and filter in "Tasks"
    # any other field is kept, shown on the card, and readable by extensions
journal:
  - {date: 2026-11-23, type: result, lead: d1-karlin, author: claude, text: …}
    # type: result | decision | stop | deletion | idea | note
    # "deletion": a real deletion of a lead by the human (duplicate, mistake); the --git guardrail requires it
```

**French registries.** Registries written with the French schema of Parallax 2 (`projet`, `pistes`, `statut: en-cours`, `prochaine`, `arret`, `texte`…) are read transparently and written back in French. Use the language the file already uses.

**Displayed priority** = importance × chance (1 to 9). Ties are broken by the smallest effort, then by the most recent update. The "Do now" cards show pinned leads, then the active leads (`idea`, `ongoing`) of highest priority.

## Rules

1. **Ratings belong to the human.**
   - You propose `importance`, `chance` and `effort` with a `why`, and set `validated: false`.
   - You only set `validated: true` on explicit confirmation.
   - Be calibrated: `chance: 3` means "I expect this to work". No complacent optimism.
2. **A lead is never deleted.**
   - A dead end becomes `stopped`, with the reason in `obstacle`, plus a journal entry `type: stop`.
   - The history of dead ends prevents exploring them again.
3. **Every status change produces a journal entry**, dated and linked to the lead. Update `updated` too.
4. **An active lead always has a concrete `next` action**, doable in one session, and a `stop` criterion.
5. **The `id` is stable.** Journal links and URLs depend on it.
6. **What is established is checked.** An `established` item is a fact (proof, computation, verified reference), never a conjecture. Conjectures go into `summary`.
7. **No duplicates.** Before creating a lead, check whether an existing one covers the idea. If so, enrich it or create a sub-lead with `parent`.
8. **Share the work.** Whenever you start a task, propose one relevant, complementary thing for the human to do meanwhile (something that does not wait for your result and that a human does better), and record shared tasks in `todo` with `who`.

## Editing by the human

**Documents and anchors.** Each `docs` entry is a path relative to the registry, optionally followed by an anchor: `notes/x.md#Explicit rule` opens Parallax's built-in reader (rendered Markdown, MathJax formulas, including ```` ```latex ```` blocks) and scrolls to the first heading that contains this text (accents and case ignored); `notes/y.pdf#page=4` opens the PDF at page 4. Use the most precise anchor you can: the section, the page of the lemma. `check` reports a Markdown anchor that matches no heading, or a PDF anchor that is not `page=N`. Quote entries that contain an anchor in the YAML.

`parallax.py serve` starts a small local server (`127.0.0.1`, session token) and opens Parallax in any browser. The human edits cards, ratings, tasks and pins, creates/stops/deletes leads, triages the inbox, adds journal notes, and commits. Parallax validates before writing (same rules as `check --git`), adds journal entries (author = `project.owner`), rewrites the registry in js-yaml format, and refuses to write if a file changed on disk since it was loaded.

Consequence for you: re-read the registry and `INBOX.md` right before changing them; keep changes short.

## Rituals

The human may call them by name, or you propose them at the right time.

### open <id>
1. Read the registry, the lead's card and its documents.
2. Answer in 5 lines at most: goal, established, obstacle, next action, stopping criterion; then the work split (what you take, what the human can do meanwhile).
3. If the id is ambiguous or missing, show the 3 top-priority leads and ask which one to open.
4. For the whole session, **stay on this lead**. Any off-topic idea goes into `INBOX.md` (see *idea*), then back to the topic.

### idea <text> (or "IDEA: …" in the conversation)
1. Append `- [YYYY-MM-DD] <text>` at the end of `INBOX.md`, verbatim, without rewording or triaging.
2. Rebuild `parallax.html`, confirm in one line, then resume exactly where you were.

### triage
For each bullet of `INBOX.md`, propose one of:
- **attach** to an existing lead (added to `summary`, `established` or `next`);
- **new lead**, with an id, a parent, proposed ratings (`validated: false`), a `next` and a `stop`;
- **reject**, with a journal entry `type: idea` saying why.

Present all proposals at once, as a table. Apply what the human validates, remove the processed bullets from `INBOX.md`, run `check`, then rebuild.

### close
1. Update the open lead's card: `established`, `obstacle`, `next`, `status`, `updated`, and its `todo` (tick yours, add the next ones with `who`).
2. Add 1 to 3 journal entries about what was established or decided, not what was discussed.
3. If the results change the chances of other leads, propose new ratings with `validated: false`.
4. Run `parallax.py check --git`, rebuild `parallax.html` and, in a git repository, commit: `git commit -am "close: <id> — <summary>"`.
5. End with two lines: what changed and the next action; what the human can do before the next session.

### review (from time to time)
- List `ongoing` leads not updated for more than 3 weeks.
- Spot leads whose stopping criterion seems reached.
- Spot ratings still `validated: false`.
- Propose changes; apply nothing without agreement.

## Writing an extension (project-specific view)

A JS file listed in `project.extensions` is inserted into the page. API:

```js
Parallax.view({id: "my-view", title: "My view", icon: "list", render(el, ctx) { el.innerHTML = "…"; }});
Parallax.overviewSection(ctx => "<h2 class='sec'>…</h2>…");  // section added to the Overview
Parallax.detailSection((lead, ctx) => "<div class='k'>…</div>…");  // section added to a lead's card ('' = nothing)
Parallax.hideFields(["my_field"]);                         // do not show this raw field on the card
```

`ctx` contains:
- `data`: the normalized registry, with `project`, `leads`, `journal`, `inbox`, `statuses`, `scales`;
- helpers: `visibleLeads()` (after filters and search), `select(id)`, `status(id)`, `esc(s)`, `text(s)` (escapes, keeps LaTeX), `priority(p)`, `chain(id)`, `typeset(el)`, `icon(name)`.

Extension-specific data goes into free fields of the leads, or under a key of `project`. Example: the One Bit project's "coverage on an axis" view reads `project.axe` and the `couverture` field of each lead.
