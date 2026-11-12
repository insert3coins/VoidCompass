"""Void Compass for an AI client, over MCP (stdio). Read-only.

An AI client you already run (Claude Code, the Claude desktop app, any MCP
client) starts this program and asks about your game through Void Compass's
Local API: your commander, where you are, the bodies here, Nearby, your route,
earnings and history. It only ever sends GET requests to this PC, so it can't
press a key or change anything. Nothing here runs inside Void Compass itself.

After ED-Outrider's MCP server (github.com/weslocke/ED-Outrider, GPLv3), on our
own API. MCP's stdio transport: one JSON-RPC 2.0 message per line.

    Turn on Settings > Integrations > Local API in Void Compass, then give your
    client this command:  python tools/mcp/voidcompass_mcp.py
    (VOIDCOMPASS_API sets the address; default http://127.0.0.1:7380/api/v1)
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("VOIDCOMPASS_API", "http://127.0.0.1:7380/api/v1").rstrip("/")
PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER = {"name": "voidcompass", "version": "5.7.8"}
TIMEOUT = 30
MAX_CHARS = 60_000

# (tool name, path, what it answers, its query parameters)
TOOLS = (
    ("commander", "/commander", "The commander: name, credits, ranks, ship, home system and where they are.", {}),
    ("location", "/commander/location", "Where the commander is: system, body, station, docked, landed or on foot.", {}),
    ("ship", "/commander/ship", "The ship now: fuel, hull, cargo, frame shift drive, heat.", {}),
    ("fleet", "/commander/fleet", "Stored ships and each ship's loadout.", {}),
    ("missions", "/missions", "Active missions.", {}),
    ("system_bodies", "/explore/system", "One system's bodies (the current one without a name): class, distance, gravity, "
                                         "biology, geology, rings, firsts, value.", {"name": "A system name (optional)"}),
    ("survey", "/exploration/survey", "The current system's survey: what's still to do, body by body.", {}),
    ("nearby", "/explore/nearby", "Known systems round the commander, from Spansh, with their status and notable worlds.", {}),
    ("route", "/explore/route", "The route being followed: stops, jumps and light years left, refuel stops, fuel warnings.", {}),
    ("unsold", "/exploration", "Unsold exploration and organic data, last sales and records.", {}),
    ("codex", "/codex", "The commander's Codex: organics logged and in which regions.", {"region": "A region name (optional)"}),
    ("earnings", "/commander/earnings", "Earnings by kind and month, where they sold most, species that paid most.",
     {"period": "all, a year (2026) or a month (2026-11)"}),
    ("history", "/history", "A row per session, trips from sale to sale, top finds and records.", {"period": "all or a year"}),
    ("journal_log", "/journal/log", "The journal as readable lines, newest first.", {"q": "Words to search for", "days": "How many days back"}),
    ("status", "/status", "Void Compass itself: version, journal, game, overlays.", {}),
)


def get(path, query=None):
    query = {k: v for k, v in (query or {}).items() if v not in (None, "")}
    url = API + path + (("?" + urllib.parse.urlencode(query)) if query else "")
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "voidcompass-mcp"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as reply:
            text = reply.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        return None, f"Void Compass answered HTTP {exc.code}: {body}"
    except (urllib.error.URLError, OSError):
        return None, ("Void Compass isn't answering. Start it, and turn on Settings > Integrations > Local API "
                      f"(it listens at {API}).")
    return text[:MAX_CHARS] + ("\n…(cut short)" if len(text) > MAX_CHARS else ""), None


def tool_list():
    tools = []
    for name, _path, about, params in TOOLS:
        tools.append({"name": name, "description": about, "annotations": {"readOnlyHint": True},
                      "inputSchema": {"type": "object", "properties": {key: {"type": "string", "description": text}
                                                                      for key, text in params.items()}}})
    return tools


def call(name, arguments):
    spec = next((row for row in TOOLS if row[0] == name), None)
    if spec is None:
        return {"content": [{"type": "text", "text": f"No tool called {name}."}], "isError": True}
    allowed = {key: str(value) for key, value in (arguments or {}).items() if key in spec[3]}
    text, error = get(spec[1], allowed)
    if error:
        return {"content": [{"type": "text", "text": error}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


def handle(message):
    method = message.get("method")
    params = message.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion")
        return {"protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0], "serverInfo": SERVER,
                "capabilities": {"tools": {"listChanged": False}},
                "instructions": "Read-only facts from the player's Elite Dangerous game, as Void Compass knows them."}
    if method == "tools/list":
        return {"tools": tool_list()}
    if method == "tools/call":
        return call(params.get("name"), params.get("arguments"))
    if method == "ping":
        return {}
    raise LookupError(method)


def serve(stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            print("Not JSON: " + line[:200], file=sys.stderr)
            continue
        if "id" not in message:
            continue   # a notification: nothing to answer
        try:
            reply = {"jsonrpc": "2.0", "id": message["id"], "result": handle(message)}
        except LookupError as exc:
            reply = {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": f"Unknown method {exc}"}}
        except Exception as exc:   # noqa: BLE001 - say it, don't die
            reply = {"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32603, "message": str(exc)[:300]}}
        stdout.write(json.dumps(reply) + "\n")
        stdout.flush()


if __name__ == "__main__":
    serve()
