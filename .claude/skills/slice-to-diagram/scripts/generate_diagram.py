#!/usr/bin/env python3
"""Generate a canonical Event Modeling Excalidraw board from Uncanvased slice YAML.

Usage:
    generate_diagram.py <path> [<path> ...] [-o board.excalidraw]
                        [--compact] [--no-specs]

Each <path> is a slice `.yaml` file OR a directory (scanned non-recursively for
`*.yaml`). All selected slices are placed on ONE combined left-to-right timeline
and written to a single `.excalidraw` file (default: ./board.excalidraw).

The board reads like a storyboard (Adam Dymitruk's Event Modeling):

    <ACTOR> ...     | one swimlane per actor: UI mockups (with example data) and
                    |  (cog) processors only
    CMD / READ      | commands (blue) and read models (green), with their fields
    EVENTS · <ctx>  | one orange event lane per stream (`context:`), with fields
    <SYSTEM>        | one lane per external system (API calls, external events)
    SPECIFICATIONS  | each slice's Given / When / Then scenarios, under its column

Arrows never point left. Events are the only shared contract: a slice that
reads an event produced further right gets its own hatched "(duplicate)" copy
of it, and the script prints a story hint (the reader probably belongs later in
the story). A to-do list's own closing event (the event its processor records)
is shown on the read model as "cleared by …" instead: that is the To-Do pattern,
not a storytelling error. Commands and read models are never duplicated.

Every element carries its slice `id` as a corner badge.

Ordering: explicit `sequence:` first, then event-dependency order
(producer left of consumer), then filename.
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
    "error":    ("#c92a2a", "#ffe3e3"),   # red    — rejected command (spec)
    "note":     ("#495057", "#ffffff"),   # white  — note / message
    "ghost":    ("#adb5bd", "#f1f3f5"),   # gray   — off-board reference
    "dup":      ("#e8590c", "#ffd8a8"),   # orange, hatched + dashed — duplicated event
    "spec":     ("#ced4da", "#f8f9fa"),   # light  — scenario frame
}
# Swimlane band fills — light tints behind each lane (no outline).
LANE_BG = {
    "actor": "#f8f9fa",   # light gray   — actor UIs / processors
    "cmd":   "#f1f3f5",   # gray         — commands & read models
    "event": "#fff4e6",   # light orange — event streams
    "ext":   "#f3f0ff",   # light purple — external systems
    "spec":  "#f8f9fa",   # light gray   — specifications
}
LANE_GAP = 8          # white gap between adjacent lane bands

ARROW = "#495057"
MUTED = "#868e96"

# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
COL_W = 360           # horizontal space per column
BOX_W = 250           # standard sticky width
BOX_H = 100           # compact sticky height
DUP_H = 70            # duplicated event / ghost
START_X = 40
LABEL_X = -250        # lane-label gutter
TOP_Y = 70            # first actor swimlane
LANE_PAD = 20         # space above/below the tallest element in a lane
AGENT_H = 96          # cog + processor node
EXT_H = 120           # external-system lane (5 wrapped detail lines)
CHARS = 34            # characters per field line in a sticky (font 12)


def box_x(col):
    return START_X + col * COL_W + (COL_W - BOX_W) // 2


def _clip(s, n=CHARS):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def _fmt(v):
    """A value as shown on a sticky: scalars plain, structures inline."""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, default=str)
    return str(v)


def _wrap(s, n):
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return lines + [cur] if cur else lines or [""]


def field_lines(fields, tags=()):
    """`name: type` lines for a sticky; DCB tags are marked."""
    if not isinstance(fields, dict):
        return []
    return [_clip(f"{k}: {_fmt(t)}" + ("  (tag)" if k in tags else ""))
            for k, t in fields.items()]


def data_lines(data):
    """`key: value` lines for a scenario sticky."""
    if isinstance(data, dict):
        return [_clip(f"{k}: {_fmt(v)}") for k, v in data.items()]
    return [_clip(_fmt(data))] if data not in (None, "", {}) else []


# --------------------------------------------------------------------------- #
# Element factory
# --------------------------------------------------------------------------- #
class Board:
    def __init__(self):
        self.els = []
        self.by_id = {}
        self._n = 0
        self.lane_y = {}       # lane key -> y of its top edge
        self.sid = None        # `id` of the slice being drawn (corner badge)
        self.members = {}      # box id -> element ids that move with it
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

    def attach(self, box_id, *el_ids):
        """Make elements move with a box (grouped at dump time)."""
        self.members.setdefault(box_id, [box_id]).extend(el_ids)

    def rect(self, x, y, w, h, kind, rounded=True):
        stroke, bg = PAL[kind]
        rid = self._id("r")
        el = {
            "id": rid, "type": "rectangle",
            "x": x, "y": y, "width": w, "height": h,
            "strokeColor": stroke, "backgroundColor": bg,
            "roundness": {"type": 3} if rounded else None,
        }
        if kind in ("dup", "ghost", "spec"):
            el["strokeStyle"] = "dashed"
        if kind == "spec":
            el["strokeWidth"] = 1
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
            self.attach(container, tid)
        return tid

    def labeled(self, x, y, w, h, kind, label, size=16, color=None, rounded=True):
        """A rectangle with centered bound text. Returns box tuple (id, x, y, w, h)."""
        rid = self.rect(x, y, w, h, kind, rounded=rounded)
        self.text(x + 6, y + 6, w - 12, h - 12, label,
                  color=color or "#1e1e1e", size=size, container=rid)
        return (rid, x, y, w, h)

    def sticky(self, x, y, kind, name, lines=(), extra=(), title_size=16,
               line_size=12, w=BOX_W, h=None):
        """A sticky with its name on top and a field / data list under it.
        `extra` lines (e.g. "cleared by …") are drawn muted after the fields."""
        h = h or sticky_h(name, lines, extra, title_size, line_size)
        rid = self.rect(x, y, w, h, kind)
        th = title_h(name, title_size)
        self.text(x + 6, y + 6, w - 12, th, "\n".join(_wrap(name, title_chars(title_size))),
                  size=title_size, valign="top", container=rid)
        cur = y + 8 + th
        lh = round(line_size * 1.25)
        if lines:
            t = self.text(x + 12, cur, w - 24, lh * len(lines), "\n".join(lines),
                          color="#343a40", size=line_size, align="left",
                          valign="top", family=2)
            self.attach(rid, t)
            cur += lh * len(lines) + 4
        if extra:
            t = self.text(x + 12, cur, w - 24, lh * len(extra), "\n".join(extra),
                          color=MUTED, size=line_size, align="left",
                          valign="top", family=2)
            self.attach(rid, t)
        return (rid, x, y, w, h)

    def tag(self, box, sid=None):
        """Slice-id badge in the box's top-right corner. Returns the box."""
        sid = self.sid if sid is None else sid
        if sid is None or sid == "":
            return box
        rid, x, y, w, h = box
        tid = self.text(x + w - 56, y + 4, 50, 14, str(sid), color=MUTED,
                        size=11, align="right", valign="top", family=2)
        self.attach(rid, tid)
        return box

    def band(self, x, y, w, h, bg):
        """Borderless, lightly filled swimlane background."""
        bid = self._id("b")
        self._base({
            "id": bid, "type": "rectangle",
            "x": x, "y": y, "width": w, "height": h,
            "strokeColor": "transparent", "backgroundColor": bg,
            "strokeWidth": 1, "roughness": 0, "roundness": {"type": 3},
        })
        return self.by_id[bid]

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
        for ids in self.members.values():      # a box moves with its parts
            if len(ids) > 1:
                gid = self._id("g")
                for eid in dict.fromkeys(ids):
                    self.by_id[eid]["groupIds"].append(gid)
        with open(path, "w") as fh:
            json.dump({
                "type": "excalidraw", "version": 2,
                "source": "uncanvased/slice-to-diagram",
                "elements": self.els,
                "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
                "files": {},
            }, fh, indent=2)


