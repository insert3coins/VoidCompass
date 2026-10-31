"""Overlay host benchmark (dev only, never released). See todo-overlay-backend.md.

Runs the real overlay host (visual hosting) against a test HtmlOverlayServer
with nine real overlay pages and the models from the text-fit tests. The test
windows appear in the top-left of the screen while it runs.

    python tools/overlay_bench.py baseline          boot screen lifting, show/hide spread, CPU per process
    python tools/overlay_bench.py baseline --cost   CPU of each overlay shown alone

Results go to temp/overlay_bench/<label>.json, host pass timings to
temp/overlay_bench/<label>_passes.json.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))
from tests.test_overlay_text_fit_5539 import OVERLAYS, THEME  # noqa: E402
from tests.test_navigation_state_visuals import hud_snapshot, hud_state  # noqa: E402
from voidcompass.overlays.html_overlay_server import HtmlOverlayServer  # noqa: E402

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi
ARGS = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
LABEL = ARGS[0] if ARGS else "baseline"
COST = "--cost" in sys.argv
OUT_DIR = REPO / "temp" / "overlay_bench"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DWMWA_CLOAKED = 14

# -- processes and their CPU --------------------------------------------------------------------


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD), ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


def tree(root_pid):
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    parents = {}
    if kernel32.Process32First(snap, ctypes.byref(entry)):
        while True:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            if not kernel32.Process32Next(snap, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snap)
    found, frontier = {root_pid}, [root_pid]
    while frontier:
        pid = frontier.pop()
        for child, parent in parents.items():
            if parent == pid and child not in found:
                found.add(child)
                frontier.append(child)
    return sorted(found)


def kinds(pids):
    """host / browser / gpu-process / renderer / ... for each pid."""
    script = ("Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -in @(" + ",".join(map(str, pids))
              + ") } | ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True).stdout
    found = {}
    for line in out.splitlines():
        pid, _, command = line.partition("\t")
        kind = "host" if "overlay_bench_host" in command else "browser"
        if "--type=" in command:
            kind = command.split("--type=")[1].split()[0]
            if kind == "utility" and "--utility-sub-type=" in command:
                kind = command.split("--utility-sub-type=")[1].split()[0].split(".")[-1]
        try:
            found[int(pid)] = kind
        except ValueError:
            pass
    return found


def cpu_seconds(pid):
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return 0.0
    times = [wt.FILETIME() for _ in range(4)]
    total = 0.0
    if kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
        for t in times[2:]:
            total += ((t.dwHighDateTime << 32) | t.dwLowDateTime) / 1e7
    kernel32.CloseHandle(handle)
    return total


def measure(pids, labels, seconds, during=None):
    """CPU % of one core per process kind over ``seconds``."""
    before, start = {pid: cpu_seconds(pid) for pid in pids}, time.perf_counter()
    while time.perf_counter() - start < seconds:
        if during:
            during()
        else:
            time.sleep(0.1)
    elapsed = time.perf_counter() - start
    split = {}
    for pid in pids:
        kind = labels.get(pid, "?")
        split[kind] = round(split.get(kind, 0) + 100 * (cpu_seconds(pid) - before[pid]) / elapsed, 1)
    return {"total": round(sum(split.values()), 1), "split": split}


# -- overlays -----------------------------------------------------------------------------------
SPECS = [("navigation", None, 500, 326)] + [(folder, (key, model), width, height)
                                            for folder, key, model, width, height, _max in OVERLAYS]
IDS = [spec[0] for spec in SPECS]


def snapshot(index, visible, tick=0):
    overlay_id, data, width, height = SPECS[index]
    window = {"x": 10 + (index % 5) * 300, "y": 30 + (index // 5) * 300, "width": min(width, 290),
              "height": min(height, 280), "visible": visible, "click_through": True}
    if data is None:
        body = hud_snapshot(hud_state("SUPERCRUISE" if tick % 2 else "FLIGHT"), reduced=False)
        body["context"] = {**body.get("context", {}), "secondary": f"TICK {tick}"}
    else:
        key, model = data
        body = {"theme": THEME, "effects": {"text_scale": 1}, key: model, "tick": tick}
    body["window"] = window
    return body


def on_screen(hwnd):
    """Mapped and not cloaked: what the user actually sees."""
    if not hwnd or not user32.IsWindowVisible(hwnd):
        return False
    cloaked = wt.DWORD(0)
    dwmapi.DwmGetWindowAttribute(wt.HWND(hwnd), DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return not cloaked.value


# Starts behind the boot screen, every overlay wanting to show.
server = HtmlOverlayServer(REPO / "web", presentation_held=True)
passes = {"count": 0}
original_manifest = server.window_manifest


def counted_manifest():
    passes["count"] += 1
    return original_manifest()


server.window_manifest = counted_manifest
for index, overlay_id in enumerate(IDS):
    server.register(overlay_id, overlay_id, f"Bench {overlay_id}")
    server.publish(overlay_id, snapshot(index, True))

timings = OUT_DIR / f"{LABEL}_passes.json"
log = open(OUT_DIR / f"{LABEL}_host.log", "w", encoding="utf-8")
host = subprocess.Popen([sys.executable, str(Path(__file__).with_name("overlay_bench_host.py")), str(timings), server.url],
                        env=dict(os.environ, PYTHONPATH=str(REPO / "src")), stdout=log, stderr=subprocess.STDOUT,
                        cwd=str(REPO))
results = {"label": LABEL, "overlays": len(IDS)}


def handles():
    return {overlay_id: int((server.host_status(overlay_id) or {}).get("handle") or 0) for overlay_id in IDS}


def watch(target, timeout=15.0):
    """When each window reached ``target`` on screen, from now."""
    start = time.perf_counter()
    found = handles()
    done = {}
    while time.perf_counter() - start < timeout and len(done) < len(IDS):
        now = time.perf_counter() - start
        for overlay_id, hwnd in found.items():
            if overlay_id not in done and on_screen(hwnd) == target:
                done[overlay_id] = now
        time.sleep(0.001)
    times = sorted(done.values())
    return {"all": len(done) == len(IDS), "first_ms": round(1000 * times[0]) if times else None,
            "last_ms": round(1000 * times[-1]) if times else None,
            "spread_ms": round(1000 * (times[-1] - times[0])) if times else None,
            "missing": [overlay_id for overlay_id in IDS if overlay_id not in done]}


def show_all(visible, tick=0):
    for index, overlay_id in enumerate(IDS):
        server.publish(overlay_id, snapshot(index, visible, tick))


def spreads():
    server.set_presentation_held(False)
    results["boot_release"] = watch(True)
    time.sleep(1.5)
    show_all(False)
    results["hide_all"] = watch(False)
    time.sleep(1.5)
    show_all(True)
    results["show_again"] = watch(True)
    time.sleep(1.0)
    show_all(False)
    watch(False)
    time.sleep(1.0)
    show_all(False, tick=1)  # new data while hidden
    time.sleep(1.0)
    show_all(True, tick=1)
    results["show_after_hidden_update"] = watch(True)
    time.sleep(1.5)
    HtmlOverlayServer.set_overrides(hidden=set(IDS))
    results["map_hide"] = watch(False)
    time.sleep(1.5)
    HtmlOverlayServer.set_overrides(hidden=set())
    results["map_show"] = watch(True)
    time.sleep(3.0)


def cpu_phases():
    pids = tree(host.pid)
    labels = kinds(pids)
    for phase, visible, rate in (("idle_visible", True, 0), ("nav10_visible", True, 10),
                                 ("idle_hidden", False, 0), ("nav10_hidden", False, 10)):
        show_all(visible, tick=50)
        watch(visible)
        time.sleep(2.0)
        tick = [100]

        def update():
            server.publish("navigation", snapshot(0, visible, tick[0]))
            tick[0] += 1
            time.sleep(1.0 / rate)
        before = passes["count"]
        result = measure(tree(host.pid), labels, 10.0, update if rate else None)
        result["manifest_passes_per_s"] = round((passes["count"] - before) / 10.0, 1)
        results[f"cpu_{phase}"] = result


def cost_each():
    pids = tree(host.pid)
    labels = kinds(pids)
    for index, overlay_id in enumerate(IDS):
        for other in range(len(IDS)):
            server.publish(IDS[other], snapshot(other, other == index, 7))
        time.sleep(3.0)
        split = measure(pids, labels, 6.0)
        results[overlay_id] = {"gpu": split["split"].get("gpu-process", 0),
                               "renderer": split["split"].get("renderer", 0), "total": split["total"]}
        print(overlay_id, results[overlay_id], flush=True)


def summarise_passes():
    try:
        stats = json.loads(timings.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    durations = [entry[1] for entry in stats["passes"]] or [0]
    shows = [entry[2] for entry in stats["visibility_ms"] if entry[1]] or [0]
    hides = [entry[2] for entry in stats["visibility_ms"] if not entry[1]] or [0]
    results["host"] = {
        "pass_median_ms": round(statistics.median(durations), 2),
        "pass_max_ms": round(max(durations), 1),
        "show_apply_median_ms": round(statistics.median(shows), 1),
        "hide_apply_median_ms": round(statistics.median(hides), 1),
        "steps_median_ms": {name: round(statistics.median(values), 3)
                            for name, values in stats["primitives"].items() if values},
    }


try:
    start = time.perf_counter()
    while time.perf_counter() - start < 90 and not all(
            server.is_ready(overlay_id) and handles()[overlay_id] for overlay_id in IDS):
        time.sleep(0.05)
    time.sleep(2)
    if COST:
        cost_each()
    else:
        spreads()
        cpu_phases()
finally:
    server.request_host_shutdown()
    try:
        host.wait(10)
    except subprocess.TimeoutExpired:
        host.kill()
    server.stop()
    log.close()
summarise_passes()
(OUT_DIR / f"{LABEL}.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
print(json.dumps(results, indent=1))
