#!/usr/bin/env python3
"""Generate a canonical Event Modeling Excalidraw board from Uncanvased slice YAML.

Usage:
    generate_diagram.py <path> [<path> ...] [-o board.excalidraw]

Each <path> is a slice `.yaml` file OR a directory (scanned non-recursively for
`*.yaml`). All selected slices are placed on ONE combined left-to-right timeline
and written to a single `.excalidraw` file (default: ./board.excalidraw).

Layout (canonical Event Modeling, colors: blue command / orange event / green
read model / red external):

    <ACTOR> ...  | one swimlane per actor: UI mockups and  (cog) processors only
    CMD / READ   | commands (write, blue)  &  read models (read, green)
    EVENTS       | the orange event timeline spine
    EXTERNAL     | external events (translation) and API calls (automation)

Arrows never point left. Events are the only shared contract: a slice that
reads an event produced further right gets its own hatched "(duplicate)" copy
of it. Commands and read models are never duplicated.

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
    "dup":      ("#e8590c", "#ffd8a8"),   # orange, hatched + dashed — duplicated event
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
TOP_Y = 70            # first actor swimlane
LANE_PAD = 20         # space above/below the tallest element in an actor lane
AGENT_H = 96          # cog + processor node
LANE_H = {"cmd": 200, "event": 200, "ext": 160}
LANE_TITLE = {
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
        self.lane_y = {}       # lane key (actor name, "cmd", "event", "ext") -> y
        self.sid = None        # `id` of the slice being drawn (corner badge)
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
        el = {
            "id": rid, "type": "rectangle",
            "x": x, "y": y, "width": w, "height": h,
            "strokeColor": stroke, "backgroundColor": bg,
            "roundness": {"type": 3} if rounded else None,
        }
        if kind in ("dup", "ghost"):
            el["strokeStyle"] = "dashed"
        if kind == "dup":
            el["fillStyle"] = "hachure"
        self._base(el)
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

    def tag(self, box, sid=None):
        """Slice-id badge in the box's top-right corner, grouped with the box
        (and its label) so they move together. Returns the box unchanged."""
        sid = self.sid if sid is None else sid
        if sid is None or sid == "":
            return box
        rid, x, y, w, h = box
        tid = self.text(x + w - 56, y + 4, 50, 14, str(sid), color="#868e96",
                        size=11, align="right", valign="top", family=2)
        gid = self._id("g")
        label = [b["id"] for b in self.by_id[rid]["boundElements"] if b["type"] == "text"]
        for eid in [rid, tid] + label:
            self.by_id[eid]["groupIds"].append(gid)
        return box

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
    # A fully sequenced board is an authored timeline: honour it as drawn.
    # (state_change slices consume nothing, so dependency order alone would
    # float every one of them to the far left.)
    if all("sequence" in s for s in slices):
        return sorted(slices, key=lambda s: key[id(s)])
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
# Layout plan: columns, duplicated events, swimlanes
# --------------------------------------------------------------------------- #
def _ename(ev):
    return ev.get("name", "Event") if isinstance(ev, dict) else str(ev)


def actor_lane(s):
    """Swimlane of a slice's top element. A "(processor)" qualifier on the
    actor is dropped, so every `System Agent (...)` shares one lane."""
    default = ("System Agent" if s.get("pattern") in ("automation", "translation")
               else "User")
    actor = str(s.get("actor") or default).split("(")[0].strip()
    return actor or default


def has_top(s):
    """Only UIs and processors live in the actor swimlanes."""
    return s.get("pattern") in ("automation", "translation") or bool(s.get("ui"))


def ext_system(s):
    """External system a slice touches: an automation's call or a
    translation's source. Each one gets a swimlane below the events."""
    if s.get("pattern") == "automation":
        call = s.get("external_call") or {}
        return (call.get("system") or "External") if call else None
    if s.get("pattern") == "translation":
        return (s.get("external") or {}).get("system") or "External"
    return None