def _edge(cx, cy, hw, hh, tx, ty):
    """Point on a rectangle's border, from its center toward (tx, ty)."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return (cx, cy)
    sx = hw / abs(dx) if dx else float("inf")
    sy = hh / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return (cx + dx * s, cy + dy * s)


def title_chars(size):
    return 26 if size >= 16 else 32


def title_h(name, size=16):
    return round(size * 1.25) * len(_wrap(name, title_chars(size)))


def sticky_h(name, lines=(), extra=(), title_size=16, line_size=12):
    lh = round(line_size * 1.25)
    h = 8 + title_h(name, title_size) + 8
    if lines:
        h += lh * len(lines) + 4
    h += lh * len(extra)
    return max(h + 8, 44)


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
# Layout plan: columns, duplicated events, to-do closures, swimlanes
# --------------------------------------------------------------------------- #
def _ename(ev):
    return ev.get("name", "Event") if isinstance(ev, dict) else str(ev)


def _who(s):
    sid = s.get("id")
    return f"{s.get('slice', s['_file'])}" + (f" (#{sid})" if sid is not None else "")


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


def stream(s):
    """Event lane of a slice's events: its `context` (the event stream)."""
    return str(s.get("context") or "").strip()


def ext_system(s):
    """External system a slice touches: an automation's call or a
    translation's source. Each one gets a swimlane below the events."""
    if s.get("pattern") == "automation":
        call = s.get("external_call") or {}
        return (call.get("system") or "External") if call else None
    if s.get("pattern") == "translation":
        return (s.get("external") or {}).get("system") or "External"
    return None


