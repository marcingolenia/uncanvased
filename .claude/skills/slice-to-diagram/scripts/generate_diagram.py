#!/usr/bin/env python3
"""Generate a canonical Event Modeling Excalidraw board from Uncanvased slice YAML.

Usage:
    generate_diagram.py <path> [<path> ...] [-o board.excalidraw]

Each <path> is a slice `.yaml` file OR a directory (scanned non-recursively for
`*.yaml`). All selected slices are placed on ONE combined left-to-right timeline
and written to a single `.excalidraw` file (default: ./board.excalidraw).

Layout (canonical Event Modeling, colors: blue command / orange event / green
read model / red external):

    WIREFRAMES  | UI mockup, or a  (cog) + actor for automated processes
    CMD / READ  | commands (write, blue)  &  read models (read, green)
    EVENTS      | the orange event timeline spine
    EXTERNAL    | external systems / API calls (translation slices)

Ordering: explicit `sequence:` first, then event-dependency order
(producer left of consumer), then filename. Cycles (e.g. the To-Do-list pattern)
are broken deterministically by the same key.
"""
import argparse
import glob
import json
import os
import random
import sys
import time

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required. Install with: pip install pyyaml")

# --------------------------------------------------------------------------- #
# Palette — (strokeColor, backgroundColor). Canonical Event Modeling colors.
# --------------------------------------------------------------------------- #
PAL = {
    "command":  ("#1971c2", "#a5d8ff"),   # blue   — write
    "event":    ("#e8590c", "#ffd8a8"),   # orange — timeline fact
    "view":     ("#2f9e44", "#b2f2bb"),   # green  — read model
    "wire":     ("#343a40", "#ffffff"),   # white  — UI wireframe
    "field":    ("#868e96", "#f1f3f5"),   # gray   — text input
    "button":   ("#1971c2", "#4dabf7"),   # blue   — button
    "auto":     ("#5f3dc4", "#d0bfff"),   # purple — processor / agent
    "external": ("#c92a2a", "#ffc9c9"),   # red    — external system
    "ghost":    ("#adb5bd", "#f1f3f5"),   # gray   — off-board reference
    "note":     ("#f08c00", "#fff3bf"),   # amber  — annotation
    "lane":     ("#adb5bd", "#ffffff"),
}
ARROW = "#495057"

# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
COL_W = 360           # horizontal space per slice
BOX_W = 250           # standard sticky width
BOX_H = 100           # standard sticky height
START_X = 40
LABEL_X = -250        # lane-label gutter
LANE_Y = {"wire": 70, "cmd": 500, "event": 760, "ext": 1010}
LANE_H = {"wire": 380, "cmd": 200, "event": 200, "ext": 160}
LANE_TITLE = {
    "wire": "WIREFRAMES",
    "cmd": "COMMANDS / READ MODELS",
    "event": "EVENTS",
    "ext": "EXTERNAL SYSTEMS",
}


def box_x(col):
    return START_X + col * COL_W + (COL_W - BOX_W) // 2


