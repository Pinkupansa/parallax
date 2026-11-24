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

## Views
- **Overview**: key figures, "Do now" (pinned leads, then highest importance × chance), progress by theme, recent activity, extension sections.
- **Matrix** importance × chance; **Tree** of themes and sub-leads; **Tasks** (with who does what: the human or an agent); **Inbox**; **Journal**; sortable **List**.
- **Reader**: documents listed on a lead open in a built-in Markdown + MathJax reader, at the right section (`notes/x.md#Section`), or PDFs at the right page (`paper.pdf#page=4`).
- **Extensions**: project-specific views in JS (`Parallax.view`, `Parallax.overviewSection`, `Parallax.detailSection` — see `SKILL.md`).

## Editing
`serve` starts a local server (`127.0.0.1` only, session token, whitelist of writable files, atomic writes, conflict detection). Every change is validated before it is written; the "Commit…" button creates the git commit. In Chrome/Edge, the `parallax.html` snapshot can also edit the folder directly (File System Access API).

## Working with agents
`SKILL.md` describes the schema, the rules (ratings belong to the human, leads are stopped rather than deleted, the journal is append-only) and the rituals (`open`, `idea`, `triage`, `close`, `review`) for AI agents. Copy its rules into your project's `AGENTS.md` / `CLAUDE.md` so that every agent follows them.

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

## License

MIT — see `LICENSE`. Bundled libraries: js-yaml and marked (MIT).