def plan(slices, absorbed=()):
    """Give each slice its columns and split what it reads into
    - refs:    produced further left → arrow from the nearest box on the left;
    - loops:   events recorded by this view's OWN consumer — the processor it
               triggers (To-Do pattern: "cleared by …") or the command behind
               the button on the screen it feeds ("updated by …"). They change
               the view after it was read; shown on the view, never drawn
               backwards and never a storytelling error;
    - copies:  other events produced further right (re-drawn as hatched
               duplicates in the reader's own columns, with a story hint) or
               names nobody produces (ghosts).
    Read models are never duplicated: a read model on the right is a
    sequencing error, reported and left unconnected."""
    ev_at, view_at, triggered = {}, {}, {}
    for i, s in enumerate(slices):
        for ev in _events(s):
            ev_at.setdefault(_ename(ev), []).append(i)
        name = (s.get("view") or {}).get("name")
        if name:
            view_at.setdefault(name, i)
        tv = (s.get("trigger") or {}).get("view")
        if tv:
            triggered.setdefault(tv, []).append(i)
    plans, col, hints = [], 0, 0
    for i, s in enumerate(slices):
        vname = (s.get("view") or {}).get("name")
        closers = {_ename(ev): "cleared by"
                   for j in triggered.get(vname, ()) for ev in _events(slices[j])}
        if i in absorbed:              # this view's screen sends the next command
            closers.update({_ename(ev): "updated by" for ev in _events(slices[i + 1])})
        refs, cleared, copies = [], [], []
        for name in dict.fromkeys(consumed(s)):
            if name in view_at:
                if view_at[name] < i:
                    refs.append(name)
                else:
                    print(f"  ! read model {name} sits right of its reader "
                          f"{_who(s)}; no arrow drawn (fix `sequence:`)",
                          file=sys.stderr)
            elif name in ev_at:
                if min(ev_at[name]) < i:
                    refs.append(name)
                elif name in closers:
                    cleared.append(f"{closers[name]} {name}")
                else:
                    copies.append((name, "dup"))
                    hints += 1
                    print(f"  ~ story: {_who(s)} reads {name}, which happens later "
                          f"in {_who(slices[min(ev_at[name])])}. If the reader belongs "
                          f"after it in the story, raise its `sequence:`; drawn as a "
                          f"duplicate", file=sys.stderr)
            else:
                copies.append((name, "ghost"))
                print(f"  ! off-board reference drawn as ghost: {name}",
                      file=sys.stderr)
        pat = s.get("pattern")
        if pat == "state_change":
            width, anchor = max(1, len(_events(s))), col
        elif pat == "state_view":
            width = max(1, len(copies))      # copies share the view's columns
            anchor = col + width - 1
        elif pat == "automation":
            width = len(copies) + 1          # own chain takes the last column
            anchor = col + width - 1
        elif pat == "translation":
            width, anchor = 2, col + 1
        else:
            width, anchor = 1, col
        plans.append({"col": col, "span": width, "anchor": anchor, "refs": refs,
                      "cleared": cleared, "copies": copies})
        col += width
    return plans, col, hints


