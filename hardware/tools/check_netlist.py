#!/usr/bin/env python3
"""Check the generated schematic's connectivity, as computed by KiCad.

KiCad 7's command line has no ERC, so this does the checks that matter for a
labelled schematic:
  1. Every net KiCad found matches what gen_schematic.py intended
     (catches labels that missed a pin end, typos in net names, shorts).
  2. No net has only one pin (a label used once is almost always a typo).
  3. Every net with input pins has something driving it, and no net has two
     push-pull outputs fighting.

Usage:
  kicad-cli sch export netlist -o /tmp/gpsclock.net hardware/gpsclock/gpsclock.kicad_sch
  python3 hardware/tools/check_netlist.py /tmp/gpsclock.net
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_schematic  # noqa: E402

# Nets that legitimately have one pin: test points are the only exceptions.
SINGLE_OK = set()
# Parts allowed to have no footprint yet (part not chosen)
NO_FOOTPRINT_OK = {"Q1"}


def parse(path):
    text = open(path).read()
    nets = {}
    for m in re.finditer(r'\(net \(code "?\d+"?\) \(name "([^"]*)"\)(.*?)\)\s*(?=\(net |\)\s*\)\s*$)', text, re.S):
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)(?: \(pinfunction "[^"]*"\))?'
                           r'(?: \(pintype "([^"]+)"\))?', m.group(2))
        nets[m.group(1)] = [(r, p, t) for r, p, t in nodes]
    return nets


def main(path):
    sheet = gen_schematic.build()
    want = collections.defaultdict(set)
    intended_nc = set()
    for ref, conns in sheet.conns.items():
        for pin, net in conns.items():
            if net == "NC":
                intended_nc.add((ref, pin))
            else:
                want[net].add((ref, pin))

    nets = parse(path)
    errors = []
    got = {}
    for name, nodes in nets.items():
        members = {(r, p) for r, p, _ in nodes if not r.startswith("#")}
        if not members:
            continue
        clean = name.lstrip("/")
        got[clean] = members
        if name.startswith("unconnected-"):
            if not members <= intended_nc:
                errors.append(f"pin left unconnected: {sorted(members)}")
            continue
        if len(members) == 1 and clean not in SINGLE_OK:
            r, p = next(iter(members))
            if not r.startswith("TP"):
                errors.append(f"net {clean} has a single pin {r}.{p}")
        types = collections.Counter(t for r, p, t in nodes if not r.startswith("#"))
        drivers = types["output"] + types["power_out"] + types["bidirectional"] + types["tri_state"] \
            + types["passive"]
        if types["input"] + types["power_in"] and not drivers and not any(r.startswith("#FLG") for r, _, _ in nodes):
            errors.append(f"net {clean}: inputs but no driver ({dict(types)})")
        if types["output"] + types["power_out"] > 1:
            errors.append(f"net {clean}: several outputs drive it ({dict(types)})")

    for net, members in want.items():
        if net not in got:
            errors.append(f"intended net {net} missing in KiCad netlist (members {sorted(members)})")
        elif got[net] != members:
            errors.append(f"net {net}: KiCad has {sorted(got[net] - members)} extra, "
                          f"{sorted(members - got[net])} missing")
    for net in got:
        if net not in want and not net.startswith("unconnected-"):
            errors.append(f"unexpected net {net}: {sorted(got[net])}")

    comps = re.findall(r'\(comp \(ref "([^"]+)"\)(.*?)\(libsource', open(path).read(), re.S)
    for ref, body in comps:
        if "(footprint " not in body and ref not in NO_FOOTPRINT_OK:
            errors.append(f"{ref} has no footprint")

    print(f"{len(got)} nets, {len(sheet.refs)} parts checked")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/gpsclock.net"))