def plan(slices):
    """Give each slice its columns and split what it reads into
    - refs:   produced further left → arrow from the nearest box on the left;
    - copies: events produced further right (re-drawn as hatched duplicates in
              the consumer's own columns) or names nobody produces (ghosts).
    Read models are never duplicated: a read model on the right is a
    sequencing error, reported and left unconnected."""
    ev_at, view_at = {}, {}
    for i, s in enumerate(slices):
        for ev in _events(s):
            ev_at.setdefault(_ename(ev), []).append(i)
        name = (s.get("view") or {}).get("name")
        if name:
            view_at.setdefault(name, i)
    plans, col = [], 0
    for i, s in enumerate(slices):
        refs, copies = [], []
        for name in dict.fromkeys(consumed(s)):
            if name in view_at:
                if view_at[name] < i:
                    refs.append(name)
                else:
                    print(f"  ! read model {name} sits right of its reader in "
                          f"{s['_file']}; no arrow drawn (fix `sequence:`)",
                          file=sys.stderr)
            elif name in ev_at:
                if min(ev_at[name]) < i:
                    refs.append(name)
                else:
                    copies.append((name, "dup"))
            else:
                copies.append((name, "ghost"))
                print(f"  ! off-board reference drawn as ghost: {name}",
                      file=sys.stderr)
        pat = s.get("pattern")
        if pat == "state_change":
            width = max(1, len(_events(s)))
        elif pat == "state_view":
            width = max(1, len(copies))      # copies share the view's columns
        elif pat == "automation":
            width = len(copies) + 1          # own event takes the last column
        elif pat == "translation":
            width = 2
        else:
            width = 1
        plans.append({"col": col, "span": width, "refs": refs, "copies": copies})
        col += width
    return plans, col


def merge_screens(slices):
    """Storyboard rule: a screen is one frame in time. A state_view whose UI is
    the same screen as the very next state_change's is that screen showing the
    read model, with the button for the next command: draw it once, in the
    state_change's column. Returns {state_change index: merged ui} and the set
    of state_view indexes whose UI was absorbed."""
    merged, absorbed = {}, set()
    for i in range(len(slices) - 1):
        v, c = slices[i], slices[i + 1]
        vui, cui = v.get("ui") or {}, c.get("ui") or {}
        if (v.get("pattern") == "state_view" and c.get("pattern") == "state_change"
                and vui.get("screen") and vui.get("screen") == cui.get("screen")):
            outs = {o.get("name"): o for o in (vui.get("outputs") or [])}
            for o in cui.get("outputs") or []:
                outs.setdefault(o.get("name"), o)
            merged[i + 1] = {**cui, "outputs": list(outs.values())}
            absorbed.add(i)
    return merged, absorbed


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render(slices, board):
    plans, ncols = plan(slices)
    merged, absorbed = merge_screens(slices)
    uis = {i: merged.get(i, s.get("ui")) for i, s in enumerate(slices)
           if s.get("ui") and i not in absorbed}

    # swimlanes: actors on top, then commands/read models, events, systems
    actors = list(dict.fromkeys(actor_lane(s) for s in slices if has_top(s)))
    systems = list(dict.fromkeys(x for x in map(ext_system, slices) if x))
    top_h = {a: AGENT_H for a in actors}
    for i, ui in uis.items():
        a = actor_lane(slices[i])
        top_h[a] = max(top_h[a], wire_h(ui))
    lanes, y = [], TOP_Y
    for a in actors:
        lanes.append((a, a, y))
        y += top_h[a] + 2 * LANE_PAD
    for key in ("cmd", "event"):
        lanes.append((key, LANE_TITLE[key], y))
        y += LANE_H[key]
    for x in systems:
        lanes.append((("ext", x), f"{x}  (external)", y))
        y += LANE_H["ext"]
    board.lane_y = {key: ly for key, _, ly in lanes}

    width = START_X + max(ncols, 1) * COL_W + 40
    for _, title, ly in lanes:
        board.text(LABEL_X + 10, ly + 8, 220, 24, title,
                   color="#868e96", size=14, align="left", family=2)
        board.line(LABEL_X, ly - 14, width, ly - 14)
    board.text(LABEL_X + 10, TOP_Y - 54, 600, 30,
               f"Event Model  —  {len(slices)} slice(s)",
               color="#1e1e1e", size=22, align="left", family=2)

    producer_id = {}       # event name -> `id` of the first slice producing it
    for s in slices:
        for ev in _events(s):
            producer_id.setdefault(_ename(ev), s.get("id"))
    events = {}            # event name -> [(col, box)], originals + duplicates
    views = {}             # view name  -> box (drawn once, in its own slice)
    links = []             # (consumer box, consumer col, refs)
    feeds = None           # (view box, slice id) whose screen the next state_change draws
    for i, (s, p) in enumerate(zip(slices, plans)):
        col, pat = p["col"], s.get("pattern")
        board.sid = s.get("id")
        top = (board.lane_y[actor_lane(s)] + LANE_PAD) if has_top(s) else None
        copies = []
        for k, (name, kind) in enumerate(p["copies"]):
            cbox = _copy(board, col + k, name, kind)
            if kind == "dup":              # a copy carries its producer's id
                board.tag(cbox, producer_id.get(name))
            copies.append(cbox)
            if kind == "dup":
                events.setdefault(name, []).append((col + k, cbox))
        last = col + p["span"] - 1
        if pat == "state_change":
            consumer = _state_change(board, col, s, top, events,
                                     uis.get(i), feeds if i in merged else None)
        elif pat == "state_view":
            consumer = _state_view(board, last, s, top, views, uis.get(i))
            feeds = (consumer, s.get("id")) if i in absorbed else None
        elif pat == "automation":
            consumer = _automation(board, last, s, top, events)
        elif pat == "translation":
            consumer = _translation(board, col, s, top, events, views)
        else:
            consumer = board.labeled(box_x(col), board.lane_y["cmd"], BOX_W, BOX_H,
                                     "ghost", f"{s.get('slice', '?')}\n(pattern: {pat})")
            print(f"  ! unknown pattern '{pat}' in {s['_file']}", file=sys.stderr)
        for cbox in copies:
            board.arrow(cbox, consumer, dashed=True)
        links.append((consumer, last, p["refs"]))

    # dependency arrows: from the nearest box at or left of the consumer
    for consumer, ccol, refs in links:
        for name in refs:
            if name in views:
                src = views[name]
            else:
                src = max((cb for cb in events[name] if cb[0] <= ccol),
                          key=lambda cb: cb[0])[1]
            board.arrow(src, consumer, dashed=True)