def ui_with_examples(s):
    """The slice's UI with example values on inputs and outputs: an explicit
    `example:` wins, else the first value the slice's scenarios give that field
    (WHEN payload, THEN data, GIVEN view data). A storyboard shows data."""
    ui = s.get("ui")
    if not ui:
        return None
    ex = {}
    for sc in s.get("scenarios") or []:
        srcs = [(sc.get("when") or {}).get("payload"), (sc.get("then") or {}).get("data")]
        srcs += [g.get("data") for g in sc.get("given") or []
                 if isinstance(g, dict) and g.get("view")]
        for src in srcs:
            if isinstance(src, dict):
                for k, v in src.items():
                    ex.setdefault(k, v)

    def fill(items, key):
        out = []
        for it in items or []:
            it = dict(it) if isinstance(it, dict) else {key: str(it)}
            if "example" not in it and it.get(key) in ex:
                it["example"] = ex[it[key]]
            out.append(it)
        return out

    return {**ui, "inputs": fill(ui.get("inputs"), "field"),
            "outputs": fill(ui.get("outputs"), "name")}


def merge_screens(slices, uis):
    """Storyboard rule: a screen is one frame in time. A state_view whose UI is
    the same screen as the very next state_change's is that screen showing the
    read model, with the button for the next command: draw it once, in the
    state_change's column. Returns {state_change index: merged ui} and the set
    of state_view indexes whose UI was absorbed."""
    merged, absorbed = {}, set()
    for i in range(len(slices) - 1):
        v, c = slices[i], slices[i + 1]
        vui, cui = uis[i] or {}, uis[i + 1] or {}
        if (v.get("pattern") == "state_view" and c.get("pattern") == "state_change"
                and vui.get("screen") and vui.get("screen") == cui.get("screen")):
            outs = {o.get("name"): o for o in (vui.get("outputs") or [])}
            for o in cui.get("outputs") or []:
                outs.setdefault(o.get("name"), o)
            merged[i + 1] = {**cui, "outputs": list(outs.values())}
            absorbed.add(i)
    return merged, absorbed


# --------------------------------------------------------------------------- #
# Sticky contents (shared by measuring and drawing)
# --------------------------------------------------------------------------- #
def cmd_parts(s, fields):
    cmd = s.get("command") or {}
    return (cmd.get("name", s.get("slice", "Command")),
            field_lines(cmd.get("payload")) if fields else [], [])


def view_parts(s, cleared, fields):
    view = s.get("view") or {}
    return (view.get("name", s.get("slice", "View")),
            field_lines(view.get("fields"), view.get("tags") or ()) if fields else [],
            [_clip(line) for line in cleared])


def event_parts(ev, fields):
    lines = []
    if fields and isinstance(ev, dict):
        lines = field_lines(ev.get("fields"), ev.get("tags") or ())
    return _ename(ev), lines, []


