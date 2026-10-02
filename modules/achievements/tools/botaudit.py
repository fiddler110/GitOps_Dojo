"""Static audit: can any bot command fire each catalog shell item? python3 -B botaudit.py <workshop>"""
import json, os, re, sys
R = os.getcwd()
sys.path[:0] = [f"{R}/modules/achievements/catalog", f"{R}/modules/achievements/service"]
import catalog as cat, matcher as mt
ws = sys.argv[1]
c, _ = cat.load(f"{R}/workshops/{ws}", f"{R}/modules/achievements/catalog/shared.json")
steps = open(f"{R}/workshops/{ws}/content/bots/steps.sh").read()
cmds = []
for m in re.finditer(r'run_cmd "((?:[^"\\]|\\.)*)"', steps):
    cmds.append(m.group(1).replace('\\"', '"').replace('\\$', '$').replace('\\\\', '\\'))
labs = f"{R}/workshops/{ws}/content/lab"
for m in re.finditer(r'vf_block (lab\d+\.md)((?: [^)"]+)+)\)', steps):
    t = open(f"{labs}/{m.group(1)}").read()
    fences = [b for l, b in re.findall(r"^```(\w+)\n(.*?)^```$", t, re.S | re.M) if l == "bash"]
    for tok in m.group(2).split():
        if ":" not in tok:
            cmds += [ln for ln in fences[int(tok) - 1].splitlines() if ln.strip() and not ln.startswith("#")]
items = [x for l in c["labs"] for x in l["milestones"] if cat.is_active(x)] + [f for f in c["funny"] if cat.is_active(f)]
for it in items:
    alts = (it.get("match") or {}).get("any") or [it.get("match") or {}]
    shell = [a for a in alts if a.get("source") == "shell"]
    if not shell:
        print(f"{it['id']:16} runtime ({','.join(sorted({a.get('source','?') for a in alts}))})")
        continue
    hit = None
    for a in shell:
        a2 = {k: v for k, v in a.items() if k not in ("out_regex", "requires", "requires_not", "count")}
        rx = re.compile(a2["regex"]) if "regex" in a2 else None
        want = a2.get("exit")
        codes = [0] if want in (None, 0) else ([1, 60] if want == "nonzero" else [want])
        for cmd in cmds:
            for code in codes:
                for inr in (True, False):
                    ev = mt.shell_event({"cmd": cmd, "exit": code, "in_repo": "1" if inr else "0", "out": ""})
                    if ev and mt._shell_match(a2, ev, rx):
                        hit = cmd; break
                if hit: break
            if hit: break
        if hit: break
    print(f"{it['id']:16} {'ok   ' + hit[:70] if hit else 'NO BOT COMMAND'}")
