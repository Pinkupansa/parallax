# Parallax

A high-altitude overview of a research project, for a human and their AI agents: a YAML registry of research leads (`leads.yaml`), an inbox of raw ideas (`INBOX.md`), an append-only journal, and a local web interface to see and edit all of it.

Two points of view — the human's and the agents' — give depth.

```bash
python3 -m pip install --user pyyaml
python3 parallax.py serve example/leads.yaml   # opens Parallax in the browser, editable
python3 parallax.py check example/leads.yaml   # validate (--git: guardrails against the last commit)
python3 parallax.py build example/leads.yaml   # self-contained, read-only HTML snapshot
```

Python ≥ 3.8 and PyYAML. No other dependency: the interface is a single HTML file (MathJax from a CDN, optional).

## How it works

Parallax has three levels.

1. **Agent behaviour (`SKILL.md`).** The skill file defines how AI agents maintain the project: the schema of the registry, the rules they follow (ratings are proposed by agents and validated by the human; leads are stopped, not deleted; the journal is append-only), and a few rituals (`open`, `idea`, `triage`, `close`, `review`). When an agent starts a task, it also proposes a task for the human that can be done in parallel, and both are recorded in the lead's task list.

2. **Repository structure (maintained by the agents).** The state of the research is kept in plain files: `leads.yaml` lists the research leads (status, importance, chance, effort, next step, stopping criterion, documents, tasks); `INBOX.md` collects untriaged ideas; the journal records what was established or decided. `parallax.py check` validates the registry and, with `--git`, rejects deleted leads or modified journal entries.

3. **Visualization (`parallax.py serve`).** A local web interface displays the registry: a list of suggested leads (pinned first, then by importance × chance), an importance × chance matrix, a tree of themes, tasks by lead and by person, the inbox and the journal. Documents linked to a lead open in a Markdown/LaTeX reader at the referenced section. The registry can be edited from the interface; projects can add their own views as JavaScript extensions.

## Views
- **Overview**: key figures, "Do now" (pinned leads, then highest importance × chance), progress by theme, recent activity, extension sections.
- **Matrix** importance × chance; **Tree** of themes and sub-leads; **Tasks** (with who does what: the human or an agent); **Inbox**; **Journal**; sortable **List**.
- **Reader**: documents listed on a lead open in a built-in Markdown + MathJax reader, at the right section (`notes/x.md#Section`), or PDFs at the right page (`paper.pdf#page=4`).
- **Extensions**: project-specific views in JS (`Parallax.view`, `Parallax.overviewSection`, `Parallax.detailSection` — see `SKILL.md`).

## Editing
`serve` starts a local server (`127.0.0.1` only, session token, whitelist of writable files, atomic writes, conflict detection). Every change is validated before it is written; the "Commit…" button creates the git commit. In Chrome/Edge, the `parallax.html` snapshot can also edit the folder directly (File System Access API).

## Working with agents

`SKILL.md` describes the schema and the rules for AI agents: ratings are proposed by agents and validated by the human, leads are stopped rather than deleted, the journal is append-only. Copy these rules into your project's `AGENTS.md` / `CLAUDE.md` so that every agent follows them.

It also defines five rituals, which the human invokes by name in a conversation with an agent:

- **`open <id>`** — the agent reads the lead and its documents, summarizes it in at most five lines (goal, established results, obstacle, next action, stopping criterion), states how the work is split between agent and human, and stays on this lead for the rest of the session.
- **`idea <text>`** — the agent appends the idea verbatim, with the date, to `INBOX.md`, then returns to the current topic.
- **`triage`** — for each inbox item, the agent proposes to attach it to an existing lead, to create a new lead (with proposed ratings, next step and stopping criterion), or to reject it with a journal entry. It applies only what the human approves.
- **`close`** — at the end of a session, the agent updates the lead (established results, obstacle, next step, status, tasks), adds one to three journal entries about what was established or decided, proposes rating changes for other leads if needed, validates the registry and commits. It ends with what changed, the next action, and what the human can do before the next session.
- **`review`** — the agent lists ongoing leads not updated for three weeks, leads whose stopping criterion seems reached, and ratings not yet validated. It proposes changes without applying them.

## Installation

Requirements: Python ≥ 3.8, git, and PyYAML (`python3 -m pip install --user pyyaml`).

1. **Add Parallax to your repository** and start from the example registry:
   ```bash
   git submodule add https://github.com/Pinkupansa/parallax tools/parallax
   cp tools/parallax/example/leads.yaml tools/parallax/example/INBOX.md .
   ```
   Edit `leads.yaml`: project title, description, and `owner` (your initials).
2. **Run it:**
   ```bash
   python3 tools/parallax/parallax.py serve leads.yaml
   ```
   Parallax opens in your browser, editable. On macOS you can add a double-click launcher `Parallax.command`:
   `cd "$(dirname "$0")" && exec python3 tools/parallax/parallax.py serve leads.yaml` (then `chmod +x Parallax.command`).
3. **Connect your agents** (optional, but that is the point): add one line to your `AGENTS.md` / `CLAUDE.md`, e.g. *"The research registry follows `tools/parallax/SKILL.md`."* Agents then know the schema, the rules and the rituals.
4. **Guardrail** (optional): a versioned `pre-commit` hook running `python3 tools/parallax/parallax.py check leads.yaml --git`, enabled with `git config core.hooksPath .githooks`.

Day to day:
- Collaborators clone with `git clone --recurse-submodules …` (or run `git submodule update --init` afterwards).
- To get a newer Parallax: `git submodule update --remote tools/parallax`, then commit.
- Without git submodules, copying this folder into your repository works too.

Registries written with the French schema of Parallax 2 (`projet`, `pistes`, `statut`…) are read transparently and written back in French.

## Files
- `parallax.py`: validation, rendering, local server.
- `template.html`: the interface (CSS + JS), data injected at render time.
- `vendor/js-yaml.min.js`: YAML in the browser (js-yaml 4.1.0, MIT licence).
- `vendor/marked.min.js`: Markdown rendering for the reader (marked 12.0.2, MIT licence).
- `SKILL.md`: guide for agents. `example/`: minimal registry.

## Example scenario

A researcher works on a conjecture with an AI agent that has access to the repository.

1. **Setup.** She adds Parallax to the repository and asks the agent to build the registry from her existing notes. The agent creates a few themes and leads, each with a next step, a stopping criterion and proposed ratings marked `validated: false`.
2. **Prioritization.** She opens Parallax (`parallax.py serve`), adjusts the ratings, validates them, and pins the lead she wants to start with. It now appears first under "Do now".
3. **Work session.** She tells the agent `open small-cases`. The agent summarizes the lead and splits the work: it writes and runs a script checking the conjecture up to n = 12; meanwhile she checks the reduction lemma in `notes/reduction.md`. Both tasks appear in the lead's task list, with `who` set accordingly.
4. **Side idea.** Halfway through, she thinks of a probabilistic argument and types `idea: try a second-moment argument` (or uses the capture field in Parallax). The idea goes to `INBOX.md`; the session stays on the current lead.
5. **End of session.** She types `close`. The agent records what was established (the conjecture holds up to n = 12), updates the next step, adds a journal entry, validates the registry and commits. It ends with what she can do before the next session.
6. **Every week or so.** `triage` turns the inbox into new leads or rejects ideas with a reason; `review` lists stale leads and ratings still to validate. A lead that turns out to be a dead end is set to `stopped` with its reason and stays visible in the tree, so that it is not explored again.

## License

MIT — see `LICENSE`. Bundled libraries: js-yaml and marked (MIT).