def _copy(board, col, name, kind):
    """A duplicated event (hatched, dashed, marked) or a ghost for a name no
    selected slice produces, in the events lane of the consumer's column."""
    if kind == "dup":
        return board.labeled(box_x(col), board.lane_y["event"], BOX_W, BOX_H,
                             "dup", f"{name}\n(duplicate)")
    gx = box_x(col) + (BOX_W - 200) // 2
    return board.labeled(gx, board.lane_y["event"] + 15, 200, 70, "ghost", name,
                         size=13)


def _name_line(head, sub=None):
    return f"{head}\n{sub}" if sub else head


def wire_h(ui):
    """Height of a UI mockup, so its actor lane can be sized to fit."""
    h = 12 + 30                         # padding + title
    h += len(ui.get("inputs") or []) * 46
    if (ui.get("trigger") or {}).get("label"):
        h += 48
    if ui.get("outputs"):
        h += 26 + len(ui["outputs"]) * 22 + 10
    return max(h, 90)


def _wireframe(board, col, ui, y):
    """Draw a UI mockup (inputs, button, outputs list). Returns box tuple."""
    x = box_x(col)
    pad = 12
    cur = y + pad
    screen = ui.get("screen", "Screen")
    inputs = ui.get("inputs") or []
    outputs = ui.get("outputs") or []
    trig = ui.get("trigger") or {}
    h = wire_h(ui)

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
        board.rect(inner, cur, iw, 24, "field")
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