# --------------------------------------------------------------------------- #
# Element factory
# --------------------------------------------------------------------------- #
class Board:
    def __init__(self):
        self.els = []
        self.by_id = {}
        self._n = 0
        self.now = int(time.time() * 1000)

    def _id(self, prefix="el"):
        self._n += 1
        return f"{prefix}-{self._n}"

    @staticmethod
    def _rand():
        return random.randint(1, 2 ** 31)

    def _base(self, el):
        el.setdefault("angle", 0)
        el.setdefault("fillStyle", "solid")
        el.setdefault("strokeWidth", 2)
        el.setdefault("strokeStyle", "solid")
        el.setdefault("roughness", 1)
        el.setdefault("opacity", 100)
        el.setdefault("groupIds", [])
        el.setdefault("frameId", None)
        el.setdefault("seed", self._rand())
        el.setdefault("version", 1)
        el.setdefault("versionNonce", self._rand())
        el.setdefault("isDeleted", False)
        el.setdefault("boundElements", [])
        el.setdefault("updated", self.now)
        el.setdefault("link", None)
        el.setdefault("locked", False)
        self.els.append(el)
        self.by_id[el["id"]] = el
        return el

    def rect(self, x, y, w, h, kind, rounded=True):
        stroke, bg = PAL[kind]
        rid = self._id("r")
        self._base({
            "id": rid, "type": "rectangle",
            "x": x, "y": y, "width": w, "height": h,
            "strokeColor": stroke, "backgroundColor": bg,
            "roundness": {"type": 3} if rounded else None,
        })
        return rid

    def text(self, x, y, w, h, s, color="#1e1e1e", size=16, align="center",
             valign="middle", family=1, container=None):
        tid = self._id("t")
        el = {
            "id": tid, "type": "text",
            "x": x, "y": y, "width": w, "height": h,
            "strokeColor": color, "backgroundColor": "transparent",
            "roundness": None,
            "text": s, "fontSize": size, "fontFamily": family,
            "textAlign": align, "verticalAlign": valign,
            "containerId": container, "originalText": s,
            "lineHeight": 1.25, "autoResize": True,
        }
        self._base(el)
        if container and container in self.by_id:
            self.by_id[container]["boundElements"].append({"type": "text", "id": tid})
        return tid

    def labeled(self, x, y, w, h, kind, label, size=16, color=None, rounded=True):
        """A rectangle with centered bound text. Returns box tuple (id, x, y, w, h)."""
        rid = self.rect(x, y, w, h, kind, rounded=rounded)
        self.text(x + 6, y + 6, w - 12, h - 12, label,
                  color=color or "#1e1e1e", size=size, container=rid)
        return (rid, x, y, w, h)

    def line(self, x1, y1, x2, y2, color="#dee2e6"):
        lid = self._id("l")
        self._base({
            "id": lid, "type": "line",
            "x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1,
            "strokeColor": color, "backgroundColor": "transparent",
            "strokeStyle": "dotted", "roughness": 0, "roundness": None,
            "points": [[0, 0], [x2 - x1, y2 - y1]], "lastCommittedPoint": None,
            "startBinding": None, "endBinding": None,
            "startArrowhead": None, "endArrowhead": None,
        })

    def arrow(self, src, dst, dashed=False):
        """Arrow between two box tuples (id, x, y, w, h), edge-to-edge & bound."""
        _, sx, sy, sw, sh = src
        _, dx, dy, dw, dh = dst
        scx, scy = sx + sw / 2, sy + sh / 2
        dcx, dcy = dx + dw / 2, dy + dh / 2
        p1 = _edge(scx, scy, sw / 2, sh / 2, dcx, dcy)
        p2 = _edge(dcx, dcy, dw / 2, dh / 2, scx, scy)
        aid = self._id("a")
        self._base({
            "id": aid, "type": "arrow",
            "x": p1[0], "y": p1[1],
            "width": abs(p2[0] - p1[0]), "height": abs(p2[1] - p1[1]),
            "strokeColor": ARROW, "backgroundColor": "transparent",
            "strokeStyle": "dashed" if dashed else "solid",
            "roundness": {"type": 2},
            "points": [[0, 0], [p2[0] - p1[0], p2[1] - p1[1]]],
            "lastCommittedPoint": None,
            "startBinding": {"elementId": src[0], "focus": 0, "gap": 4},
            "endBinding": {"elementId": dst[0], "focus": 0, "gap": 4},
            "startArrowhead": None, "endArrowhead": "arrow",
        })
        for end in (src[0], dst[0]):
            if end in self.by_id:
                self.by_id[end]["boundElements"].append({"type": "arrow", "id": aid})

    def dump(self, path):
        maxx = max((e["x"] + e.get("width", 0) for e in self.els), default=1000)
        with open(path, "w") as fh:
            json.dump({
                "type": "excalidraw", "version": 2,
                "source": "uncanvased/slice-to-diagram",
                "elements": self.els,
                "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
                "files": {},
            }, fh, indent=2)
        return maxx