def spec_rows(sc):
    """(row, kind, name, lines) for one scenario; kind None = muted text."""
    rows = []
    for g in sc.get("given") or []:
        if not isinstance(g, dict):
            continue
        if g.get("event"):
            rows.append(("GIVEN", "event", g["event"], data_lines(g.get("data"))))
        elif g.get("view"):
            rows.append(("GIVEN", "view", g["view"], data_lines(g.get("data"))))
        elif g.get("external"):
            ext = g["external"] or {}
            rows.append(("GIVEN", "external", ext.get("event", "External"),
                         data_lines(ext.get("data"))))
    if not rows:
        rows.append(("GIVEN", None, "(nothing happened yet)", []))
    when = sc.get("when") or {}
    if when.get("command"):
        rows.append(("WHEN", "command", when["command"], data_lines(when.get("payload"))))
    then = sc.get("then") or {}
    if then.get("events"):
        for e in then["events"]:
            rows.append(("THEN", "event", e.get("event", "Event"), data_lines(e.get("data"))))
    elif then.get("event"):
        rows.append(("THEN", "event", then["event"], data_lines(then.get("data"))))
    elif then.get("exception"):
        rows.append(("THEN", "error", then["exception"],
                     ["no event emitted"] if then.get("emits") == "none" else []))
    elif then.get("view"):
        rows.append(("THEN", "view", then["view"], data_lines(then.get("data"))))
    elif then.get("command"):
        rows.append(("THEN", "command", then["command"], data_lines(then.get("payload"))))
    if then.get("message"):
        rows.append(("THEN", "note", f"“{then['message']}”", []))
    return rows


SPEC_T, SPEC_L, ROW_LABEL_H, GAP = 13, 11, 18, 6


def _spec_item_h(kind, name, lines):
    return 16 if kind is None else sticky_h(name, lines, (), SPEC_T, SPEC_L)


