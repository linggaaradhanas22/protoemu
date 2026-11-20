#!/usr/bin/env python3
"""Generate the G4 block diagrams (draw.io) in the ARCH-B house style.

One spec per block: internal sub-blocks inside a plain enclosure, neighbouring
blocks outside it. Colors follow the drawio-skill `hardware-architecture`
preset: blue = clocked logic (clk 60 MHz), grey = combinational logic,
white = neighbouring block. Line style follows design/05_microarch/diagrams/README.md:
solid = data, dashed = control / status.

Usage: python3 scripts/block_diagrams.py [--out design/05_microarch/diagrams]
Export SVG with draw.io:  draw.io -x -f svg --embed-svg-fonts false -o X.svg X.drawio
"""

import argparse
from html import escape
from pathlib import Path

FONT = "fontFamily=Helvetica;fontColor=#202124;"
FILL = {"clocked": ("#dae8fc", "#6c8ebf"), "comb": ("#f5f5f5", "#666666"), "ext": ("#ffffff", "#000000")}
EDGE = ("edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
        "labelBackgroundColor=#ffffff;fontFamily=Helvetica;fontSize=11;")


def node(cid, label, x, y, w, h, kind):
    fill, stroke = FILL[kind]
    style = f"rounded=1;html=1;whiteSpace=wrap;fillColor={fill};strokeColor={stroke};{FONT}fontSize=13;"
    return (f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def text(cid, label, x, y, w, h, size=12, bold=False):
    style = f"text;html=1;align=left;verticalAlign=top;{FONT}fontSize={size};" + ("fontStyle=1;" if bold else "")
    return (f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')


def edge(cid, label, src, dst, kind, exit, entry, both=False, points=(), offset=None, at=None):
    style = EDGE + ("dashed=1;dashPattern=6 4;" if kind == "ctrl" else "")
    style += ("startArrow=classic;" if both else "startArrow=none;") + "endArrow=classic;"
    style += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in points)
    geo = f'<mxGeometry{f" x={chr(34)}{at}{chr(34)}" if at is not None else ""} relative="1" as="geometry">'
    if pts:
        geo += f'<Array as="points">{pts}</Array>'
    if offset:
        geo += f'<mxPoint x="{offset[0]}" y="{offset[1]}" as="offset"/>'
    geo += "</mxGeometry>"
    return (f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
            f'source="{src}" target="{dst}">{geo}</mxCell>')


def page(spec):
    ex, ey, ew, eh = spec["enclosure"]
    cells = [text("title", spec["title"], 20, 20, 900, 30, size=22, bold=True),
             text("enclosure-label", spec["label"], ex, ey - 26, 400, 22, size=13, bold=True),
             '<mxCell id="enclosure" style="rounded=0;html=1;fillColor=none;strokeColor=#202124;" '
             f'vertex="1" parent="1"><mxGeometry x="{ex}" y="{ey}" width="{ew}" height="{eh}" as="geometry"/></mxCell>']
    kinds = set()
    for n in spec["nodes"]:
        cells.append(node(*n))
        kinds.add(n[-1])
    for e in spec["edges"]:
        cid, label, src, dst, kind, exit, entry, *rest = e
        opts = rest[0] if rest else {}
        cells.append(edge(cid, label, src, dst, kind, exit, entry, **opts))
    route_y = [y for e in spec["edges"] if len(e) > 7 for _, y in e[7].get("points", ())]
    legend_y = max(ey + eh, *(n[3] + n[5] for n in spec["nodes"]), *route_y) + 30
    colors = [("clocked", "Blue: clocked logic (clk 60 MHz)"), ("comb", "Grey: combinational logic"),
              ("ext", "White: neighbouring block")]
    block_text = "<b>Block color</b><br>" + "<br>".join(t for k, t in colors if k in kinds)
    cells.append(text("legend-block", block_text, 20, legend_y, 280, 70))
    cells.append(text("legend-line", "<b>Line style</b><br>Solid: data<br>Dashed: control / status", 320, legend_y, 240, 70))
    if spec.get("note"):
        cells.append(text("note", spec["note"], 580, legend_y, 560, 70))
    body = "\n        ".join(cells)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="drawio">
  <diagram id="{spec['id']}" name="{escape(spec['label'])}">
    <mxGraphModel grid="1" gridSize="10" page="1" pageWidth="1400" pageHeight="800">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        {body}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
'''


R, L, T, B = (1, 0.5), (0, 0.5), (0.5, 0), (0.5, 1)

SPECS = {}

SPECS["blk-timer"] = {
    "id": "blk-timer", "title": "BLK-TIMER — Cycle timebase", "label": "Cycle timebase",
    "enclosure": (40, 100, 440, 270),
    "nodes": [("inc", "+1", 70, 200, 80, 60, "comb"),
              ("counter", "24-bit<br>cycle register", 240, 110, 180, 240, "clocked"),
              ("core", "BLK-CORE", 660, 110, 170, 50, "ext"),
              ("drive", "BLK-DRIVE", 660, 205, 170, 50, "ext"),
              ("capture", "BLK-CAPTURE", 660, 300, 170, 50, "ext")],
    "edges": [("e-cur", "Cycle", "counter", "inc", "data", (0, 0.4583), (1, 0.3333)),
              ("e-next", "Next", "inc", "counter", "data", (1, 0.6667), (0, 0.5417)),
              ("e-core", "Issue time, deadlines", "counter", "core", "data", (1, 0.1042), L, {"at": 0.35}),
              ("e-drive", "Deadline compare", "counter", "drive", "data", (1, 0.5), L, {"at": 0.35}),
              ("e-cap", "Observation time", "counter", "capture", "data", (1, 0.8958), L, {"at": 0.35})],
    "note": "Never stops or rewinds while powered. Reset sets it to zero.",
}

SPECS["blk-program"] = {
    "id": "blk-program", "title": "BLK-PROGRAM — Shared program store", "label": "Shared program store",
    "enclosure": (240, 100, 760, 370),
    "nodes": [("wport", "Write port<br>index decode", 280, 150, 170, 60, "comb"),
              ("array", "128 × 24-bit<br>flop array", 560, 150, 170, 60, "clocked"),
              ("mux", "128:1 read mux", 560, 270, 170, 50, "comb"),
              ("check", "Fetch check<br>running, PC &lt; count", 800, 260, 170, 70, "comb"),
              ("resp", "Fetch response<br>register", 560, 370, 170, 60, "clocked"),
              ("host", "BLK-HOST<br>loader", 20, 150, 150, 60, "ext"),
              ("core", "BLK-CORE", 1180, 260, 150, 70, "ext")],
    "edges": [("e-words", "Program words", "host", "wport", "data", R, L),
              ("e-image", "Image state", "host", "check", "ctrl", T, T, {"points": [(95, 120), (885, 120)]}),
              ("e-write", "Index / word", "wport", "array", "data", R, L),
              ("e-read", "All words", "array", "mux", "data", B, T),
              ("e-req", "Fetch request (PC)", "core", "check", "ctrl", L, R, {"at": -0.4}),
              ("e-sel", "PC select", "check", "mux", "ctrl", L, R),
              ("e-inst", "Instruction word", "mux", "resp", "data", B, T),
              ("e-valid", "Valid / fault", "check", "resp", "ctrl", B, R, {"points": [(885, 400)]}),
              ("e-out", "Instruction word, valid / fault", "resp", "core", "data", B, B,
               {"points": [(645, 450), (1255, 450)], "at": -0.3})],
    "note": "Words stay hidden until COMMIT; fetch runs only after START.",
}

SPECS["blk-drive"] = {
    "id": "blk-drive", "title": "BLK-DRIVE — Timed output queue", "label": "Timed output queue",
    "enclosure": (330, 100, 790, 360),
    "nodes": [("adm", "Admission check<br>owner, empty mask,<br>collision, half range", 360, 140, 190, 80, "comb"),
              ("slots", "Four deadline slots<br>deadline, mask,<br>value, OE", 640, 140, 190, 80, "clocked"),
              ("due", "Due compare ×4<br>cycle == deadline", 640, 360, 190, 60, "comb"),
              ("merge", "Merge due entries<br>disjoint masks", 920, 360, 170, 60, "comb"),
              ("core", "BLK-CORE", 20, 140, 140, 80, "ext"),
              ("timer", "BLK-TIMER", 20, 270, 140, 60, "ext"),
              ("host", "BLK-HOST<br>run control", 1240, 130, 160, 60, "ext"),
              ("pads", "BLK-PADS", 1240, 360, 160, 60, "ext")],
    "edges": [("e-req-data", "Deadline / mask / values", "core", "adm", "data", (1, 0.3), (0, 0.3)),
              ("e-req-ctl", "Request / ready / reject", "core", "adm", "ctrl", (1, 0.7), (0, 0.7), {"both": True}),
              ("e-accept", "Accepted entry", "adm", "slots", "data", R, L),
              ("e-cyc-adm", "", "timer", "adm", "data", (1, 0.3), B, {"points": [(455, 288)]}),
              ("e-cyc-due", "Cycle count", "timer", "due", "data", (1, 0.7), L, {"points": [(600, 312), (600, 390)]}),
              ("e-dl", "Deadlines", "slots", "due", "data", B, T),
              ("e-due", "Due slots", "due", "merge", "ctrl", R, L),
              ("e-vals", "Mask / value / OE", "slots", "merge", "data", (1, 0.75), T, {"points": [(1005, 200)]}),
              ("e-pad", "Pad values", "merge", "pads", "data", (1, 0.3), (0, 0.3), {"at": 0.15}),
              ("e-pad-ctl", "Mask / output enable", "merge", "pads", "ctrl", (1, 0.7), (0, 0.7), {"at": 0.15}),
              ("e-flush", "Flush", "host", "slots", "ctrl", L, (1, 0.25)),
              ("e-own", "Write ownership", "host", "adm", "ctrl", T, T, {"points": [(1320, 115), (455, 115)]})],
    "note": "Each entry retires whole on its deadline edge. Flush on the safe edge wins (CHG-008).",
}

SPECS["blk-capture"] = {
    "id": "blk-capture", "title": "BLK-CAPTURE — Context-owned input capture", "label": "Input capture",
    "enclosure": (270, 100, 810, 410),
    "nodes": [("sel", "Pin select<br>and previous sample", 300, 140, 180, 60, "comb"),
              ("match", "Match logic<br>level, edge, timed sample", 640, 140, 200, 60, "comb"),
              ("cmp", "Deadline compare<br>cycle == deadline", 300, 290, 180, 80, "comb"),
              ("slots", "Capture slot ×2, one per context<br>state, guard-open, deadline,<br>timeout, result bit and time",
               640, 280, 240, 100, "clocked"),
              ("reload", "Timeout reload<br>target + Rt × 64", 300, 410, 180, 50, "comb"),
              ("pads", "BLK-PADS", 20, 140, 130, 60, "ext"),
              ("timer", "BLK-TIMER", 20, 300, 130, 60, "ext"),
              ("core", "BLK-CORE", 1160, 270, 160, 120, "ext"),
              ("host", "BLK-HOST<br>run control", 1160, 430, 160, 60, "ext")],
    "edges": [("e-pins", "Pin samples", "pads", "sel", "data", R, L),
              ("e-sel", "Selected pin, previous", "sel", "match", "data", R, L),
              ("e-hit", "Match", "match", "slots", "ctrl", B, (0.4167, 0)),
              ("e-cyc", "Cycle count", "timer", "cmp", "data", R, (0, 0.375)),
              ("e-stamp", "Observation time", "timer", "slots", "data", B, (0.75, 1),
               {"points": [(85, 490), (820, 490)]}),
              ("e-dl", "Deadline", "slots", "cmp", "data", (0, 0.3), (1, 0.25)),
              ("e-due", "Guard open / due / expired", "cmp", "slots", "ctrl", (1, 0.75), (0, 0.7)),
              ("e-tgt", "Target, Rt", "slots", "reload", "data", (0.1, 1), R, {"points": [(664, 435)]}),
              ("e-exp", "Expiry", "reload", "slots", "data", (1, 0.8), (0.35, 1), {"points": [(724, 450)]}),
              ("e-arm", "Arm: pin, mode, target, Rt", "core", "slots", "data", (0, 0.25), (1, 0.2), {"at": 0.3}),
              ("e-ctl", "Arm / consume / ready", "core", "slots", "ctrl", L, R, {"both": True, "at": 0.3}),
              ("e-res", "Captured bit / time", "slots", "core", "data", (1, 0.8), (0, 0.75), {"at": -0.3}),
              ("e-flush", "Flush", "host", "slots", "ctrl", L, (0.9, 1), {"points": [(856, 460)]})],
    "note": "Guard and timeout follow CHG-007 and CHG-013. Edge arms have no timeout.",
}

SPECS["blk-pads"] = {
    "id": "blk-pads", "title": "BLK-PADS — Tiny Tapeout pad adapter", "label": "Pad adapter",
    "enclosure": (300, 100, 550, 460),
    "nodes": [("psync", "Protocol input<br>synchronizers, 2 flops", 620, 140, 190, 60, "clocked"),
              ("outreg", "Pad output registers<br>value, OE", 330, 260, 190, 60, "clocked"),
              ("override", "Open-drain, safe<br>and reset override", 620, 260, 190, 60, "comb"),
              ("hsync", "Host input<br>synchronizers, 2 flops", 620, 380, 190, 60, "clocked"),
              ("hostregs", "Host pin registers<br>MISO, READY", 620, 480, 190, 60, "clocked"),
              ("capture", "BLK-CAPTURE", 20, 140, 140, 60, "ext"),
              ("drive", "BLK-DRIVE", 20, 260, 140, 60, "ext"),
              ("host", "BLK-HOST", 20, 380, 140, 160, "ext"),
              ("pins", "Tiny Tapeout pins<br>ui_in, uo_out,<br>uio_in, uio_out, uio_oe", 1010, 140, 180, 400, "ext")],
    "edges": [("e-pin", "uio_in", "pins", "psync", "data", (0, 0.075), R),
              ("e-samp", "Pin samples", "psync", "capture", "data", L, R),
              ("e-pad", "Pad values", "drive", "outreg", "data", (1, 0.3), (0, 0.3)),
              ("e-pad-ctl", "Mask / output enable", "drive", "outreg", "ctrl", (1, 0.7), (0, 0.7)),
              ("e-reg", "Value / OE", "outreg", "override", "data", R, L),
              ("e-out", "uio_out, uio_oe", "override", "pins", "data", R, (0, 0.375)),
              ("e-safe", "Safe / open-drain mode", "host", "override", "ctrl", T, B, {"points": [(90, 355), (715, 355)]}),
              ("e-hin", "ui_in[2:0]", "pins", "hsync", "data", (0, 0.675), R),
              ("e-hsamp", "CS, SCK, MOSI", "hsync", "host", "data", L, (1, 0.1875)),
              ("e-hout", "MISO, READY", "host", "hostregs", "data", (1, 0.8125), L),
              ("e-uo", "uo_out[4:3]", "hostregs", "pins", "data", R, (0, 0.925))],
    "note": "Reset, then deselect, then the safe edge, then due updates (CHG-008). In DONE, pads hold.",
}

SPECS["blk-host"] = {
    "id": "blk-host", "title": "BLK-HOST — Loader and run control", "label": "Loader and run control",
    "enclosure": (270, 100, 850, 310),
    "nodes": [("rx", "SPI frame receiver<br>shift register, CRC check", 300, 140, 190, 60, "clocked"),
              ("dec", "Command decoder<br>length and state checks", 590, 140, 190, 60, "comb"),
              ("img", "Image control<br>BEGIN, DATA, COMMIT", 880, 140, 190, 60, "clocked"),
              ("tx", "Reply transmitter<br>CRC generate, READY", 300, 270, 190, 60, "clocked"),
              ("fifo", "Payload FIFOs<br>2 ingress + 2 egress,<br>depth 8", 590, 270, 190, 80, "clocked"),
              ("run", "Run state<br>HALTED, RUNNING,<br>DONE, FAULTED;<br>fault record", 880, 260, 190, 90, "clocked"),
              ("pads", "BLK-PADS", 20, 140, 130, 190, "ext"),
              ("program", "BLK-PROGRAM", 1210, 140, 160, 60, "ext"),
              ("timedio", "BLK-DRIVE,<br>BLK-CAPTURE", 1210, 265, 160, 60, "ext"),
              ("core", "BLK-CORE", 680, 450, 320, 60, "ext")],
    "edges": [("e-in", "CS, SCK, MOSI", "pads", "rx", "data", (1, 0.1579), L),
              ("e-bytes", "Frame bytes", "rx", "dec", "data", R, L),
              ("e-img", "Image commands", "dec", "img", "ctrl", R, L),
              ("e-words", "Program words", "img", "program", "data", (1, 0.3), (0, 0.3), {"at": 0.35}),
              ("e-istate", "Image state", "img", "program", "ctrl", (1, 0.7), (0, 0.7), {"at": 0.35}),
              ("e-pay", "Payload words", "dec", "fifo", "data", B, T, {"both": True}),
              ("e-run", "START / STOP", "dec", "run", "ctrl", (1, 0.85), (0, 0.2222), {"points": [(830, 191), (830, 280)]}),
              ("e-reply", "Reply status / words", "dec", "tx", "data", (0, 0.85), R, {"points": [(540, 191), (540, 300)]}),
              ("e-out", "MISO, READY", "tx", "pads", "data", L, (1, 0.8421)),
              ("e-flush", "Flush", "run", "timedio", "ctrl", (1, 0.3889), L, {"at": 0.35}),
              ("e-corerun", "Run control / status", "run", "core", "ctrl", (0.45, 1), (0.8922, 0), {"both": True, "at": 0.4}),
              ("e-corepay", "Payload", "fifo", "core", "data", B, (0.0156, 0), {"both": True, "at": 0.4}),
              ("e-safe", "Safe", "run", "pads", "ctrl", (1, 0.8), B, {"points": [(1100, 332), (1100, 550), (85, 550)]})],
    "note": "SPI0 at 1 MHz (DEC-005); READN/WRITEN move up to 4 words (CHG-011).",
}

SPECS["blk-core"] = {
    "id": "blk-core", "title": "BLK-CORE — Shared issue core", "label": "Shared issue core",
    "enclosure": (270, 100, 750, 395),
    "nodes": [("dec", "Decode", 300, 150, 160, 60, "comb"),
              ("fetch", "Fetch slot<br>PC, context tag", 550, 150, 170, 60, "clocked"),
              ("sel", "Round-robin<br>context select", 800, 150, 170, 60, "comb"),
              ("alu", "ALU and register writes<br>port A, narrow port,<br>offset pair", 300, 270, 170, 80, "comb"),
              ("ctx", "Context state ×2<br>PC, R0–R7, return stack,<br>saved time, pending op,<br>guard bit", 530, 270, 210, 110, "clocked"),
              ("dl", "Deadline adder<br>half-range check", 810, 280, 170, 60, "comb"),
              ("fault", "Fault record<br>context, PC, cause", 300, 420, 170, 60, "clocked"),
              ("program", "BLK-PROGRAM", 20, 150, 130, 60, "ext"),
              ("host", "BLK-HOST", 20, 420, 130, 130, "ext"),
              ("timer", "BLK-TIMER", 1160, 150, 160, 60, "ext"),
              ("drive", "BLK-DRIVE", 1160, 270, 160, 80, "ext"),
              ("capture", "BLK-CAPTURE", 1160, 400, 160, 100, "ext")],
    "edges": [("e-inst", "Instruction word", "program", "dec", "data", R, L),
              ("e-fetchreq", "Fetch request", "fetch", "program", "ctrl", T, T, {"points": [(635, 120), (85, 120)]}),
              ("e-ctxsel", "Context", "sel", "fetch", "ctrl", L, R),
              ("e-decoded", "Decoded operation", "dec", "ctx", "data", B, (0.2, 0), {"points": [(380, 240), (572, 240)]}),
              ("e-runnable", "Runnable", "ctx", "sel", "ctrl", (0.8, 0), B, {"points": [(698, 240), (885, 240)]}),
              ("e-ops", "Operands / results", "ctx", "alu", "data", (0, 0.4), (1, 0.55), {"both": True}),
              ("e-time", "Saved time, offsets", "ctx", "dl", "data", (1, 0.3636), L),
              ("e-cyc", "Cycle count", "timer", "dl", "data", B, T, {"points": [(1240, 255), (895, 255)]}),
              ("e-drive", "Deadline / mask / values", "dl", "drive", "data", (1, 0.3), (0, 0.35), {"at": 0.3}),
              ("e-ready", "Request / ready / reject", "dl", "drive", "ctrl", (1, 0.7), (0, 0.65), {"both": True, "at": 0.3}),
              ("e-arm", "Arm: target, Rt", "dl", "capture", "data", (0.8, 1), (0, 0.2), {"points": [(946, 420)], "at": 0.5}),
              ("e-capctl", "Arm / consume / ready", "dl", "capture", "ctrl", B, (0, 0.4), {"both": True, "points": [(895, 440)], "at": 0.6}),
              ("e-cap", "Captured bit / time", "capture", "ctx", "data", (0, 0.6), (0.9, 1), {"points": [(719, 460)]}),
              ("e-faultc", "Fault cause", "ctx", "fault", "ctrl", (0, 0.9), T, {"points": [(385, 369)]}),
              ("e-status", "Run state,<br>fault record", "fault", "host", "ctrl", L, (1, 0.2308)),
              ("e-run", "Start config / run control", "host", "ctx", "ctrl", (1, 0.7308), (0.4286, 1), {"points": [(620, 515)]}),
              ("e-pay", "Payload", "host", "ctx", "data", (1, 0.8846), (0.6667, 1), {"both": True, "points": [(670, 535)]})],
    "note": "Structure fixed for G4; pipeline timing and final opcodes are still open.",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("design/05_microarch/diagrams"))
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, spec in SPECS.items():
        if args.only and name not in args.only:
            continue
        path = args.out / f"{name}_v1.drawio"
        path.write_text(page(spec), encoding="utf-8")
        print(path)


if __name__ == "__main__":
    main()