def _edge(cx, cy, hw, hh, tx, ty):
    """Point on a rectangle's border, from its center toward (tx, ty)."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return (cx, cy)
    sx = hw / abs(dx) if dx else float("inf")
    sy = hh / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return (cx + dx * s, cy + dy * s)


# --------------------------------------------------------------------------- #
# Slice loading & ordering
# --------------------------------------------------------------------------- #
def load_slices(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files.extend(sorted(glob.glob(os.path.join(p, "*.yaml"))))
        elif os.path.isfile(p):
            files.append(p)
        else:
            print(f"  ! skipped (not found): {p}", file=sys.stderr)
    slices = []
    for f in files:
        with open(f) as fh:
            data = yaml.safe_load(fh) or {}
        data["_file"] = os.path.basename(f)
        slices.append(data)
    return slices


def _events(s):
    if "events" in s:
        return s["events"] if isinstance(s["events"], list) else [s["events"]]
    if "event" in s:
        return [s["event"]]
    return []


def produced(s):
    """Names this slice makes available to others (events + views)."""
    out = []
    for ev in _events(s):
        if isinstance(ev, dict) and ev.get("name"):
            out.append(ev["name"])
    intern = s.get("internal") or {}
    if intern.get("event"):
        out.append(intern["event"])
    view = s.get("view") or {}
    if view.get("name"):
        out.append(view["name"])
    return out


def consumed(s):
    """Names this slice reads from the timeline."""
    names = list(s.get("sources") or [])
    trig = s.get("trigger") or {}
    for key in ("event", "view"):
        if trig.get(key):
            names.append(trig[key])
    return names


def ordering_deps(s):
    """Causal predecessors used ONLY for left-right ordering.

    Everything `consumed` (sources + trigger) PLUS the events named in each
    scenario's `given:` precondition. The given clause states the timeline
    facts that must already exist for the scenario to run, so a slice sits to
    the RIGHT of whatever produces them — this is what lets a command like
    MergeOrganizations (which only declares its dependency via `given:` /
    `constraints`) land after the slice that records those facts.

    Kept separate from `consumed()` so dependency ARROWS on the board are
    unaffected; only the column order changes.
    """
    names = list(consumed(s))
    for sc in s.get("scenarios") or []:
        for g in sc.get("given") or []:
            if isinstance(g, dict) and g.get("event"):
                names.append(g["event"])
    return names


def _pat_rank(s):
    """Tie-break rank: read models sit left of the writers/processors."""
    return 0 if s.get("pattern") == "state_view" else 1


def _sccs(nodes, adj):
    """Tarjan's strongly-connected components over node ids."""
    idx, low, on, stack, out, counter = {}, {}, set(), [], [], [0]

    def strong(v):
        idx[v] = low[v] = counter[0]
        counter[0] += 1
        stack.append(v)
        on.add(v)
        for w in adj[v]:
            if w not in idx:
                strong(w)
                low[v] = min(low[v], low[w])
            elif w in on:
                low[v] = min(low[v], idx[w])
        if low[v] == idx[v]:
            comp = []
            while True:
                w = stack.pop()
                on.discard(w)
                comp.append(w)
                if w == v:
                    break
            out.append(comp)

    for v in nodes:
        if v not in idx:
            strong(v)
    return out