def scenario_h(sc):
    head = _wrap(sc.get("name") or "Scenario", 34)
    h, last = 10 + 17 * len(head) + 6, None
    for row, kind, name, lines in spec_rows(sc):
        if row != last:
            h, last = h + ROW_LABEL_H, row
        h += _spec_item_h(kind, name, lines) + GAP
    return h + 6


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def render(slices, board, fields=True, specs=True):
    uis = [ui_with_examples(s) for s in slices]
    merged, absorbed = merge_screens(slices, uis)
    plans, ncols, hints = plan(slices, absorbed)
    top_ui = {i: merged.get(i, uis[i]) for i in range(len(slices))
              if uis[i] and i not in absorbed}
    producer = {}
    for s in slices:
        for ev in _events(s):
            producer.setdefault(_ename(ev), s)

    # ---- measure lanes
    actors = list(dict.fromkeys(actor_lane(s) for s in slices if has_top(s)))
    streams = list(dict.fromkeys(stream(s) for s in slices if _events(s))) or [""]
    systems = list(dict.fromkeys(x for x in map(ext_system, slices) if x))
    top_h = {a: AGENT_H for a in actors}
    for i, ui in top_ui.items():
        a = actor_lane(slices[i])
        top_h[a] = max(top_h[a], wire_h(ui))
    cmd_h, ev_h = BOX_H, {st: DUP_H for st in streams}
    for s, p in zip(slices, plans):
        if s.get("command"):
            cmd_h = max(cmd_h, sticky_h(*cmd_parts(s, fields)))
        if s.get("view") and s.get("pattern") in ("state_view", "translation"):
            cmd_h = max(cmd_h, sticky_h(*view_parts(s, p["cleared"], fields)))
        for ev in _events(s):
            ev_h[stream(s)] = max(ev_h[stream(s)], sticky_h(*event_parts(ev, fields)))
    lanes, y = [], TOP_Y
    for a in actors:
        lanes.append((a, a, y))
        y += top_h[a] + 2 * LANE_PAD
    lanes.append(("cmd", "COMMANDS / READ MODELS", y))
    y += cmd_h + 2 * LANE_PAD
    for st in streams:
        lanes.append((("event", st), f"EVENTS · {st}" if st else "EVENTS", y))
        y += ev_h[st] + 2 * LANE_PAD
    for x in systems:
        lanes.append((("ext", x), f"{x}  (external)", y))
        y += EXT_H + 2 * LANE_PAD
    show_specs = specs and any(s.get("scenarios") for s in slices)
    if show_specs:
        lanes.append(("spec", "SPECIFICATIONS\nGiven / When / Then", y))
    board.lane_y = {key: ly for key, _, ly in lanes}
    board.fields = fields

    width = START_X + max(ncols, 1) * COL_W + 40
    bands = []
    for n, (key, title, ly) in enumerate(lanes):
        kind = key if key in ("cmd", "spec") else (
            key[0] if isinstance(key, tuple) else "actor")
        top = ly - 14 + LANE_GAP / 2
        nxt = lanes[n + 1][2] if n + 1 < len(lanes) else y   # spec lane: resized below
        bottom = nxt - 14 - LANE_GAP / 2
        bands.append(board.band(LABEL_X, top, width - LABEL_X, bottom - top, LANE_BG[kind]))
        board.text(LABEL_X + 10, ly + 8, 220, 40, title,
                   color=MUTED, size=14, align="left", valign="top", family=2)
    board.text(LABEL_X + 10, TOP_Y - 54, 600, 30,
               f"Event Model  —  {len(slices)} slice(s)",
               color="#1e1e1e", size=22, align="left", family=2)

    # ---- the timeline
    events = {}            # event name -> [(col, box)], originals + duplicates
    views = {}             # view name  -> box (drawn once, in its own slice)
    links = []             # (consumer box, consumer col, refs)
    feeds = None           # (view box, slice id) whose screen the next state_change draws
    dups = 0
    for i, (s, p) in enumerate(zip(slices, plans)):
        col, pat = p["col"], s.get("pattern")
        board.sid = s.get("id")
        top = (board.lane_y[actor_lane(s)] + LANE_PAD) if has_top(s) else None
        copies = []
        for k, (name, kind) in enumerate(p["copies"]):
            if kind == "dup":
                src = producer[name]
                cbox = board.sticky(box_x(col + k),
                                    board.lane_y[("event", stream(src))] + LANE_PAD,
                                    "dup", name, extra=["(duplicate)"], h=DUP_H)
                board.tag(cbox, src.get("id"))     # a copy carries its producer's id
                events.setdefault(name, []).append((col + k, cbox))
                dups += 1
            else:
                cbox = board.labeled(box_x(col + k) + (BOX_W - 200) // 2,
                                     board.lane_y[("event", streams[0])] + LANE_PAD,
                                     200, DUP_H, "ghost", name, size=13)
            copies.append(cbox)
        last = col + p["span"] - 1
        if pat == "state_change":
            consumer = _state_change(board, col, s, top, events,
                                     top_ui.get(i), feeds if i in merged else None)
        elif pat == "state_view":
            consumer = _state_view(board, last, s, top, views, top_ui.get(i),
                                   p["cleared"])
            feeds = (consumer, s.get("id")) if i in absorbed else None
        elif pat == "automation":
            consumer = _automation(board, last, s, top, events)
        elif pat == "translation":
            consumer = _translation(board, col, s, top, events, views)
        else:
            consumer = board.labeled(box_x(col), board.lane_y["cmd"] + LANE_PAD,
                                     BOX_W, BOX_H, "ghost",
                                     f"{s.get('slice', '?')}\n(pattern: {pat})")
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

    # ---- specifications under each slice's column
    if show_specs:
        spec_bottom = board.lane_y["spec"] + LANE_PAD + BOX_H
        for s, p in zip(slices, plans):
            board.sid = s.get("id")
            y = board.lane_y["spec"] + LANE_PAD
            for sc in s.get("scenarios") or []:
                y = _scenario(board, p["anchor"], y, sc) + 24
                spec_bottom = max(spec_bottom, y)
        bands[-1]["height"] = spec_bottom - bands[-1]["y"]
    return {"columns": ncols, "duplicates": dups, "story_hints": hints,
            "streams": [st for st in streams if st]}


