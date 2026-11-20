#!/usr/bin/env python3
"""
check_trace.py - traceability checker and progress counter for the design/ docs.

What it does
  * Finds every item (REQ, SPEC, ARCH, EVAL, DEC, BLK, TEST, CHG, TASK) in design/**/*.md
  * Checks IDs are unique, links point to real items, required links exist,
    status values are valid, replaced decisions say what replaced them.
  * Works out "derived verification" from passing tests (does not trust claims).
  * Optionally cross-checks TEST status against cocotb results.xml files.
  * Reports progress numbers and whether a stage gate (G1..G7) is met.
  * Regenerates design/trace.md (never edit that file by hand).

Usage
  python3 scripts/check_trace.py                 # check + summary
  python3 scripts/check_trace.py --write-trace   # also regenerate design/trace.md
  python3 scripts/check_trace.py --gate G2       # also check gate G2 (exit 1 if not met)
  python3 scripts/check_trace.py --quiet         # only errors + one-line summary

Exit code: 1 if there are errors (or the requested gate is not met), else 0.

Item format (see AGENTS.md):
  ### SPEC-UART-001 - UART TX bit timing
  - Status: draft
  - Traces to: REQ-PROTO-001
  Free text below the fields.

Only lines of the form "- Key: value" are read as fields. Text inside ``` code
fences is ignored, and design/templates/ is skipped, so examples there are safe.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DESIGN = os.path.join(ROOT, "design")
TRACE_FILE = os.path.join(DESIGN, "trace.md")
SKIP_DIRS = {os.path.join(DESIGN, "templates"), os.path.join(DESIGN, "reference")}
SKIP_FILES = {TRACE_FILE}

TYPES = ["REQ", "SPEC", "ARCH", "EVAL", "DEC", "BLK", "TEST", "CHG", "TASK"]
ID_RE = r"(?:%s)-[A-Z0-9]+(?:-[A-Z0-9]+)*" % "|".join(TYPES)
ID_PAT = re.compile(r"\b(" + ID_RE + r")\b")
HEAD_PAT = re.compile(r"^(#{1,4})\s+(" + ID_RE + r")\b\s*(?:[—–:\-]+\s*(.*))?$")
ANY_HEAD = re.compile(r"^(#{1,6})\s")
FIELD_PAT = re.compile(r"^\s*[-*]\s+\**([A-Za-z][A-Za-z ]*?)\**\s*:\s*(.*)$")

STATUSES = {
    "REQ": {"draft", "agreed", "implemented", "verified", "suspect", "rejected"},
    "SPEC": {"draft", "agreed", "implemented", "verified", "suspect", "rejected"},
    "BLK": {"draft", "agreed", "implemented", "verified", "suspect", "rejected"},
    "ARCH": {"candidate", "chosen", "rejected", "suspect"},
    "EVAL": {"planned", "running", "done", "suspect"},
    "DEC": {"draft", "agreed", "replaced", "suspect"},
    "TEST": {"planned", "written", "passing", "failing", "suspect"},
    "CHG": {"proposed", "approved", "rejected", "done"},
    "TASK": {"todo", "doing", "done", "blocked"},
}
PRIORITIES = {"must", "should", "could", "won't", "wont"}
TEST_LEVELS = {"unit", "integration", "system", "acceptance"}
REF_KEYS = {"traces to", "verifies", "evidence", "chooses", "compares", "replaces",
            "replaced by", "affects", "works on", "blocked by"}
# Upward link types that every item of a type must have (at least one ID of these types)
REQUIRED_UP = {
    "SPEC": ("traces to", {"REQ"}),
    "EVAL": ("traces to", {"REQ", "SPEC", "BLK"}),
    "DEC": ("traces to", {"REQ", "SPEC", "BLK"}),
    "BLK": ("traces to", {"REQ", "SPEC", "DEC", "ARCH"}),
    "TEST": ("verifies", {"REQ", "SPEC", "BLK", "ARCH", "DEC"}),
}
INACTIVE = {"rejected", "replaced"}
# Types that pass trace links through to their own children when building trace.md
PASS_THROUGH = {"SPEC", "BLK"}


@dataclass
class Item:
    id: str
    type: str
    title: str
    file: str
    line: int
    fields: dict = field(default_factory=dict)       # key -> raw value
    refs: dict = field(default_factory=dict)         # key -> [ids]

    @property
    def status(self) -> str:
        return self.fields.get("status", "").strip().lower()

    def get(self, key: str) -> str:
        return self.fields.get(key, "").strip()

    def ids(self, key: str) -> list:
        return self.refs.get(key, [])


def rel(path: str) -> str:
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def md_files():
    for path in sorted(glob.glob(os.path.join(DESIGN, "**", "*.md"), recursive=True)):
        if path in SKIP_FILES:
            continue
        if any(path.startswith(d + os.sep) for d in SKIP_DIRS):
            continue
        yield path


def parse():
    items, dups = [], []
    for path in md_files():
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        in_fence = False
        cur, cur_level = None, 0
        for n, line in enumerate(lines, 1):
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = HEAD_PAT.match(line)
            if m:
                cur = Item(id=m.group(2), type=m.group(2).split("-")[0],
                           title=(m.group(3) or "").strip(), file=path, line=n)
                cur_level = len(m.group(1))
                items.append(cur)
                continue
            h = ANY_HEAD.match(line)
            if h and cur is not None and len(h.group(1)) <= cur_level:
                cur = None
                continue
            if cur is None:
                continue
            f = FIELD_PAT.match(line)
            if f:
                key = f.group(1).strip().lower()
                val = f.group(2).strip()
                if key in cur.fields:          # repeated key: append
                    cur.fields[key] += ", " + val
                else:
                    cur.fields[key] = val
                if key in REF_KEYS:
                    cur.refs.setdefault(key, [])
                    cur.refs[key] += ID_PAT.findall(val)
    seen = {}
    for it in items:
        if it.id in seen:
            dups.append((it, seen[it.id]))
        else:
            seen[it.id] = it
    return items, seen, dups


def load_results():
    """Map cocotb testcase name -> 'pass' | 'fail' | 'skip' from results*.xml files."""
    res = {}
    files = glob.glob(os.path.join(ROOT, "test", "**", "results*.xml"), recursive=True)
    for path in files:
        try:
            tree = ET.parse(path)
        except ET.ParseError:
            continue
        for tc in tree.iter("testcase"):
            name = tc.get("name", "")
            outcome = "pass"
            for child in tc:
                if child.tag in ("failure", "error"):
                    outcome = "fail"
                elif child.tag == "skipped" and outcome == "pass":
                    outcome = "skip"
            # a failure anywhere wins over a pass elsewhere
            if res.get(name) == "fail":
                continue
            res[name] = outcome
    return res, files


class Report:
    def __init__(self):
        self.errors, self.warnings, self.infos = [], [], []

    def err(self, it, msg):
        self.errors.append(f"{where(it)} {msg}")

    def warn(self, it, msg):
        self.warnings.append(f"{where(it)} {msg}")

    def info(self, it, msg):
        self.infos.append(f"{where(it)} {msg}")


def where(it):
    if it is None:
        return ""
    return f"{it.id} ({rel(it.file)}:{it.line}):"


def check(items, by_id, dups, results):
    rep = Report()
    for a, b in dups:
        rep.err(a, f"duplicate ID (also at {rel(b.file)}:{b.line})")

    for it in by_id.values():
        # status
        if not it.status:
            rep.err(it, "missing '- Status:' field")
        elif it.status not in STATUSES[it.type]:
            rep.err(it, f"status '{it.status}' not valid for {it.type} "
                        f"(use one of: {', '.join(sorted(STATUSES[it.type]))})")
        # dangling references
        for key, ids in it.refs.items():
            for ref in ids:
                if ref not in by_id:
                    rep.err(it, f"'{key}' points to unknown ID {ref}")
                elif by_id[ref].status in INACTIVE and key not in ("replaces", "replaced by", "compares", "affects") \
                        and it.status not in INACTIVE:
                    rep.warn(it, f"'{key}' points to {ref} which is {by_id[ref].status}")
        # required upward links
        if it.type in REQUIRED_UP and it.status not in INACTIVE:
            key, allowed = REQUIRED_UP[it.type]
            if not any(r.split("-")[0] in allowed for r in it.ids(key)):
                rep.err(it, f"needs '- {key.capitalize()}:' with at least one of "
                            f"{'/'.join(sorted(allowed))}")
        # type-specific fields
        if it.type == "REQ":
            pr = it.get("priority").lower()
            if pr not in PRIORITIES:
                rep.err(it, "needs '- Priority:' Must / Should / Could / Won't")
            if not it.get("source"):
                rep.warn(it, "has no '- Source:'")
        if it.type == "TEST":
            lvl = it.get("level").lower()
            if lvl not in TEST_LEVELS:
                rep.err(it, "needs '- Level:' unit / integration / system / acceptance")
        if it.type == "DEC" and it.status not in INACTIVE:
            ev = it.get("evidence")
            if not ev:
                rep.err(it, "needs '- Evidence:' (EVAL IDs, or the word 'guess')")
            elif "guess" in ev.lower():
                rep.warn(it, "evidence includes a guess - back it with an EVAL before the gate")
        if it.type == "DEC" and it.status == "replaced" and not it.ids("replaced by"):
            rep.err(it, "status 'replaced' needs '- Replaced by: DEC-...'")
        if it.status == "suspect":
            rep.warn(it, "is SUSPECT - re-check it after a change, then restore its status")

    # cocotb results cross-check
    if results:
        for it in by_id.values():
            if it.type != "TEST" or not it.get("run"):
                continue
            names = [r.strip().split("::")[-1].split(".")[-1]
                     for r in re.split(r"[,\s]+", it.get("run")) if r.strip()]
            outs = [results.get(n) for n in names]
            if any(o is None for o in outs):
                missing = [n for n, o in zip(names, outs) if o is None]
                if it.status in ("passing", "failing"):
                    rep.warn(it, f"no result found for {', '.join(missing)} (run the tests)")
                continue
            actual = "failing" if "fail" in outs else ("passing" if all(o == "pass" for o in outs) else None)
            if actual and it.status in ("passing", "failing", "written") and actual != it.status:
                rep.err(it, f"status says '{it.status}' but results.xml says '{actual}'")
    return rep


def children_map(by_id):
    """Reverse graph: parent ID -> list of child items (via 'traces to' and 'verifies')."""
    kids = defaultdict(list)
    for it in by_id.values():
        if it.status in INACTIVE:
            continue
        for key in ("traces to", "verifies"):
            for p in it.ids(key):
                kids[p].append(it)
    return kids


def tests_of(item_id, kids):
    return [k for k in kids.get(item_id, []) if k.type == "TEST"]


def derived_verified(it, kids, cache):
    if it.id in cache:
        return cache[it.id]
    cache[it.id] = False                     # guard against cycles
    if it.type == "TEST":
        ok = it.status == "passing"
    elif it.type in ("SPEC", "BLK"):
        ts = tests_of(it.id, kids)
        ok = bool(ts) and all(t.status == "passing" for t in ts)
    elif it.type == "REQ":
        specs = [k for k in kids.get(it.id, []) if k.type == "SPEC"]
        ts = tests_of(it.id, kids)
        ok = bool(specs or ts) and all(derived_verified(s, kids, cache) for s in specs) \
            and all(t.status == "passing" for t in ts)
    else:
        ok = False
    cache[it.id] = ok
    return ok


def descendants(item_id, kids):
    out, stack, seen = [], [item_id], {item_id}
    while stack:
        cur = stack.pop()
        for k in kids.get(cur, []):
            if k.id in seen or k.type in ("CHG", "TASK"):
                continue
            seen.add(k.id)
            out.append(k)
            if k.type in PASS_THROUGH:
                stack.append(k.id)
    return out


def gate_check(gate, by_id, kids, cache, rep):
    """Return list of unmet criteria for gates up to and including `gate`."""
    g = int(gate.upper().lstrip("G"))
    of = lambda t: [i for i in by_id.values() if i.type == t]
    active = lambda t: [i for i in of(t) if i.status not in INACTIVE]
    unmet = []
    if rep.errors:
        unmet.append(f"checker has {len(rep.errors)} error(s)")
    sus = [i.id for i in by_id.values() if i.status == "suspect"]
    if sus:
        unmet.append("suspect items: " + ", ".join(sus))
    # G1
    reqs = active("REQ")
    if not reqs:
        unmet.append("G1: no requirements")
    drafts = [r.id for r in reqs if r.status == "draft"]
    if drafts:
        unmet.append("G1: requirements still draft: " + ", ".join(drafts))
    if g >= 2:
        for r in reqs:
            if r.get("priority").lower() in ("must", "should"):
                specs = [k for k in kids.get(r.id, []) if k.type == "SPEC"]
                acc = [t for t in tests_of(r.id, kids) if t.get("level").lower() == "acceptance"]
                if not specs and not acc:
                    unmet.append(f"G2: {r.id} has no SPEC and no acceptance TEST")
        for s in active("SPEC"):
            if s.status == "draft":
                unmet.append(f"G2: {s.id} still draft")
            if not tests_of(s.id, kids):
                unmet.append(f"G2: {s.id} has no TEST that verifies it")
    if g >= 3:
        archs = of("ARCH")
        chosen = [a for a in archs if a.status == "chosen"]
        if len(archs) < 2:
            unmet.append("G3: fewer than 2 ARCH options")
        if len(chosen) != 1:
            unmet.append(f"G3: need exactly 1 chosen ARCH (have {len(chosen)})")
        else:
            decs = [d for d in active("DEC") if chosen[0].id in d.ids("chooses")]
            if not any(d.status == "agreed" for d in decs):
                unmet.append(f"G3: no agreed DEC that chooses {chosen[0].id}")
            for d in decs:
                evals = [by_id[e] for e in d.ids("evidence") if e in by_id]
                if not evals:
                    unmet.append(f"G3: {d.id} has no EVAL evidence")
                if "guess" in d.get("evidence").lower():
                    unmet.append(f"G3: {d.id} still relies on a guess")
                for e in evals:
                    if e.status != "done":
                        unmet.append(f"G3: {e.id} (evidence for {d.id}) is not done")
    if g >= 4:
        blks = active("BLK")
        if not blks:
            unmet.append("G4: no BLK items")
        for b in blks:
            if b.status == "draft":
                unmet.append(f"G4: {b.id} still draft")
            if not [t for t in tests_of(b.id, kids) if t.get("level").lower() == "unit"]:
                unmet.append(f"G4: {b.id} has no unit TEST")
    if g >= 5:
        for b in active("BLK"):
            if b.status not in ("implemented", "verified"):
                unmet.append(f"G5: {b.id} not implemented")
        for t in active("TEST"):
            if t.get("level").lower() == "unit" and t.status != "passing":
                unmet.append(f"G5: unit {t.id} is {t.status}")
    if g >= 6:
        for t in active("TEST"):
            if t.get("level").lower() in ("integration", "system") and t.status != "passing":
                unmet.append(f"G6: {t.get('level').lower()} {t.id} is {t.status}")
        for s in active("SPEC"):
            if not derived_verified(s, kids, cache):
                unmet.append(f"G6: {s.id} not verified by passing tests")
    if g >= 7:
        for t in active("TEST"):
            if t.get("level").lower() == "acceptance" and t.status != "passing":
                unmet.append(f"G7: acceptance {t.id} is {t.status}")
        for r in reqs:
            if r.get("priority").lower() in ("must",) and not derived_verified(r, kids, cache):
                unmet.append(f"G7: Must requirement {r.id} not verified")
        if not os.path.exists(os.path.join(ROOT, "WRITEUP.md")):
            unmet.append("G7: WRITEUP.md missing")
    return unmet


def write_trace(by_id, kids, cache):
    reqs = sorted([i for i in by_id.values() if i.type == "REQ"], key=lambda i: i.id)
    out = []
    out.append("# Traceability table (GENERATED - do not edit)\n")
    out.append(f"Generated by `scripts/check_trace.py --write-trace` on "
               f"{datetime.now().strftime('%Y-%m-%d %H:%M')}. Edit the source docs instead.\n")
    out.append("Legend: **V** = derived verified (all linked tests passing), "
               "**-** = not yet. Rejected/replaced items are hidden.\n")
    out.append("## Requirements -> everything below them\n")
    out.append("| REQ | Pri | Status | V | SPEC | ARCH / DEC / EVAL | BLK | TEST |")
    out.append("|---|---|---|---|---|---|---|---|")
    for r in reqs:
        if r.status in INACTIVE:
            continue
        d = descendants(r.id, kids)
        grp = lambda *ts: ", ".join(sorted({x.id for x in d if x.type in ts})) or "-"
        v = "V" if derived_verified(r, kids, cache) else "-"
        out.append(f"| {r.id} | {r.get('priority')} | {r.status} | {v} | {grp('SPEC')} | "
                   f"{grp('ARCH', 'DEC', 'EVAL')} | {grp('BLK')} | {grp('TEST')} |")
    out.append("\n## Specs and blocks -> tests\n")
    out.append("| Item | Status | V | Tests (status) |")
    out.append("|---|---|---|---|")
    for it in sorted([i for i in by_id.values() if i.type in ("SPEC", "BLK")], key=lambda i: i.id):
        if it.status in INACTIVE:
            continue
        ts = tests_of(it.id, kids)
        tl = ", ".join(f"{t.id} ({t.status})" for t in sorted(ts, key=lambda t: t.id)) or "-"
        v = "V" if derived_verified(it, kids, cache) else "-"
        out.append(f"| {it.id} | {it.status} | {v} | {tl} |")
    out.append("\n## Decisions\n")
    out.append("| DEC | Status | Chooses | Evidence | Traces to | Replaced by |")
    out.append("|---|---|---|---|---|---|")
    for d in sorted([i for i in by_id.values() if i.type == "DEC"], key=lambda i: i.id):
        out.append(f"| {d.id} | {d.status} | {d.get('chooses') or '-'} | {d.get('evidence') or '-'} | "
                   f"{', '.join(d.ids('traces to')) or '-'} | {', '.join(d.ids('replaced by')) or '-'} |")
    gaps = [r.id for r in reqs if r.status not in INACTIVE and not descendants(r.id, kids)]
    out.append("\n## Gaps\n")
    out.append("Requirements with nothing below them yet: " + (", ".join(gaps) if gaps else "none") + "\n")
    with open(TRACE_FILE, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")


def summary(by_id, kids, cache):
    lines = []
    count = defaultdict(lambda: defaultdict(int))
    for it in by_id.values():
        count[it.type][it.status or "?"] += 1
    for t in TYPES:
        if count[t]:
            parts = ", ".join(f"{s} {n}" for s, n in sorted(count[t].items()))
            lines.append(f"  {t:<5} {sum(count[t].values()):>3}  ({parts})")
    reqs = [i for i in by_id.values() if i.type == "REQ" and i.status not in INACTIVE]
    if reqs:
        cov = sum(1 for r in reqs if descendants(r.id, kids))
        ver = sum(1 for r in reqs if derived_verified(r, kids, cache))
        must = [r for r in reqs if r.get("priority").lower() == "must"]
        mver = sum(1 for r in must if derived_verified(r, kids, cache))
        lines.append(f"  Requirements covered by something below: {cov}/{len(reqs)}")
        lines.append(f"  Requirements verified (derived):        {ver}/{len(reqs)}  "
                     f"(Must: {mver}/{len(must)})")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", help="check a stage gate, e.g. G2")
    ap.add_argument("--write-trace", action="store_true", help="regenerate design/trace.md")
    ap.add_argument("--quiet", action="store_true", help="only errors and the summary line")
    a = ap.parse_args()

    if not os.path.isdir(DESIGN):
        print(f"ERROR: no design/ folder at {DESIGN}")
        return 1
    items, by_id, dups = parse()
    results, result_files = load_results()
    rep = check(items, by_id, dups, results)
    kids = children_map(by_id)
    cache = {}

    # promotion hints and false claims
    for it in by_id.values():
        if it.type in ("SPEC", "BLK", "REQ"):
            dv = derived_verified(it, kids, cache)
            if it.status == "verified" and not dv:
                rep.err(it, "status says 'verified' but its tests are not all passing")
            elif dv and it.status in ("agreed", "implemented"):
                rep.info(it, "all its tests pass - can be promoted to 'verified'")

    print(f"check_trace: {len(by_id)} items in design/, "
          f"{len(result_files)} results file(s) found")
    if not a.quiet:
        for line in summary(by_id, kids, cache):
            print(line)
    if rep.errors:
        print(f"\nERRORS ({len(rep.errors)}):")
        for e in rep.errors:
            print("  - " + e)
    if rep.warnings and not a.quiet:
        print(f"\nWARNINGS ({len(rep.warnings)}):")
        for w in rep.warnings:
            print("  - " + w)
    if rep.infos and not a.quiet:
        print(f"\nINFO ({len(rep.infos)}):")
        for i in rep.infos:
            print("  - " + i)

    rc = 1 if rep.errors else 0
    if a.gate:
        unmet = gate_check(a.gate, by_id, kids, cache, rep)
        if unmet:
            print(f"\nGATE {a.gate.upper()}: NOT MET ({len(unmet)} open point(s))")
            for u in unmet:
                print("  - " + u)
            rc = 1
        else:
            print(f"\nGATE {a.gate.upper()}: MET - ask the human to approve it")
    if a.write_trace:
        write_trace(by_id, kids, cache)
        print(f"\nwrote {rel(TRACE_FILE)}")
    print(f"\nresult: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