def order_slices(slices):
    """sequence -> dependency (producer before consumer) -> read-model -> file.

    Dependencies include scenario `given:` events (see ordering_deps). Genuine
    cycles (the To-Do pattern: a view feeding a processor that records an event
    feeding the same view) can't be linearised, so they're broken by picking a
    real cycle member (nontrivial SCC), preferring the read model to its left.
    """
    INF = float("inf")
    key = {id(s): (s.get("sequence", INF), _pat_rank(s), s["_file"]) for s in slices}
    cyc_key = {id(s): (_pat_rank(s), s.get("sequence", INF), s["_file"]) for s in slices}
    producer = {}
    for s in slices:
        for name in produced(s):
            producer.setdefault(name, id(s))
    by_id = {id(s): s for s in slices}
    nodes = list(by_id)
    adj = {n: [] for n in nodes}
    indeg = {n: 0 for n in nodes}
    for s in slices:
        cons = id(s)
        srcs = set()
        for name in ordering_deps(s):
            src = producer.get(name)
            if src is not None and src != cons:
                srcs.add(src)
        for src in srcs:               # one edge per (producer, consumer) pair
            adj[src].append(cons)
            indeg[cons] += 1
    in_cycle = {n for comp in _sccs(nodes, adj) if len(comp) > 1 for n in comp}
    remaining = set(nodes)
    order = []
    while remaining:
        ready = [n for n in remaining if indeg[n] == 0]
        if ready:
            nxt = min(ready, key=lambda n: key[n])
        else:  # cycle — break on a real cycle member, read model first
            pool = [n for n in remaining if n in in_cycle] or list(remaining)
            nxt = min(pool, key=lambda n: cyc_key[n])
        remaining.discard(nxt)
        order.append(by_id[nxt])
        for m in adj[nxt]:
            if m in remaining:
                indeg[m] -= 1
    return order


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render(slices, board):
    registry = {}          # produced name -> box tuple
    deferred = []          # (consumer_box, [names], ghost_lane)

    # lane scaffold
    n = max(len(slices), 1)
    width = START_X + n * COL_W + 40
    for lane, y in LANE_Y.items():
        board.text(LABEL_X + 10, y + 8, 220, 24, LANE_TITLE[lane],
                   color="#868e96", size=14, align="left", family=2)
        board.line(LABEL_X, y - 14, width, y - 14)
    board.text(LABEL_X + 10, LANE_Y["wire"] - 54, 600, 30,
               f"Event Model  —  {len(slices)} slice(s)",
               color="#1e1e1e", size=22, align="left", family=2)

    for col, s in enumerate(slices):
        pat = s.get("pattern")
        if pat == "state_change":
            _state_change(board, col, s, registry)
        elif pat == "state_view":
            _state_view(board, col, s, registry, deferred)
        elif pat == "automation":
            _automation(board, col, s, deferred)
        elif pat == "translation":
            _translation(board, col, s, registry, deferred)
        else:
            board.labeled(box_x(col), LANE_Y["cmd"], BOX_W, BOX_H, "ghost",
                          f"{s.get('slice', '?')}\n(pattern: {pat})")

    # second pass: dependency arrows into consumers (+ ghosts for off-board refs)
    for consumer, names, lane in deferred:
        for name in names:
            src = registry.get(name)
            if src is None:
                gx = consumer[1] + (BOX_W - 200) // 2
                src = board.labeled(gx, LANE_Y[lane] + 30, 200, 70, "ghost",
                                    name, size=13)
                registry[name] = src
            board.arrow(src, consumer, dashed=True)


def _name_line(head, sub=None):
    return f"{head}\n{sub}" if sub else head


def _wireframe(board, col, ui):
    """Draw a UI mockup (inputs, button, outputs list). Returns box tuple."""
    x = box_x(col)
    y = LANE_Y["wire"] + 10
    pad = 12
    cur = y + pad
    screen = ui.get("screen", "Screen")
    inputs = ui.get("inputs") or []
    outputs = ui.get("outputs") or []
    trig = ui.get("trigger") or {}

    # measure
    h = pad + 30                       # title
    h += len(inputs) * 46
    if trig.get("label"):
        h += 48
    if outputs:
        h += 26 + len(outputs) * 22 + 10
    h = min(max(h, 90), LANE_H["wire"] - 20)

    cid = board.rect(x, y, BOX_W, h, "wire")
    board.text(x + pad, cur, BOX_W - 2 * pad, 24, screen, size=17,
               align="left", family=2)
    cur += 34
    inner = x + pad
    iw = BOX_W - 2 * pad
    for inp in inputs:
        fld = inp.get("field", "?")
        board.text(inner, cur, iw, 16, fld, color="#868e96", size=12,
                   align="left", family=2)
        cur += 18
        frid = board.rect(inner, cur, iw, 24, "field")
        board.text(inner + 6, cur + 4, iw - 12, 16, inp.get("type", ""),
                   color="#adb5bd", size=11, align="left", family=2,
                   container=None)
        cur += 30
    if trig.get("label"):
        bw = min(iw, 150)
        board.labeled(inner, cur, bw, 34, "button", trig["label"],
                      size=14, color="#ffffff")
        cur += 46
    if outputs:
        lh = 22 * len(outputs) + 14
        board.rect(inner, cur, iw, lh, "field")
        oy = cur + 8
        for o in outputs:
            board.text(inner + 8, oy, iw - 16, 18,
                       f"• {o.get('name', '?')}", color="#495057", size=12,
                       align="left", family=2)
            oy += 22
    return (cid, x, y, BOX_W, h)