def _scenario(board, col, y, sc):
    """One Given / When / Then block in a dashed frame. Returns its bottom."""
    x, w = box_x(col), BOX_W
    h = scenario_h(sc)
    frame = board.rect(x - 10, y, w + 20, h, "spec")
    start = len(board.els)
    head = _wrap(sc.get("name") or "Scenario", 34)
    board.text(x, y + 10, w, 17 * len(head), "\n".join(head), size=13,
               align="left", valign="top", family=2)
    cur, last = y + 10 + 17 * len(head) + 6, None
    for row, kind, name, lines in spec_rows(sc):
        if row != last:
            board.text(x, cur, w, 14, row, color=MUTED, size=11, align="left",
                       valign="top", family=2)
            cur, last = cur + ROW_LABEL_H, row
        if kind is None:
            board.text(x, cur, w, 14, name, color=MUTED, size=11, align="left",
                       valign="top", family=2)
        else:
            board.tag(board.sticky(x, cur, kind, name, lines,
                                   title_size=SPEC_T, line_size=SPEC_L))
        cur += _spec_item_h(kind, name, lines) + GAP
    board.attach(frame, *[e["id"] for e in board.els[start:]])
    return y + h


def wire_h(ui):
    """Height of a UI mockup, so its actor lane can be sized to fit."""
    h = 12 + 30                         # padding + title
    h += len(ui.get("inputs") or []) * 48
    if (ui.get("trigger") or {}).get("label"):
        h += 48
    if ui.get("outputs"):
        h += 26 + len(ui["outputs"]) * 22 + 10
    return max(h, 90)


def _wireframe(board, col, ui, y):
    """Draw a UI mockup: inputs (with example values), button, outputs list."""
    x = box_x(col)
    pad = 12
    cur = y + pad
    inputs = ui.get("inputs") or []
    outputs = ui.get("outputs") or []
    trig = ui.get("trigger") or {}
    h = wire_h(ui)

    cid = board.rect(x, y, BOX_W, h, "wire")
    start = len(board.els)
    board.text(x + pad, cur, BOX_W - 2 * pad, 24, ui.get("screen", "Screen"),
               size=17, align="left", family=2)
    cur += 34
    inner = x + pad
    iw = BOX_W - 2 * pad
    for inp in inputs:
        board.text(inner, cur, iw, 16, inp.get("field", "?"), color=MUTED,
                   size=12, align="left", family=2)
        cur += 18
        board.rect(inner, cur, iw, 24, "field")
        has_ex = "example" in inp
        board.text(inner + 6, cur + 4, iw - 12, 16,
                   _clip(_fmt(inp["example"]) if has_ex else inp.get("type", ""), 32),
                   color="#343a40" if has_ex else "#adb5bd", size=12 if has_ex else 11,
                   align="left", family=2)
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
            line = o.get("name", "?")
            if "example" in o:
                line += f": {_fmt(o['example'])}"
            board.text(inner + 8, oy, iw - 16, 18, _clip(f"• {line}", 32),
                       color="#495057", size=12, align="left", family=2)
            oy += 22
    board.attach(cid, *[e["id"] for e in board.els[start:]])
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
    qual = (actor[actor.index("(") + 1:actor.rindex(")")]
            if "(" in actor and ")" in actor else None)
    label = s.get("processor") or qual or actor
    timer = (s.get("trigger") or {}).get("timer")
    if timer:
        label += f"\n⏱ {timer}"
    rid = board.rect(x, y, w, h, "auto")
    a = board.text(x + 14, y + h / 2 - 22, 44, 44, "⚙️", color="#5f3dc4", size=34,
                   align="left", valign="middle", family=2)
    b = board.text(x + 64, y + 14, w - 76, h - 28, label,
                   color="#1e1e1e", size=14, align="left", valign="middle", family=2)
    board.attach(rid, a, b)
    return board.tag((rid, x, y, w, h))


