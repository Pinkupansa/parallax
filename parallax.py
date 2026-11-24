#!/usr/bin/env python3
"""Parallax: a high-altitude overview of a research project, built from a YAML registry of leads.

Usage:
    python3 parallax.py serve [leads.yaml]              # open Parallax in the browser, editable (any browser)
    python3 parallax.py build [leads.yaml] [-o f.html]  # write a self-contained, read-only page
    python3 parallax.py check [leads.yaml] [--git] [--strict]   # validate; --git: guardrails vs. last commit

Registries written with the French schema (projet / pistes / statut …) are read transparently
and written back in French.

Dependency: PyYAML (python3 -m pip install --user pyyaml).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is missing: python3 -m pip install --user pyyaml")

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "template.html"
VERSION = "3.0"
NAME = "Parallax"
MD_EXT = (".md", ".markdown")

# ----------------------------------------------------------------------------- schema
# Canonical schema is English. French registries (schema 2.x) are translated on read
# and written back in French by the browser editor (same table, injected into the page).
SCHEMA_FR = {
    "keys": {
        "top": {"projet": "project", "statuts": "statuses", "pistes": "leads", "journal": "journal"},
        "project": {"titre": "title", "sortie": "output", "vues": "views", "echelles": "scales",
                    "responsable": "owner"},
        "status": {"libelle": "label", "couleur": "color", "actif": "active", "anneau": "ring"},
        "lead": {"titre": "title", "court": "short", "statut": "status", "valide": "validated",
                 "pourquoi": "why", "resume": "summary", "acquis": "established", "prochaine": "next",
                 "arret": "stop", "maj": "updated", "cree": "created", "assigne": "assignee",
                 "epingle": "pinned"},
        "todo": {"texte": "text", "fait": "done", "qui": "who"},
        "journal": {"piste": "lead", "texte": "text", "auteur": "author"},
    },
    "values": {
        "status": {"idee": "idea", "en-cours": "ongoing", "reussie": "done", "arretee": "stopped"},
        "type": {"piste": "lead"},
        "journal": {"resultat": "result", "abandon": "stop", "suppression": "deletion", "idee": "idea"},
        "views": {"apercu": "overview", "matrice": "matrix", "arbre": "tree", "todo": "tasks", "liste": "list"},
    },
}


def _ren(d, table):
    return {table.get(k, k): v for k, v in d.items()} if isinstance(d, dict) else d


def detect_lang(raw: dict) -> str:
    return "fr" if isinstance(raw, dict) and ("pistes" in raw or "projet" in raw) else "en"


def to_english(raw: dict) -> tuple[dict, str]:
    """Translate a registry (either schema) into the canonical English schema."""
    lang = detect_lang(raw)
    if lang == "en":
        return raw, lang
    K, V = SCHEMA_FR["keys"], SCHEMA_FR["values"]
    reg = _ren(raw, K["top"])
    if isinstance(reg.get("project"), dict):
        pr = _ren(reg["project"], K["project"])
        if isinstance(pr.get("views"), list):
            pr["views"] = [V["views"].get(v, v) for v in pr["views"]]
        reg["project"] = pr
    if isinstance(reg.get("statuses"), dict):
        reg["statuses"] = {V["status"].get(k, k): _ren(v, K["status"]) for k, v in reg["statuses"].items()}
    leads = []
    for p in reg.get("leads") or []:
        q = _ren(p, K["lead"])
        if isinstance(q, dict):
            if "status" in q:
                q["status"] = V["status"].get(q["status"], q["status"])
            if "type" in q:
                q["type"] = V["type"].get(q["type"], q["type"])
            if isinstance(q.get("todo"), list):
                q["todo"] = [_ren(t, K["todo"]) for t in q["todo"]]
        leads.append(q)
    if "leads" in reg:
        reg["leads"] = leads
    if isinstance(reg.get("journal"), list):
        js = []
        for e in reg["journal"]:
            f = _ren(e, K["journal"])
            if isinstance(f, dict) and "type" in f:
                f["type"] = V["journal"].get(f["type"], f["type"])
            js.append(f)
        reg["journal"] = js
    return reg, lang


def anchor_norm(s) -> str:
    """Canonical form of an anchor or heading (no accents, lower case, punctuation collapsed).
    Same rule as Reader.norm in template.html."""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[\W_]+", " ", s).strip()


def md_headings(text: str) -> list[str]:
    """Markdown headings (#, ##, …) outside code blocks."""
    out, code = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            code = not code
        elif not code:
            m = re.match(r"\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$", line)
            if m:
                out.append(m.group(1))
    return out


def split_doc(d: str) -> tuple[str, str]:
    """'path#anchor' -> (path, anchor). Anchor: heading text (.md) or page=N (PDF)."""
    path, _, anchor = d.partition("#")
    return path, anchor


DEFAULT_STATUSES = {  # four statuses; two hues (steel blue, green) and silver neutrals
    "idea":    {"label": "Idea",    "color": "#7D858F", "active": True, "ring": True},
    "ongoing": {"label": "Ongoing", "color": "#2B68B0", "active": True},
    "done":    {"label": "Done",    "color": "#1F8A5B", "active": False},
    "stopped": {"label": "Stopped", "color": "#BFC5CC", "active": False},
}
DEFAULT_SCALES = {
    "importance": {1: "Useful", 2: "Important", 3: "Decisive"},
    "chance": {1: "Low", 2: "Medium", 3: "High"},
    "effort": {"S": "A few hours", "M": "A few days", "L": "Weeks"},
}
JOURNAL_TYPES = {"result", "decision", "stop", "deletion", "idea", "note"}
KNOWN_FIELDS = {
    "id", "title", "short", "type", "parent", "status", "importance", "chance",
    "effort", "validated", "why", "summary", "established", "obstacle", "next",
    "stop", "docs", "tags", "updated", "created", "assignee", "todo", "pinned",
}
RE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_BULLET = re.compile(r"^- (?:\[(\d{4}-\d{2}-\d{2})\]\s*|(\d{4}-\d{2}-\d{2})\s*:\s*)?(.*)$")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def as_date(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    return str(v)


def read_inbox(path: Path) -> list[dict]:
    """Top-level bullets of INBOX.md; indented lines continue the bullet."""
    items: list[dict] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- "):
            m = RE_BULLET.match(line)
            date = (m.group(1) or m.group(2)) if m else None
            items.append({"date": date, "text": (m.group(3) if m else line[2:]).strip()})
        elif items and line.startswith((" ", "\t")) and line.strip():
            items[-1]["text"] += "\n" + line.strip()
    return items


def validate(reg: dict, r: Report, base: Path | None = None) -> None:
    project = reg.get("project")
    if not isinstance(project, dict) or not project.get("title"):
        r.err("project.title is required")
    leads = reg.get("leads")
    if not isinstance(leads, list) or not leads:
        r.err("the 'leads' list is empty or missing")
        return
    statuses = reg["_statuses"]
    ids: dict[str, dict] = {}
    for i, p in enumerate(leads):
        where = f"leads[{i}]"
        if not isinstance(p, dict):
            r.err(f"{where} is not a mapping")
            continue
        pid = p.get("id")
        if not pid or not isinstance(pid, str) or not RE_ID.match(pid):
            r.err(f"{where}: missing or invalid id (lower case, digits, dashes): {pid!r}")
            continue
        where = f"lead '{pid}'"
        if pid in ids:
            r.err(f"{where}: duplicate id")
        ids[pid] = p
        if not p.get("title"):
            r.err(f"{where}: missing title")
        kind = p.get("type", "lead")
        if kind not in ("lead", "theme"):
            r.err(f"{where}: unknown type {kind!r} (lead | theme)")
        if kind == "theme":
            continue
        st = p.get("status")
        if st not in statuses:
            r.err(f"{where}: unknown status {st!r} ({' | '.join(statuses)})")
        for field in ("importance", "chance"):
            v = p.get(field)
            if v is None:
                r.warn(f"{where}: {field} not rated")
            elif not (isinstance(v, int) and 1 <= v <= 3):
                r.err(f"{where}: {field} must be an integer 1..3 (got {v!r})")
        eff = p.get("effort")
        if eff is None:
            r.warn(f"{where}: effort not estimated")
        elif eff not in ("S", "M", "L"):
            r.err(f"{where}: effort must be S, M or L (got {eff!r})")
        if st in ("idea", "ongoing") and not p.get("next"):
            r.warn(f"{where}: active lead without a 'next' action")
        if st in ("idea", "ongoing") and not p.get("stop"):
            r.warn(f"{where}: no stopping criterion ('stop')")
        if st == "stopped" and not (p.get("summary") or p.get("obstacle")):
            r.warn(f"{where}: stopped without a reason ('obstacle' or 'summary')")
        for field in ("established", "docs", "tags", "todo"):
            if field in p and not isinstance(p[field], list):
                r.err(f"{where}: {field} must be a list")
        for k, t in enumerate(p.get("todo") or [] if isinstance(p.get("todo"), list) else []):
            if not (isinstance(t, dict) and t.get("text")):
                r.err(f"{where}: todo[{k}] must be {{text: …, done: false}}")
            elif "who" in t and not isinstance(t["who"], str):
                r.err(f"{where}: todo[{k}].who must be a name (string)")
        if "pinned" in p and not isinstance(p["pinned"], bool):
            r.err(f"{where}: pinned must be true or false")
        if base is not None and isinstance(p.get("docs"), list):
            for d in p["docs"]:
                if not isinstance(d, str) or "://" in d:
                    continue
                path, anchor = split_doc(d)
                f = base / path
                if not f.exists():
                    r.warn(f"{where}: document not found {path!r}")
                elif anchor and path.lower().endswith(MD_EXT):
                    a = anchor_norm(anchor)
                    try:
                        heads = md_headings(f.read_text(encoding="utf-8"))
                    except (OSError, UnicodeDecodeError):
                        heads = []
                    if not any(a in anchor_norm(h) for h in heads):
                        r.warn(f"{where}: no heading of {path!r} contains '{anchor}'")
                elif anchor and path.lower().endswith(".pdf") and not re.fullmatch(r"page=\d+", anchor):
                    r.warn(f"{where}: PDF anchor must be page=N (got '{anchor}')")
        m = as_date(p.get("updated"))
        if m and not RE_DATE.match(m):
            r.err(f"{where}: updated must be YYYY-MM-DD (got {m!r})")
    for pid, p in ids.items():
        par = p.get("parent")
        if par is not None and par not in ids:
            r.err(f"lead '{pid}': unknown parent {par!r}")
    for pid in ids:  # cycles
        seen, cur = set(), pid
        while cur is not None and cur in ids:
            if cur in seen:
                r.err(f"parent cycle through '{pid}'")
                break
            seen.add(cur)
            cur = ids[cur].get("parent")
    deleted = {e.get("lead") for e in (reg.get("journal") or [])
               if isinstance(e, dict) and e.get("type") == "deletion"}
    for i, e in enumerate(reg.get("journal") or []):
        where = f"journal[{i}]"
        if not isinstance(e, dict):
            r.err(f"{where} is not a mapping")
            continue
        d = as_date(e.get("date"))
        if not d or not RE_DATE.match(d):
            r.err(f"{where}: date YYYY-MM-DD is required")
        if not e.get("text"):
            r.err(f"{where}: missing text")
        if e.get("lead") is not None and e["lead"] not in ids and e["lead"] not in deleted:
            r.err(f"{where}: unknown lead {e['lead']!r}")
        if e.get("type") is not None and e["type"] not in JOURNAL_TYPES:
            r.warn(f"{where}: type {e['type']!r} not in {sorted(JOURNAL_TYPES)}")


def normalize(reg: dict, base: Path, r: Report) -> dict:
    """reg: canonical (English) registry. Returns the data injected into the page."""
    project = dict(reg.get("project") or {})
    statuses = {k: dict(v) for k, v in DEFAULT_STATUSES.items()}
    for k, v in (reg.get("statuses") or {}).items():
        statuses.setdefault(k, {"label": k, "color": "#888888", "active": False}).update(v or {})
    scales = {k: dict(v) for k, v in DEFAULT_SCALES.items()}
    for k, v in (project.get("scales") or {}).items():
        scales.setdefault(k, {}).update(v or {})
    reg["_statuses"] = statuses

    validate(reg, r, base)

    leads = []
    for p in reg.get("leads") or []:
        if not isinstance(p, dict) or "id" not in p:
            continue
        q = {k: (as_date(v) if k in ("updated", "created") else v) for k, v in p.items()}
        q.setdefault("type", "lead")
        q.setdefault("validated", True)
        q["_extra"] = sorted(k for k in p if k not in KNOWN_FIELDS)
        leads.append(q)

    journal = []
    for e in reg.get("journal") or []:
        if isinstance(e, dict):
            e = dict(e)
            e["date"] = as_date(e.get("date"))
            journal.append(e)
    journal.sort(key=lambda e: e.get("date") or "", reverse=True)

    inbox = read_inbox(base / project.get("inbox", "INBOX.md"))

    return {
        "version": VERSION,
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "project": {k: v for k, v in project.items() if k != "scales"},
        "statuses": statuses,
        "scales": {k: {str(kk): vv for kk, vv in v.items()} for k, v in scales.items()},
        "leads": leads,
        "journal": journal,
        "inbox": inbox,
        "warnings": r.warnings,
        "_fields": sorted(KNOWN_FIELDS),
    }


def git_guardrails(source: Path, reg: dict, r: Report) -> None:
    """Compare with the last commit: no lead and no journal entry may disappear."""
    owner = (reg.get("project") or {}).get("owner") or "the human owner of the project"
    import subprocess
    try:
        top = subprocess.run(["git", "-C", str(source.parent), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        r.warn("--git: not a git repository, guardrails skipped")
        return
    rel = source.resolve().relative_to(Path(top).resolve()).as_posix()
    res = subprocess.run(["git", "-C", top, "show", f"HEAD:{rel}"], capture_output=True, text=True)
    if res.returncode != 0:
        return  # registry not committed yet
    try:
        old = to_english(yaml.safe_load(res.stdout) or {})[0]
    except yaml.YAMLError:
        return
    def leads(x):
        return {p["id"]: p for p in (x.get("leads") or []) if isinstance(p, dict) and "id" in p}
    def entries(x):
        return {(as_date(e.get("date")), str(e.get("text"))) for e in (x.get("journal") or []) if isinstance(e, dict)}
    before, after = leads(old), leads(reg)
    traced = {e.get("lead") for e in (reg.get("journal") or [])
              if isinstance(e, dict) and e.get("type") == "deletion"}
    for pid in sorted(set(before) - set(after)):
        if pid in traced:
            r.warn(f"lead '{pid}' deleted (traced in the journal)")
        else:
            r.err(f"lead '{pid}' deleted: set its status to 'stopped' instead; a real deletion "
                  f"(duplicate, mistake) is done by {owner} with a journal entry of type 'deletion'")
    for d, t in sorted(entries(old) - entries(reg), key=lambda e: e[0] or ""):
        r.err(f"journal entry of {d} deleted or modified: the journal is append-only ({t[:60]!r})")
    for pid in sorted(set(before) & set(after)):
        if before[pid].get("validated") is False and after[pid].get("validated", True) is not False:
            r.warn(f"lead '{pid}': ratings validated — fine if done by {owner}; an agent never validates")


def analyse(source: Path, git: bool = False):
    """Read, translate, validate and normalize. Returns (registry, data, report); registry is None if unreadable."""
    r = Report()
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        r.err(f"unreadable YAML: {exc}")
        return None, None, r
    if not isinstance(raw, dict):
        r.err("the registry must be a YAML mapping")
        return None, None, r
    reg, lang = to_english(raw)
    data = normalize(reg, source.parent, r)
    data["registry"] = source.name
    data["lang"] = lang
    if git:
        git_guardrails(source, reg, r)
    return reg, data, r


def render_page(source: Path, reg: dict, data: dict, server: dict | None = None) -> str:
    base = source.parent
    exts = []
    for path in (reg.get("project") or {}).get("extensions") or []:
        f = base / path
        if f.exists():
            code = f.read_text(encoding="utf-8").replace("</script", "<\\/script")
            exts.append(f"<script>/* extension: {path} */\n{code}\n</script>")
        else:
            data.setdefault("warnings", []).append(f"extension not found: {path}")
    template = TEMPLATE.read_text(encoding="utf-8")
    # Markdown documents cited in 'docs': the built-in reader uses these copies when the page
    # is opened as a file (no server); with the server it reads the current file instead.
    texts, root = {}, base.resolve()
    for p in data.get("leads", []):
        for d in p.get("docs") or []:
            if not isinstance(d, str) or "://" in d:
                continue
            path = split_doc(d)[0]
            if path in texts or not path.lower().endswith(MD_EXT):
                continue
            f = (base / path).resolve()
            try:
                f.relative_to(root)
                texts[path] = f.read_text(encoding="utf-8")
            except (ValueError, OSError, UnicodeDecodeError):
                pass
    data["texts"] = texts
    data["schema"] = SCHEMA_FR
    def vendor(name):
        f = HERE / "vendor" / name
        return f.read_text(encoding="utf-8").replace("</script", "<\\/script") if f.exists() else ""
    jsyaml, marked = vendor("js-yaml.min.js"), vendor("marked.min.js")
    js = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    srv = json.dumps(server or None).replace("</", "<\\/")
    title = str(data["project"].get("title", "Project")).replace("&", "&amp;").replace("<", "&lt;")
    return (template
            .replace("/*BEGIN_DATA*/null/*END_DATA*/", "/*BEGIN_DATA*/" + js + "/*END_DATA*/")
            .replace("/*__SERVER__*/null", srv)
            .replace("/*__JSYAML__*/", jsyaml)
            .replace("/*__MARKED__*/", marked)
            .replace("<!--__EXTENSIONS__-->", "\n".join(exts))
            .replace("__TITLE__", f"{title} — {NAME}"))


def show(r: Report) -> None:
    for w in r.warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in r.errors:
        print(f"ERROR: {e}", file=sys.stderr)


def build(source: Path, output: Path | None, check_only: bool, strict: bool, git: bool = False, quiet: bool = False) -> int:
    reg, data, r = analyse(source, git)
    if not quiet:
        show(r)
    if r.errors or (strict and r.warnings):
        if not quiet:
            print(f"{len(r.errors)} error(s), {len(r.warnings)} warning(s): nothing written.", file=sys.stderr)
        return 1
    n = sum(1 for p in data["leads"] if p["type"] == "lead")
    if check_only:
        if not quiet:
            print(f"OK: {n} leads, {len(data['journal'])} journal entries, "
                  f"{len(data['inbox'])} ideas to triage, {len(r.warnings)} warning(s).")
        return 0
    page = render_page(source, reg, data)
    output = output or source.parent / data["project"].get("output", "parallax.html")
    output.write_text(page, encoding="utf-8")
    if not quiet:
        print(f"Wrote {output}: {n} leads, {len(data['inbox'])} ideas to triage, {len(r.warnings)} warning(s).")
    return 0


# ============================================================================ local server
def serve(source: Path, port: int, open_browser: bool) -> int:
    import http.server
    import mimetypes
    import os
    import secrets
    import subprocess
    import threading
    import urllib.parse
    import webbrowser

    source = source.resolve()
    base = source.parent
    token = secrets.token_urlsafe(24)
    lock = threading.Lock()

    def inbox_name() -> str:
        try:
            reg = to_english(yaml.safe_load(source.read_text(encoding="utf-8")) or {})[0]
            return str((reg.get("project") or {}).get("inbox", "INBOX.md"))
        except Exception:
            return "INBOX.md"

    def writable() -> dict:
        return {source.name: source, inbox_name(): base / inbox_name()}

    def mtime(p: Path):
        return str(p.stat().st_mtime_ns) if p.exists() else None

    def git(*args):
        return subprocess.run(["git", "-C", str(base), *args], capture_output=True, text=True)

    def git_state() -> dict:
        if git("rev-parse", "--is-inside-work-tree").returncode != 0:
            return {"git": False}
        names = list(writable())
        st = git("status", "--porcelain", "--", *names).stdout.splitlines()
        br = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        last = git("log", "-1", "--format=%h %s (%cr)").stdout.strip()
        return {"git": True, "branch": br, "modified": [l[3:] for l in st], "last": last}

    class H(http.server.BaseHTTPRequestHandler):
        server_version = "Parallax"

        def log_message(self, fmt, *args):  # quiet
            pass

        def _host_ok(self) -> bool:
            h = self.headers.get("Host", "")
            return h in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _guard(self, api: bool) -> bool:
            if not self._host_ok():
                self._json(403, {"error": "host refused"})
                return False
            if api and self.headers.get("X-Parallax-Token") != token:
                self._json(403, {"error": "missing or invalid token"})
                return False
            return True

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 5_000_000:
                raise ValueError("request too large")
            return json.loads(self.rfile.read(n).decode("utf-8") or "{}")

        def do_GET(self):
            u = urllib.parse.urlsplit(self.path)
            if u.path in ("/", "/index.html"):
                if not self._guard(False):
                    return
                reg, data, r = analyse(source)
                if reg is None:
                    msg = "<h1>Parallax</h1><p>Unreadable registry:</p><pre>" + "\n".join(r.errors).replace("<", "&lt;") + "</pre>"
                    return self._send(500, msg.encode("utf-8"), "text/html; charset=utf-8")
                data["warnings"] = r.warnings + [f"ERROR: {e}" for e in r.errors]
                page = render_page(source, reg, data, {"token": token})
                return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            if u.path == "/api/file":
                if not self._guard(True):
                    return
                name = urllib.parse.parse_qs(u.query).get("name", [""])[0]
                f = writable().get(name)
                if f is None:
                    return self._json(403, {"error": f"file not writable: {name}"})
                if not f.exists():
                    return self._json(404, {"error": "missing"})
                return self._json(200, {"text": f.read_text(encoding="utf-8"), "mtime": mtime(f)})
            if u.path == "/api/status":
                if not self._guard(True):
                    return
                return self._json(200, git_state())
            # project files (read-only): notes, PDFs, code…
            if not self._guard(False):
                return
            rel = urllib.parse.unquote(u.path.lstrip("/"))
            f = (base / rel).resolve()
            if base not in f.parents or ".git" in f.relative_to(base).parts or not f.is_file():
                return self._json(404, {"error": "not found"})
            ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if f.suffix in (".md", ".yaml", ".yml", ".py", ".cpp", ".txt", ".js"):
                ctype = "text/plain; charset=utf-8"
            return self._send(200, f.read_bytes(), ctype)

        def do_PUT(self):
            if urllib.parse.urlsplit(self.path).path != "/api/file" or not self._guard(True):
                return self._json(404, {"error": "not found"}) if self._host_ok() else None
            try:
                d = self._body()
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            name, text = d.get("name"), d.get("text")
            f = writable().get(name)
            if f is None or not isinstance(text, str):
                return self._json(403, {"error": f"file not writable: {name}"})
            with lock:
                if d.get("mtime") != mtime(f):
                    return self._json(409, {"error": "changed on disk since it was loaded", "mtime": mtime(f)})
                tmp = f.with_name(f".{f.name}.parallax-tmp")
                tmp.write_text(text, encoding="utf-8")
                if f == source:
                    r = Report()
                    try:
                        reg = to_english(yaml.safe_load(text) or {})[0]
                        normalize(reg, base, r)
                        git_guardrails(source, reg, r)
                    except yaml.YAMLError as exc:
                        r.err(f"unreadable YAML: {exc}")
                    if r.errors:
                        tmp.unlink(missing_ok=True)
                        return self._json(422, {"errors": r.errors})
                os.replace(tmp, f)
                new = mtime(f)
            try:  # static snapshot, for reading without the server
                build(source, None, False, False, quiet=True)
            except Exception:
                pass
            return self._json(200, {"mtime": new})

        def do_POST(self):
            if urllib.parse.urlsplit(self.path).path != "/api/commit" or not self._guard(True):
                return self._json(404, {"error": "not found"}) if self._host_ok() else None
            try:
                d = self._body()
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            msg = str(d.get("message") or "").strip() or "Changes from Parallax"
            names = [n for n, f in writable().items() if f.exists()]
            with lock:
                a = git("add", "--", *names)
                if a.returncode != 0:
                    return self._json(500, {"ok": False, "output": a.stderr})
                if git("diff", "--cached", "--quiet").returncode == 0:
                    return self._json(200, {"ok": True, "nothing": True, "state": git_state()})
                c = git("commit", "-m", msg, "-m", "Agent: human (Parallax)")
            return self._json(200 if c.returncode == 0 else 422,
                              {"ok": c.returncode == 0, "output": (c.stdout + c.stderr).strip(), "state": git_state()})

    srv = None
    for p in range(port, port + 20):
        try:
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", p), H)
            break
        except OSError:
            continue
    if srv is None:
        print(f"No free port between {port} and {port + 19}.", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{srv.server_port}/"
    print(f"{NAME} — {source.name} — {url}")
    print("Close this window (or press Ctrl-C) to stop Parallax.")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nParallax stopped.")
    return 0


def default_registry() -> Path:
    for name in ("leads.yaml", "pistes.yaml"):
        if Path(name).exists():
            return Path(name)
    return Path("leads.yaml")


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0].endswith((".yaml", ".yml")):  # legacy form: parallax.py leads.yaml [--check]
        argv = ["check" if "--check" in argv else "build"] + [a for a in argv if a != "--check"]
    ap = argparse.ArgumentParser(prog="parallax", description="Parallax: a high-altitude overview of a research project.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="open Parallax in the browser (editable)")
    s.add_argument("registry", type=Path, nargs="?")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-open", action="store_true", help="do not open the browser")
    b = sub.add_parser("build", help="write a self-contained, read-only page")
    b.add_argument("registry", type=Path, nargs="?")
    b.add_argument("-o", "--output", type=Path)
    b.add_argument("--git", action="store_true")
    b.add_argument("--strict", action="store_true")
    c = sub.add_parser("check", help="validate the registry")
    c.add_argument("registry", type=Path, nargs="?")
    c.add_argument("--git", action="store_true", help="guardrails against the last commit")
    c.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv)
    reg = a.registry or default_registry()
    if a.cmd == "serve":
        sys.exit(serve(reg, a.port, not a.no_open))
    if a.cmd == "build":
        sys.exit(build(reg, a.output, False, a.strict, a.git))
    sys.exit(build(reg, None, True, a.strict, a.git))


if __name__ == "__main__":
    main()