def _agent(board, col, s, y):
    """Cog + processor node in the actor's swimlane.

    The cog is drawn as its OWN element in the emoji-capable font (family 2).
    Bound labels use the hand-drawn font (family 1), which has no emoji glyph,
    so an inline ⚙️ there renders as blank tofu — hence the separate element.
    The lane already names the actor, so the node names the processor.
    """
    x = box_x(col)
    w, h = BOX_W, AGENT_H
    actor = str(s.get("actor") or "System Agent")
    qual = actor[actor.index("(") + 1:actor.rindex(")")] if "(" in actor and ")" in actor else None
    label = s.get("processor") or qual or actor
    timer = (s.get("trigger") or {}).get("timer")
    if timer:
        label += f"\n⏱ {timer}"
    rid = board.rect(x, y, w, h, "auto")
    box = (rid, x, y, w, h)
    board.text(x + 14, y + h / 2 - 22, 44, 44, "⚙️", color="#5f3dc4", size=34,
               align="left", valign="middle", family=2)
    board.text(x + 64, y + 14, w - 76, h - 28, label,
               color="#1e1e1e", size=14, align="left", valign="middle", family=2)
    return board.tag(box)


def _command(board, col, s, default="Command"):
    cmd = s.get("command") or {}
    return board.tag(board.labeled(box_x(col), board.lane_y["cmd"], BOX_W, BOX_H,
                                   "command", cmd.get("name", default)))


def _event(board, col, ev, events):
    name = _ename(ev)
    ebox = board.labeled(box_x(col), board.lane_y["event"], BOX_W, BOX_H,
                         "event", name)
    events.setdefault(name, []).append((col, ebox))
    return board.tag(ebox)


def _external(board, col, system, detail):
    system = system or "External"
    return board.tag(board.labeled(box_x(col), board.lane_y[("ext", system)] + 30,
                                   BOX_W, 90, "external", _name_line(system, detail),
                                   size=13))


def _state_change(board, col, s, top, events, ui, view=None):
    """`view`: (read model box, slice id) feeding this screen when it was merged
    with the preceding state_view's (see merge_screens); the screen's badge
    then names both slices, e.g. `12·13`."""
    cbox = _command(board, col, s, s.get("slice", "Command"))
    for i, ev in enumerate(_events(s)):
        board.arrow(cbox, _event(board, col + i, ev, events))
    if ui:
        wf = _wireframe(board, col, ui, top)
        board.arrow(wf, cbox)
        if view:
            board.arrow(view[0], wf)   # read model feeds the screen
            ids = [x for x in (view[1], board.sid) if x is not None]
            board.tag(wf, "·".join(map(str, ids)))
        else:
            board.tag(wf)
    return cbox


def _state_view(board, col, s, top, views, ui):
    view = s.get("view") or {}
    vbox = board.labeled(box_x(col), board.lane_y["cmd"], BOX_W, BOX_H,
                         "view", view.get("name", s.get("slice", "View")))
    board.tag(vbox)
    if view.get("name"):
        views.setdefault(view["name"], vbox)
    if ui:
        board.arrow(vbox, board.tag(_wireframe(board, col, ui, top)))   # read model feeds the UI
    return vbox


def _automation(board, col, s, top, events):
    """Read Model (to-do) ⇢ ⚙️ → Command → Event; an `external_call` sits in its
    system's swimlane below the events and feeds the recorded event."""
    agent = _agent(board, col, s, top)
    cbox = _command(board, col, s)
    board.arrow(agent, cbox)
    ebox = None
    for ev in _events(s)[:1]:
        ebox = _event(board, col, ev, events)
        board.arrow(cbox, ebox)
    call = s.get("external_call") or {}
    if call:
        xbox = _external(board, col, call.get("system"), call.get("action"))
        if ebox:
            board.arrow(xbox, ebox, dashed=True)
    return agent


def _translation(board, col, s, top, events, views):
    """External Event → Read Model | ⚙️ → Command → internal Event, over two
    columns: the view and its external event, then the processor chain."""
    ext = s.get("external") or {}
    xbox = _external(board, col, ext.get("system"), ext.get("event"))
    view = s.get("view") or {}
    vbox = board.labeled(box_x(col), board.lane_y["cmd"], BOX_W, BOX_H,
                         "view", view.get("name", "View"))
    board.tag(vbox)
    if view.get("name"):
        views.setdefault(view["name"], vbox)
    board.arrow(xbox, vbox)

    agent = _agent(board, col + 1, s, top)
    board.arrow(vbox, agent, dashed=True)
    cbox = _command(board, col + 1, s)
    board.arrow(agent, cbox)
    for ev in _events(s)[:1]:
        board.arrow(cbox, _event(board, col + 1, ev, events))
    return vbox


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