def _agent(board, col, s):
    """Cog + actor node in the wireframe lane (automated processes).

    The cog is drawn as its OWN element in the emoji-capable font (family 2).
    Bound labels use the hand-drawn font (family 1), which has no emoji glyph,
    so an inline ⚙️ there renders as blank tofu — hence the separate element.
    """
    x = box_x(col)
    y = LANE_Y["wire"] + 10
    w, h = BOX_W, 96
    actor = s.get("actor", "System Agent")
    proc = s.get("processor")
    rid = board.rect(x, y, w, h, "auto")
    board.text(x + 14, y + h / 2 - 22, 44, 44, "⚙️", color="#5f3dc4", size=34,
               align="left", valign="middle", family=2)
    board.text(x + 64, y + 14, w - 76, h - 28, _name_line(actor, proc),
               color="#1e1e1e", size=14, align="left", valign="middle", family=2)
    return (rid, x, y, w, h)


def _state_change(board, col, s, registry):
    ui = s.get("ui") or {}
    wf = _wireframe(board, col, ui) if ui else None
    cmd = s.get("command") or {}
    cbox = board.labeled(box_x(col), LANE_Y["cmd"], BOX_W, BOX_H,
                         "command", cmd.get("name", s.get("slice", "Command")))
    prev = cbox
    for ev in _events(s):
        name = ev.get("name", "Event") if isinstance(ev, dict) else str(ev)
        ebox = board.labeled(box_x(col), LANE_Y["event"], BOX_W, BOX_H,
                             "event", name)
        board.arrow(prev, ebox)
        if isinstance(ev, dict) and ev.get("name"):
            registry.setdefault(ev["name"], ebox)
    if wf:
        board.arrow(wf, cbox)


def _state_view(board, col, s, registry, deferred):
    view = s.get("view") or {}
    vbox = board.labeled(box_x(col), LANE_Y["cmd"], BOX_W, BOX_H,
                         "view", view.get("name", s.get("slice", "View")))
    if view.get("name"):
        registry.setdefault(view["name"], vbox)
    ui = s.get("ui") or {}
    if ui:
        wf = _wireframe(board, col, ui)
        board.arrow(vbox, wf)          # read model feeds the UI
    deferred.append((vbox, list(s.get("sources") or []), "event"))


def _automation(board, col, s, deferred):
    agent = _agent(board, col, s)
    cmd = s.get("command") or {}
    cbox = board.labeled(box_x(col), LANE_Y["cmd"], BOX_W, BOX_H,
                         "command", cmd.get("name", "Command"))
    board.arrow(agent, cbox)
    deferred.append((cbox, consumed(s), "event"))


def _translation(board, col, s, registry, deferred):
    intern = s.get("internal") or {}
    ext = s.get("external") or {}
    call = s.get("external_call") or {}
    ibox = board.labeled(box_x(col), LANE_Y["event"], BOX_W, BOX_H,
                         "event", intern.get("event", "Event"))
    if intern.get("event"):
        registry.setdefault(intern["event"], ibox)

    if call:  # variant B: request-response
        # Chain reads: source view -> agent (reads To-Do) -> records event; the
        # external call (in its own lane) feeds the recorded event. Arrows are
        # routed agent->event and call->event so none crosses the event box.
        agent = _agent(board, col, s)
        cbox = board.labeled(box_x(col), LANE_Y["ext"], BOX_W, 90, "external",
                             _name_line(call.get("system", "External"),
                                        call.get("action")), size=13)
        board.arrow(agent, ibox)
        board.arrow(cbox, ibox)
        deferred.append((agent, list(s.get("sources") or []), "cmd"))
    else:     # variant A: event-driven boundary crossing
        ebox = board.labeled(box_x(col), LANE_Y["ext"], BOX_W, 90, "external",
                             _name_line(ext.get("system", "External"),
                                        ext.get("event")), size=13)
        if s.get("direction") == "outbound":
            board.arrow(ibox, ebox)
        else:
            board.arrow(ebox, ibox)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Uncanvased slices -> Excalidraw board")
    ap.add_argument("paths", nargs="+", help="slice .yaml files and/or directories")
    ap.add_argument("-o", "--output", default="board.excalidraw")
    args = ap.parse_args()

    slices = load_slices(args.paths)
    if not slices:
        sys.exit("No slices found.")
    ordered = order_slices(slices)
    board = Board()
    render(ordered, board)
    board.dump(args.output)
    print(f"Wrote {args.output}  ({len(ordered)} slices)")
    for i, s in enumerate(ordered):
        print(f"  {i + 1}. {s.get('slice', s['_file'])}  [{s.get('pattern', '?')}]")


if __name__ == "__main__":
    main()