def _command(board, col, s):
    return board.tag(board.sticky(box_x(col), board.lane_y["cmd"] + LANE_PAD,
                                  "command", *cmd_parts(s, board.fields)))


def _event(board, col, s, ev, events):
    ebox = board.sticky(box_x(col), board.lane_y[("event", stream(s))] + LANE_PAD,
                        "event", *event_parts(ev, board.fields))
    events.setdefault(_ename(ev), []).append((col, ebox))
    return board.tag(ebox)


def _external(board, col, system, detail):
    system = system or "External"
    lines = [_clip(l) for l in _wrap(detail, CHARS)][:5] if detail else []
    return board.tag(board.sticky(box_x(col), board.lane_y[("ext", system)] + LANE_PAD,
                                  "external", system, lines, title_size=13))


def _state_change(board, col, s, top, events, ui, view=None):
    """`view`: (read model box, slice id) feeding this screen when it was merged
    with the preceding state_view's (see merge_screens); the screen's badge
    then names both slices, e.g. `12·13`."""
    cbox = _command(board, col, s)
    for i, ev in enumerate(_events(s)):
        board.arrow(cbox, _event(board, col + i, s, ev, events))
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


def _view(board, col, s, views, cleared=()):
    vbox = board.tag(board.sticky(box_x(col), board.lane_y["cmd"] + LANE_PAD,
                                  "view", *view_parts(s, cleared, board.fields)))
    name = (s.get("view") or {}).get("name")
    if name:
        views.setdefault(name, vbox)
    return vbox


def _state_view(board, col, s, top, views, ui, cleared):
    vbox = _view(board, col, s, views, cleared)
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
        ebox = _event(board, col, s, ev, events)
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
    vbox = _view(board, col, s, views)
    board.arrow(xbox, vbox)

    agent = _agent(board, col + 1, s, top)
    board.arrow(vbox, agent, dashed=True)
    cbox = _command(board, col + 1, s)
    board.arrow(agent, cbox)
    for ev in _events(s)[:1]:
        board.arrow(cbox, _event(board, col + 1, s, ev, events))
    return vbox


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Uncanvased slices -> Excalidraw board")
    ap.add_argument("paths", nargs="+", help="slice .yaml files and/or directories")
    ap.add_argument("-o", "--output", default="board.excalidraw")
    ap.add_argument("--compact", action="store_true",
                    help="names only: no field lists on stickies")
    ap.add_argument("--no-specs", action="store_true",
                    help="leave out the Given / When / Then area")
    args = ap.parse_args()

    slices = load_slices(args.paths)
    if not slices:
        sys.exit("No slices found.")
    ordered = order_slices(slices)
    board = Board()
    stats = render(ordered, board, fields=not args.compact, specs=not args.no_specs)
    board.dump(args.output)
    print(f"Wrote {args.output}  ({len(ordered)} slices, {stats['columns']} columns, "
          f"{stats['duplicates']} duplicated events, "
          f"{stats['story_hints']} story hints)")
    print("  event streams: " + (", ".join(stats["streams"]) or
                                 "none (set `context:` to split the events lane)"))
    for i, s in enumerate(ordered):
        sid = s.get("id")
        tag = f"#{sid} " if sid is not None else ""
        print(f"  {i + 1}. {tag}{s.get('slice', s['_file'])}  [{s.get('pattern', '?')}]")


if __name__ == "__main__":
    main()
