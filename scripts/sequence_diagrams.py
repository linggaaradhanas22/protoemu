#!/usr/bin/env python3
"""Generate the editable ARCH-B sequence book with the drawio-skill layout tool."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


BLOCKS = {
    "host": "Host", "program": "Program", "core": "Core", "timer": "Timer",
    "drive": "Drive", "capture": "Capture", "pads": "Pads",
}
EXTERNAL = {"rp": "RP2350", "peer": "Protocol peer", "clk": "Board clock"}
BOOK = {
    "chip": ("ARCH-B | Chip sequence", "rp pads host program core timer drive capture peer", [
        "01   Load and commit",
        ("rp", "pads", "BEGIN / DATA / COMMIT bits"),
        ("pads", "host", "Synchronized host inputs"),
        ("host", "program", "Tentative DATA words"),
        ("host", "program", "COMMIT: publish valid image", "ctrl"),
        ("host", "pads", "READY", "ctrl"),
        ("pads", "rp", "Registered READY", "ctrl"),
        ("host", "pads", "COMMIT reply bits"),
        ("pads", "rp", "COMMIT reply on MISO"),
        "02   Start and fetch",
        ("rp", "pads", "START request bits"),
        ("pads", "host", "Synchronized host inputs"),
        ("host", "program", "Enable fetch", "ctrl"),
        ("host", "core", "Start enabled contexts", "ctrl"),
        ("core", "program", "Fetch PC"),
        ("program", "core", "Registered instruction word"),
        "03   Timed I/O: example exchange. Issue, deadline checks and input observation can overlap.",
        ("timer", "core", "Pre-edge cycle"),
        ("core", "drive", "Deadline, mask, values and enables"),
        ("core", "capture", "Arm an input observation", "ctrl"),
        ("timer", "drive", "Pre-edge cycle"),
        ("drive", "pads", "Due masked update"),
        ("pads", "peer", "Registered pad change"),
        ("peer", "pads", "Peer response"),
        ("pads", "capture", "Synchronized pin sample"),
        ("timer", "capture", "Pre-edge cycle"),
        ("capture", "core", "Result and observation time on consume"),
        "04   Read back: the host can also drain payload while running",
        ("core", "host", "host_put: result word"),
        ("core", "host", "DONE after all enabled contexts halt and the drive queue drains", "ctrl"),
        ("rp", "pads", "READN request bits"),
        ("pads", "host", "Synchronized host inputs"),
        ("host", "pads", "READY", "ctrl"),
        ("pads", "rp", "Registered READY", "ctrl"),
        ("host", "pads", "Result reply bits"),
        ("pads", "rp", "Result words on MISO"),
    ]),
    "host": ("BLK-HOST | Loader and run control", "rp pads host program core", [
        "01   Load: each command is a separate SPI request with a separate reply frame",
        ("rp", "pads", "BEGIN / DATA / COMMIT frame bits"),
        ("pads", "host", "Synchronized CS, SCK and MOSI"),
        ("host", "program", "DATA: stream tentative words while halted"),
        "At CS close: check length and CRC. A bad load leaves the image invalid.",
        ("host", "program", "COMMIT: publish valid image; do not start", "ctrl"),
        ("host", "pads", "Assert READY for the pending reply", "ctrl"),
        ("pads", "rp", "Registered READY", "ctrl"),
        ("host", "pads", "Reply bits"),
        ("pads", "rp", "Reply on MISO"),
        "02   Run: START needs a committed image and HALTED state; preloaded ingress stays",
        ("rp", "pads", "START frame bits"),
        ("pads", "host", "Synchronized host inputs"),
        ("host", "core", "Entry PCs, enables and ownership masks"),
        ("host", "core", "Start enabled contexts together", "ctrl"),
        ("host", "core", "Ingress word on host_get"),
        ("core", "host", "Egress word on host_put"),
        "FIFOs use pre-edge counts: an enqueue into an empty FIFO cannot satisfy a same-edge read.",
        "03   Read results and stop",
        ("rp", "pads", "READN frame bits"),
        ("pads", "host", "Synchronized host inputs"),
        ("host", "pads", "Assert READY", "ctrl"),
        ("pads", "rp", "Registered READY", "ctrl"),
        ("host", "pads", "READN reply bits"),
        ("pads", "rp", "Up to four words on MISO"),
        "Pop READN words only on exact reply close. An interrupted reply keeps the same words.",
        ("rp", "pads", "STOP frame bits"),
        ("pads", "host", "Synchronized host inputs"),
        ("host", "pads", "Safe on the edge after validated STOP close", "ctrl"),
        "That edge also flushes timed work and FIFOs and invalidates the image. Acknowledge after it.",
    ]),
    "program": ("BLK-PROGRAM | Shared program store", "host program core", [
        "01   Load while halted (fetch disabled)",
        ("host", "program", "BEGIN: image invalid", "ctrl"),
        ("host", "program", "DATA: index and 24-bit word"),
        "Write in place. Fetch cannot see tentative words, even after bad DATA.",
        ("host", "program", "COMMIT: image valid; fetch still disabled", "ctrl"),
        "02   Registered read after START",
        ("host", "program", "Running: enable fetch", "ctrl"),
        ("core", "program", "Fetch PC on edge n"),
        "Check PC against the committed word count. No writes during run.",
        ("program", "core", "In range: registered word for execute on n+1"),
        ("program", "core", "Otherwise: registered bounds fault (no word)", "ctrl"),
        "Reset clears response validity and hides old words; it does not clear the array.",
    ]),
    "core": ("BLK-CORE | Shared issue core", "host program core timer drive", [
        "01   Fetch, then execute",
        ("host", "core", "Start enabled contexts at committed PCs", "ctrl"),
        "At a free issue boundary, choose a runnable context by round robin and retain its fetch tag.",
        ("core", "program", "Selected context's fetch PC"),
        ("program", "core", "Registered instruction word"),
        ("timer", "core", "Pre-edge cycle for execute"),
        "02   Example: one timed output instruction",
        ("core", "drive", "Absolute deadline and masked update"),
        ("drive", "core", "Ready, blocked or reject", "ctrl"),
        "Ready: retire once. Update the shift register only on admission.",
        "Blocked: save decoded request and operands. The other context can issue while this one waits.",
        ("core", "drive", "Retry same deadline and data without refetch"),
        ("drive", "core", "Ready, still blocked or reject", "ctrl"),
        "Capture and payload stalls use the same saved-operation approach.",
        "03   End paths (alternatives)",
        "HALT ends just that context; admitted pad updates still retire.",
        ("core", "host", "DONE when all enabled contexts halt and drive is empty", "ctrl"),
        "Fault F: do not retire the bad instruction. Accept no other issue on F. Due I/O still acts on F.",
        ("core", "host", "FAULTED and fault record; F+1 is the global safe edge", "ctrl"),
    ]),
    "timer": ("BLK-TIMER | Shared cycle timebase", "clk timer core drive capture", [
        "01   Reset sets the counter to zero",
        ("clk", "timer", "60 MHz rising edge", "ctrl"),
        "02   On each active edge: consumers read the same pre-edge C in parallel",
        ("timer", "core", "C for issue and deadline calculation"),
        ("timer", "drive", "C for admission and due comparison"),
        ("timer", "capture", "C for sample comparison and observation timestamp"),
        "On that edge the counter also registers (C + 1) mod 2^24. START, HALT and fault do not rewind it.",
        "03   Consumers use C in two ways",
        "New drive or timed sample: accept only a positive delta less than 2^23. Accepted work fires on equality.",
        "Guard: classify once. A future target waits for equality; zero or a past-half delta opens the guard.",
        "The consumer keeps the guard open. The timer sends only a number, not a trigger or a clock.",
    ]),
    "drive": ("BLK-DRIVE | Timed output queue", "core timer drive pads host", [
        "01   Admit or block a request",
        ("core", "drive", "Context, deadline, mask, values and enables"),
        ("timer", "drive", "Pre-edge cycle"),
        "Check mask, ownership, same-deadline overlap and the future half-range before reporting full.",
        ("drive", "core", "Ready: enqueue in one slot; reject: fault; neither: retry", "ctrl"),
        "02   Fire on the deadline edge, regardless of core activity",
        ("timer", "drive", "Pre-edge cycle equals a stored deadline"),
        "Merge disjoint due masks and retire every due slot whole. Reuse a retiring slot for a future event.",
        ("drive", "pads", "Merged mask, values and enables on that edge"),
        "03   Fault and flush (alternative to continuing)",
        "Due updates still retire on fault edge F.",
        ("host", "drive", "Flush on F+1 clears remaining entries and suppresses due updates", "ctrl"),
    ]),
    "capture": ("BLK-CAPTURE | Context-owned input capture", "pads timer capture core", [
        "01   Arm the issuing context's empty slot",
        ("core", "capture", "Owner, pin, mode and any target or timeout"),
        ("capture", "core", "Accept empty slot; reject occupied slot", "ctrl"),
        "02   Observe before the decision edge. An edge arm ignores the arm edge itself.",
        ("pads", "capture", "Second-stage pin_sample"),
        ("timer", "capture", "Same pre-edge cycle"),
        "A sample uses deadline equality. A guarded level wait observes once its guard opens.",
        "A timed guard sets expiry at target + Rt × 64. A matching level wins on the expiry edge.",
        "03   Hold result until the owner consumes it",
        ("capture", "core", "Result-ready from the next cycle; no same-edge bypass", "ctrl"),
        ("core", "capture", "Consume owning slot", "ctrl"),
        ("capture", "core", "Sampled bit and original observation time"),
        ("capture", "core", "Or expired status for a timed wait", "ctrl"),
        "Consume frees the slot. Flush clears both slots and suppresses observations on that edge.",
    ]),
    "pads": ("BLK-PADS | Tiny Tapeout pad adapter", "rp host pads capture drive peer", [
        "01   Sample external inputs continuously",
        ("rp", "pads", "Raw host CS, SCK and MOSI"),
        ("peer", "pads", "Raw protocol pin levels"),
        "Pass both groups through two flop stages. Forward the second stage, not the asynchronous value.",
        ("pads", "host", "Synchronized host inputs"),
        ("pads", "capture", "Synchronized pin_sample"),
        "02   Register outputs",
        ("drive", "pads", "Due update: mask, values and output enables"),
        "Keep unmasked pads unchanged. On open drain, high or disabled means release; never drive high.",
        ("pads", "peer", "Registered protocol pad state"),
        ("host", "pads", "MISO bit"),
        ("host", "pads", "READY status", "ctrl"),
        ("pads", "rp", "Registered MISO bit"),
        ("pads", "rp", "Registered READY", "ctrl"),
        "03   Resolve coincident controls on the output edge",
        ("host", "pads", "Safe on STOP or fault cleanup", "ctrl"),
        "Priority: reset, deselect, safe, then due update. DONE holds the last pad state.",
    ]),
}

FONT = "fontFamily=Helvetica;fontColor=#202124;"
TEXT = f"text;html=1;align=left;verticalAlign=middle;{FONT}"


def add_text(root, cid, value, x, y, width, height, style, parent="1"):
    cell = ET.SubElement(root, "mxCell", id=cid, value=value, style=style, vertex="1", parent=parent)
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(width), height=str(height),
                  attrib={"as": "geometry"})
    return cell


def link(root, cell, page):
    cid = cell.attrib.pop("id")
    value = cell.attrib.pop("value")
    index = list(root).index(cell)
    root.remove(cell)
    wrapper = ET.Element("UserObject", id=cid, label=value, link=f"data:page/id,seq-{page}")
    wrapper.append(cell)
    root.insert(index, wrapper)


def page(key, title, lanes, rows, tool):
    participants = [{"id": lane, "label": f"BLK-{lane.upper()}" if lane in BLOCKS else EXTERNAL[lane]}
                    for lane in lanes.split()]
    messages = []
    for row in rows:
        if isinstance(row, str):
            messages.append({"note": row, "over": participants[0]["id"]})
        else:
            src, dst, label, *kind = row
            messages.append({"from": src, "to": dst, "label": label, "activate": False,
                             "async": kind == ["ctrl"]})
    spec = json.dumps({"title": title, "participants": participants, "messages": messages})
    # seqlayout accepts a filename or the process's standard input on WSL.
    output = subprocess.run([sys.executable, str(tool), "/dev/stdin"], input=spec, text=True,
                            encoding="utf-8", capture_output=True, check=True).stdout
    diagram = ET.fromstring(output).find("diagram")
    diagram.set("id", f"seq-{key}")
    model = diagram.find("mxGraphModel")
    root = model.find("root")
    cells = {cell.get("id"): cell for cell in root}
    geom = cells[participants[-1]["id"]].find("mxGeometry")
    width = int(geom.get("x")) + 100
    end = int(geom.get("y")) + int(geom.get("height"))
    model.set("pageWidth", str(width + 40))
    model.set("pageHeight", str(end + 60))
    for p in participants:
        pid = p["id"]
        cell = cells[pid]
        internal = pid in BLOCKS
        fill, stroke = ("#dae8fc", "#6c8ebf") if internal else ("#ffffff", "#202124")
        cell.set("style", cell.get("style") + f"fillColor={fill};strokeColor={stroke};"
                 f"fontStyle=1;fontSize=12;{FONT}")
        # Use a header-only link, so clicking a lifeline in the body does not change pages.
        if internal and pid != key:
            header = add_text(root, f"open-{pid}", p["label"], 2, 2, 96, 36,
                              f"rounded=0;html=1;align=center;fillColor={fill};strokeColor=none;"
                              "fontFamily=Helvetica;fontColor=#193c66;fontStyle=5;fontSize=12;", pid)
            link(root, header, pid)
    root.insert(2, ET.Element("mxCell", id="notes", value="Phase captions and notes", parent="0"))
    for index, row in enumerate(rows):
        if isinstance(row, str):
            cell = cells[f"note{index}"]
            phase = row[:2].isdigit()
            fill = "#e7eff9" if phase else "#f5f5f5"
            cell.set("parent", "notes")
            cell.set("style", f"rounded=0;html=1;align=left;spacingLeft=10;{FONT}"
                     f"fillColor={fill};strokeColor=none;fontSize=12;" + ("fontStyle=1;" if phase else ""))
            cell.find("mxGeometry").attrib.update(x="40", width=str(width - 40), height="30")
        else:
            cell = cells[f"m{index}"]
            cell.set("style", cell.get("style") + f"labelBackgroundColor=#ffffff;{FONT}"
                     "strokeColor=#293548;fontSize=12;spacingBottom=2;")
    add_text(root, "title", title, 40, 4, min(550, width - 195), 30, TEXT + "fontSize=18;fontStyle=1;")
    if key != "chip":
        back = add_text(root, "back", "Back to chip sequence", width - 145, 5, 145, 25,
                        TEXT + "fontSize=12;fontStyle=4;")
        link(root, back, "chip")
    add_text(root, "key", "Read top to bottom. Solid: data. Dashed: control / status. Blue: ASIC blocks at 60 MHz.",
             40, end + 8, width - 40, 26, TEXT + "fontSize=12;")
    return diagram


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout-tool", type=Path, required=True, help="drawio-skill/scripts/seqlayout.py")
    parser.add_argument("--out", type=Path,
                        default=Path("design/05_microarch/diagrams/arch-b-sequences_v1.drawio"))
    args = parser.parse_args()
    book = ET.Element("mxfile", host="drawio")
    for key, (title, lanes, rows) in BOOK.items():
        book.append(page(key, title, lanes, rows, args.layout_tool))
    ET.indent(book, space="  ")
    ET.ElementTree(book).write(args.out, encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()
