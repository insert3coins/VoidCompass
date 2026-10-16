# Void Compass Local API

Void Compass can talk to your own tools. A script, a Stream Deck button, an OBS scene, a Discord bot or a home-made overlay can ask Void Compass what is happening in your game, and tell it to do things: show or hide overlays, put a thought in the Watcher's head, speak through its voice, switch the theme, change track.

Everything is plain HTTP and JSON, so any language works, and there's no key to look after. The API lives at:

```http
http://127.0.0.1:7380/api/v1
```

> The API is version 1. Within version 1, fields and endpoints are only ever added, never removed or renamed, so what you build keeps working.

<!-- group: Start here -->

## Quick start

Three steps, and under a minute.

1. In Void Compass, open **Settings › Integrations › Local API** and switch **Local API** on.
2. Settings says **LISTENING**. That's all the setup there is.
3. Ask Void Compass who you are:

**Windows PowerShell**

```powershell
Invoke-RestMethod http://127.0.0.1:7380/api/v1/commander
```

**curl** (built into Windows 10 and later)

```bat
curl http://127.0.0.1:7380/api/v1/commander
```

**Python** (`pip install requests`)

```python
import requests

API = "http://127.0.0.1:7380/api/v1"

me = requests.get(f"{API}/commander").json()
print(me["name"], "is in", me["location"]["system"])
```

**JavaScript** (a page on this PC, or an OBS browser source)

```javascript
const API = "http://127.0.0.1:7380/api/v1";

const me = await (await fetch(`${API}/commander`)).json();
console.log(me.name, "is in", me.location.system);
```

**In a web browser**, just to look: open `http://127.0.0.1:7380/api/v1/commander`. Or press **TRY** on any endpoint in these docs.

This page itself is served by the API: `http://127.0.0.1:7380/api/v1/docs` (the **API DOCS** button in Settings opens it).

## The basics

How the API behaves: who it answers, what it sends back, and what it never sends.

### No key needed

The API answers without a password. It never talks to the internet itself, your keys and secrets are never in its answers, and out of the box it only answers this PC. That keeps it simple: a script, a Stream Deck button or an OBS source just calls it.

Web browsers are the one thing to be careful with, because any website you visit could try to call `127.0.0.1` too. So the API only answers web pages that live on this PC:

| Page | Answered? |
|---|---|
| A file on this PC, opened in a browser | Yes |
| An OBS browser source with **Local file** ticked | Yes |
| A page served from `localhost` or `127.0.0.1` (your own dev server) | Yes |
| These docs | Yes |
| Any website on the internet | No: it can't read anything or change anything |

Programs (scripts, bots, Stream Deck, curl) aren't web pages, so they're always answered.

### Reading and controlling

Reading (every `GET`) is always allowed. Changing things (every `POST`) needs **Allow control**, which is on unless you switch it off. With it off, the API is read-only and every `POST` answers `403`.

### This PC, or your network

Out of the box the API only answers programs on this PC. Switch on **Allow other devices** to reach it from a phone, a tablet or a second PC on your network: use your PC's address instead of `127.0.0.1`, for example `http://192.168.1.20:7380/api/v1`. Windows may ask whether to let Void Compass through the firewall.

With no key, anything on your network can then use the API, so only do this on a network you trust (your home, not a café or a LAN party).

### Sending data

`POST` requests take a JSON body, with `Content-Type: application/json`. Requests without a body are fine where nothing needs saying (for example `POST /overlays/hide-all`).

### Answers and errors

Answers are JSON. When something goes wrong you get an HTTP status and a message:

```json
{"error": {"status": 409, "message": "The voice is off or not downloaded yet (The Watcher › VOICE)"}}
```

| Status | Means |
|---|---|
| 200 | Done; the answer is in the body |
| 400 | Something in the request is missing or wrong; the message says what |
| 403 | Not allowed: control is off, the call came from another device, a website tried to call it, or that page isn't shared |
| 404 | No such endpoint, page or overlay |
| 405 | Wrong method (a `GET` where a `POST` is needed, or the other way round) |
| 409 | Can't do it right now: the feature is switched off (the message says where to switch it on), or the BGS record isn't open yet |
| 413 | The request body is too big (64 KB at most) |
| 429 | Too many open event streams (16 at most) |
| 503 | Void Compass is closing, or the command deck isn't running |
| 504 | Void Compass was busy for 8 seconds; try again |

### Secrets stay home

Your EDSM, Inara and Raven Colonial keys, Discord webhooks and other secrets are never sent. Anything named like a key, token, webhook, secret or password reads `<hidden>`, and the Settings page isn't shared at all.

## OBS Studio

Put your game on your stream, live, or let the game run OBS for you. Three ways, from the simplest to the most powerful. All of them work with OBS Studio 28 and later.

| Way | What you get | What you need |
|---|---|---|
| Browser source | Live widgets: your system, the Watcher's thoughts, now playing, a session tally. Styled however you like | A small `.html` file (below) |
| Text source from a file | Plain text that OBS reads from a file and keeps up to date | A PowerShell window left running |
| obs-websocket | The game drives OBS: scenes change as you dock, land and jump, replays save themselves | Python, and obs-websocket switched on in OBS |

### Browser source widgets

Save one of these as an `.html` file anywhere, for example `Documents\OBS\system.html`. In OBS: **Sources › + › Browser**, tick **Local file**, pick the file and set the size (800 × 200 is plenty). The background is see-through, it updates the moment something happens, and it reconnects by itself whenever Void Compass restarts.

**System and thoughts**

```html
<!doctype html>
<meta charset="utf-8">
<style>
  body { margin: 0; font: 600 28px "Segoe UI", sans-serif; color: #d8e6ee; text-shadow: 0 0 4px #000; }
  #system::before { content: "CMDR IN "; color: #ff8a3d; font-size: 18px; letter-spacing: .1em; }
  #thought { color: #00d1ff; font-style: italic; }
</style>
<div id="system"></div>
<div id="thought"></div>
<script>
  const API = "http://127.0.0.1:7380/api/v1";
  const show = (id, text) => { document.getElementById(id).textContent = text; };

  fetch(`${API}/commander/location`).then((r) => r.json()).then((here) => show("system", here.system));

  const stream = new EventSource(`${API}/events/stream?types=journal,thought&event=FSDJump,Location,CarrierJump`);
  stream.addEventListener("journal", (message) => show("system", JSON.parse(message.data).data.StarSystem));
  stream.addEventListener("thought", (message) => show("thought", JSON.parse(message.data).data.text));
</script>
```

**Now playing**

```html
<!doctype html>
<meta charset="utf-8">
<style>
  body { margin: 0; font: 600 24px "Segoe UI", sans-serif; color: #fff; text-shadow: 0 0 4px #000; }
  #card { display: inline-block; padding: 10px 18px; border-left: 4px solid #00d1ff;
          background: rgba(7, 11, 16, .7); transition: opacity .5s; }
  #card.off { opacity: 0; }
  small { display: block; color: #91a8b7; font-size: 16px; }
</style>
<div id="card" class="off"><span id="title"></span><small id="artist"></small></div>
<script>
  const API = "http://127.0.0.1:7380/api/v1";
  const card = document.getElementById("card");
  const show = (playing, title, artist) => {
    document.getElementById("title").textContent = title || "";
    document.getElementById("artist").textContent = artist || "";
    card.classList.toggle("off", !playing || !title);
  };

  fetch(`${API}/music`).then((r) => r.json()).then((m) => show(m.playing, m.track?.title, m.track?.artist));
  new EventSource(`${API}/events/stream?types=music`).addEventListener("music", (message) => {
    const m = JSON.parse(message.data).data;
    show(m.playing, m.title, m.artist);
  });
</script>
```

**Session tally**

```html
<!doctype html>
<meta charset="utf-8">
<style>
  body { margin: 0; font: 600 22px "Segoe UI", sans-serif; color: #fff; text-shadow: 0 0 4px #000; }
  b { color: #00d1ff; font-size: 30px; margin-right: 4px; }
  span { margin-right: 22px; }
</style>
<span><b id="jumps">0</b> jumps</span><span><b id="ly">0</b> ly</span><span><b id="scans">0</b> bodies scanned</span>
<script>
  const API = "http://127.0.0.1:7380/api/v1";
  const tally = { jumps: 0, ly: 0, scans: 0 };

  new EventSource(`${API}/events/stream?types=journal&event=FSDJump,Scan`).addEventListener("journal", (message) => {
    const e = JSON.parse(message.data).data;
    if (e.event === "FSDJump") { tally.jumps += 1; tally.ly += e.JumpDist || 0; }
    if (e.event === "Scan" && e.ScanType !== "NavBeaconDetail") tally.scans += 1;
    for (const [id, value] of Object.entries(tally)) {
      document.getElementById(id).textContent = Math.round(value).toLocaleString();
    }
  });
</script>
```

The session tally counts from when its source loads: right-click it and choose **Refresh** to start a new one.

Try a widget in your normal browser first: open the file, and if nothing shows, press F12 and the console says why. A widget must stay a file on this PC (or be served from `localhost`): the API doesn't answer web pages from the internet.

The cockpit overlays can go on stream just as they are, too: add a **Window Capture** and pick the overlay's window from the list.

### Text source from a file

OBS's **Text (GDI+)** source can read its words from a file. Leave this running in a PowerShell window and it keeps two files up to date: where you are, and what's playing.

**Example: system and music as text files** (PowerShell)

```powershell
$api = "http://127.0.0.1:7380/api/v1"
$folder = "$HOME\Documents\OBS"
New-Item -ItemType Directory -Force $folder | Out-Null
while ($true) {
  try {
    $here = Invoke-RestMethod "$api/commander/location"
    Set-Content "$folder\system.txt" $here.system
    $music = Invoke-RestMethod "$api/music"
    $song = if ($music.playing -and $music.track) { "$($music.track.title) - $($music.track.artist)" } else { "" }
    Set-Content "$folder\music.txt" $song
  } catch { }
  Start-Sleep 5
}
```

In OBS: **Sources › + › Text (GDI+)**, tick **Read from file**, and pick `system.txt` (or `music.txt`).

### Let the game drive OBS

OBS has a remote control built in, obs-websocket. Switch it on in OBS under **Tools › WebSocket Server Settings**: tick **Enable WebSocket server**, and copy the password from **Show Connect Info**. Then this script listens to Void Compass and runs OBS for you:

- Scenes change as you dock, launch, land, lift off and jump.
- A text source called `System` follows you from system to system.
- The replay buffer saves the moment you die, or find something new for the Codex.

**Example: the game runs your scenes** (Python, `pip install obsws-python requests`)

```python
import time

import obsws_python as obs
import requests

API = "http://127.0.0.1:7380/api/v1"
OBS = obs.ReqClient(host="localhost", port=4455, password="YOUR_OBS_PASSWORD")

# Journal event -> your scene's name in OBS. Leave out any you don't have.
SCENES = {
    "Docked": "Station",
    "Undocked": "Flight",
    "Touchdown": "Surface",
    "Liftoff": "Flight",
    "StartJump": "Hyperspace",
    "FSDJump": "Flight",
}
TEXT_SOURCE = "System"
WATCH = ",".join([*SCENES, "Location", "Died", "CodexEntry"])


def act(event):
    name = event["event"]
    if name == "StartJump" and event.get("JumpType") != "Hyperspace":
        return  # into supercruise, not a jump
    if name in SCENES:
        OBS.set_current_program_scene(SCENES[name])
    if name in ("FSDJump", "Location"):
        OBS.set_input_settings(TEXT_SOURCE, {"text": event["StarSystem"]}, True)
    if name == "Died" or (name == "CodexEntry" and event.get("IsNewEntry")):
        OBS.save_replay_buffer()  # needs the replay buffer started in OBS


seq = 0
while True:
    try:
        answer = requests.get(f"{API}/events", timeout=40, params={
            "since": seq, "types": "journal", "event": WATCH, "wait": 25}).json()
    except requests.RequestException:
        time.sleep(5)  # Void Compass isn't running yet
        continue
    first = seq == 0
    seq = answer["seq"]
    if first:
        continue  # start from now, not from what happened before
    for item in answer["events"]:
        try:
            act(item["data"])
        except Exception as error:
            print(item["data"]["event"], "-", error)
```

Run it with `python obs-pilot.py` while you stream. If a scene or the text source doesn't exist, it says so and carries on.

## Discord

Bring your game into your Discord server, or let your server talk to the Watcher. Both run on your own PC beside Void Compass. The API never talks to Discord itself; your script does.

| Way | What you get | What you need |
|---|---|---|
| Webhook | A channel that posts as things happen: jumps, first discoveries, docking, deaths, the Watcher's thoughts | A webhook link from the channel's settings, and Python |
| Bot | Slash commands in your server (`/where`, `/ship`, `/status`, `/watcher`, and `/say` to give the Watcher a thought, spoken if its voice is on), plus a live feed to a channel | A bot from the Discord Developer Portal, and Python |
| Squadron BGS | A report of your work each tick, danger alerts for your tracked factions, and a `/bgs` command | The webhook or the bot, and factions tracked on the BGS page |

> Whatever you post, everyone who can read that channel sees: where you are, where you're going. Keep the feed in a channel for people you trust.

### Webhook: your game, posted

A webhook only posts, so there's nothing to log in to.

1. In Discord, open the channel's settings: **Edit Channel › Integrations › Webhooks › New Webhook**, then **Copy Webhook URL**.
2. Paste it into the script below as `WEBHOOK`, and save it as `discord-feed.py`.
3. Run `python discord-feed.py` and leave it running while you play.

**Example: a live feed for your channel** (Python, `pip install requests`)

```python
import time

import requests

API = "http://127.0.0.1:7380/api/v1"
WEBHOOK = "https://discord.com/api/webhooks/..."


def commander():
    """The commander flying now, as Void Compass knows them."""
    try:
        return requests.get(f"{API}/commander", timeout=10).json().get("name") or "Unknown"
    except requests.RequestException:
        return "Unknown"


def words(item, cmdr):
    """What to post for one event, or None to post nothing."""
    data = item["data"]
    if item["type"] == "thought":
        return f'The Watcher, to CMDR {cmdr}: *{data["text"]}*'
    event = data.get("event")
    if event == "FSDJump":
        return f'**CMDR {cmdr}** jumped {data.get("JumpDist", 0):.1f} ly to **{data["StarSystem"]}**'
    if event == "Scan" and data.get("WasDiscovered") is False and data.get("PlanetClass"):
        return f'**CMDR {cmdr}** made a first discovery: **{data["BodyName"]}**, {data["PlanetClass"]}'
    if event == "Docked":
        return f'**CMDR {cmdr}** docked at **{data["StationName"]}** in {data.get("StarSystem", "")}'
    if event == "Died":
        return f"**CMDR {cmdr}** lost their ship. Rebuy time."
    return None


cmdr = commander()
seq = 0
while True:
    try:
        answer = requests.get(f"{API}/events", timeout=40, params={
            "since": seq, "types": "journal,thought", "wait": 25,
            "event": "FSDJump,Scan,Docked,Died,LoadGame,Commander"}).json()
    except requests.RequestException:
        time.sleep(5)  # Void Compass isn't running yet
        continue
    first = seq == 0
    seq = answer["seq"]
    if first:
        cmdr = commander()
        continue  # start from now, not from what happened before
    for item in answer["events"]:
        data = item["data"]
        if data.get("event") in ("LoadGame", "Commander"):
            # Logged in, or switched to another commander: post under their name.
            cmdr = data.get("Commander") or data.get("Name") or cmdr
            continue
        text = words(item, cmdr)
        if text:
            requests.post(WEBHOOK, timeout=10, json={
                "content": text, "username": f"CMDR {cmdr}", "allowed_mentions": {"parse": []}})
            time.sleep(1)  # Discord lets a webhook post a few times a second at most
```

Every post names the commander flying (it follows you if you switch commanders), and posts as **CMDR Name** in the channel. Change `words` to post what you like: any journal event works (add its name to `event`), and `item["type"]` can be `music` or `feed` too (add them to `types`).

### Bot: commands for your server

A bot can answer. Anyone in your server can ask where you are; only you can make the Watcher speak.

1. Go to **discord.com/developers/applications › New Application**. Under **Bot**, press **Reset Token** and copy the token. It's the bot's password: keep it to yourself.
2. Under **Installation** (or **OAuth2 › URL Generator**), tick the scopes `bot` and `applications.commands` and the permission **Send Messages**. Open the link it gives you and add the bot to your server.
3. In Discord, switch on **Settings › Advanced › Developer Mode**. Right-click the channel for the feed and **Copy Channel ID**; right-click your own name and **Copy User ID**.
4. Put the token and both IDs into the script below, save it as `discord-bot.py`, and run `python discord-bot.py`.

The first time, the slash commands can take a few minutes to show up in your server. `/say` needs **Allow control** on; everything else only reads.

**Example: the Void Compass bot** (Python, `pip install discord.py`)

```python
import asyncio

import aiohttp
import discord
from discord import app_commands

API = "http://127.0.0.1:7380/api/v1"
TOKEN = "YOUR_BOT_TOKEN"
FEED_CHANNEL = 123456789012345678  # where jumps, deaths and thoughts are posted (0 for none)
OWNER = 123456789012345678  # your own user ID: only you can make the Watcher speak


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default(), allowed_mentions=discord.AllowedMentions.none())
        self.tree = app_commands.CommandTree(self)
        self.http_api = None

    async def setup_hook(self):
        self.http_api = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=40))
        await self.tree.sync()
        self.loop.create_task(feed())


bot = Bot()


async def get(path, **params):
    async with bot.http_api.get(f"{API}{path}", params=params) as reply:
        return await reply.json()


async def post(path, body):
    async with bot.http_api.post(f"{API}{path}", json=body) as reply:
        return reply.status, await reply.json()


@bot.tree.command(description="Where the commander is right now")
async def where(interaction: discord.Interaction):
    here = await get("/commander/location")
    at = here["station"]["name"] if here["station"] else here["body"] or "open space"
    await interaction.response.send_message(f'**{here["system"] or "Somewhere"}**, {at}')


@bot.tree.command(description="The commander's ship")
async def ship(interaction: discord.Interaction):
    now = await get("/commander/ship")
    name = now["ship"].get("ship_name") or now["ship"].get("ship") or "A ship"
    hull = f'{now["hull_percent"]:.0f}%' if now["hull_percent"] is not None else "unknown"
    cargo = now["cargo"]
    await interaction.response.send_message(
        f'**{name}**, hull {hull}, cargo {cargo["tons"] or 0} of {cargo["capacity"] or 0} t')


@bot.tree.command(description="Is the commander in the game?")
async def status(interaction: discord.Interaction):
    app = await get("/status")
    playing = "flying right now" if app["journal"]["live"] else "not in the game right now"
    await interaction.response.send_message(f'CMDR {app["commander"]} is {playing}.')


@bot.tree.command(description="What the Watcher is thinking")
async def watcher(interaction: discord.Interaction):
    mind = await get("/watcher")
    thought = (mind.get("current") or {}).get("text") or "It's quiet. The eye is watching."
    await interaction.response.send_message(f"*{thought}*")


@bot.tree.command(description="Give the Watcher a thought (spoken, if its voice is on)")
@app_commands.describe(text="What it should think")
async def say(interaction: discord.Interaction, text: str):
    if interaction.user.id != OWNER:
        await interaction.response.send_message("Only the commander can do that.", ephemeral=True)
        return
    code, answer = await post("/watcher/thought", {"text": text, "heading": f"From {interaction.user.display_name}"})
    reply = "Done." if code == 200 else answer["error"]["message"]
    await interaction.response.send_message(reply, ephemeral=True)


async def feed():
    """Jumps, deaths and the Watcher's thoughts, posted as they happen."""
    await bot.wait_until_ready()
    channel = bot.get_channel(FEED_CHANNEL) if FEED_CHANNEL else None
    if channel is None:
        return
    seq = None
    while not bot.is_closed():
        try:
            answer = await get("/events", since=seq or 0, types="journal,thought", event="FSDJump,Died", wait=25)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(5)  # Void Compass isn't running yet
            continue
        first, seq = seq is None, answer["seq"]
        if first:
            continue  # start from now
        for item in answer["events"]:
            data = item["data"]
            if item["type"] == "thought":
                await channel.send(f'*{data["text"]}*')
            elif data.get("event") == "FSDJump":
                await channel.send(f'Jumped to **{data["StarSystem"]}** ({data.get("JumpDist", 0):.1f} ly)')
            elif data.get("event") == "Died":
                await channel.send("Ship lost. Back soon.")


bot.run(TOKEN)
```

Add your own commands the same way: `/music` from `GET /api/v1/music`, `/hide` with `POST /api/v1/overlays/hide-all`, a cockpit pop-up with `POST /api/v1/overlays/notify`. Keep anything that changes things to `OWNER`, like `/say`.

### BGS for your squadron

Your BGS record can feed a squadron's Discord: a report of your work every tick, a warning when one of your factions is in trouble, and a `/bgs` command anyone can use to check on them. Set it up once; after that it runs while you play.

There are two ways, and you can use both:

| | Tick reports and danger alerts | The `/bgs` command |
|---|---|---|
| What the channel gets | Posts by themselves: your work as each tick ends, and each new danger | An answer whenever someone types `/bgs` |
| What you need | A webhook (two clicks in the channel's settings) | The bot above, already running |
| Script | `bgs-reports.py` (below) | A few lines added to `discord-bot.py` |

**Before either: get your BGS record ready**

1. Switch on the Local API: **Settings › Integrations › Local API**.
2. Open the **BGS** page in Void Compass and let it read your journals (the first time takes a moment).
3. Track the factions your squadron supports: on the BGS page, press the star beside each one so it fills in. Reports cover everything you did; the alerts and `/bgs` follow the factions you track.
4. Check it from a browser: `http://127.0.0.1:7380/api/v1/bgs` should list your tracked factions under `tracked_factions`.

#### Way 1: tick reports and danger alerts

1. In Discord, pick the squadron's BGS channel. **Edit Channel › Integrations › Webhooks › New Webhook**, give it a name (say "BGS"), and **Copy Webhook URL**.
2. Save the script below as `bgs-reports.py`, and paste the webhook link in as `WEBHOOK`.
3. Install its one library: `pip install requests`.
4. Run it: `python bgs-reports.py`. Leave the window open while you play (minimise it).

**Example: bgs-reports.py** (Python)

```python
import time

import requests

API = "http://127.0.0.1:7380/api/v1"
WEBHOOK = "https://discord.com/api/webhooks/..."


def post(text):
    requests.post(WEBHOOK, timeout=10, json={"content": text[:1900], "allowed_mentions": {"parse": []}})


tick, warned = None, set()
while True:
    try:
        bgs = requests.get(f"{API}/bgs", timeout=20).json()
    except requests.RequestException:
        time.sleep(60)  # Void Compass isn't running yet
        continue
    if "error" in bgs:
        time.sleep(300)  # the BGS record isn't open yet
        continue
    current = bgs["tick"]["current"]
    if tick is not None and current != tick:
        # A new tick: post what you did in the one that just ended.
        detail = requests.get(f"{API}/bgs/activity", params={"tick": tick}, timeout=20).json().get("detail")
        if detail and detail["systems"]:
            post(detail["report"])
    tick = current
    for alert in bgs["alerts"]:
        key = (alert["system"], alert["faction"], alert["text"])
        if alert["level"] == "danger" and key not in warned:
            warned.add(key)
            post(f'**{alert["faction"]}** in {alert["system"]}: {alert["text"]}')
            time.sleep(1)
    time.sleep(300)  # the BGS moves once a day; every five minutes is plenty
```

What the channel sees when a tick ends: your work during it.

```text
BGS Report - Tick: 16 Oct 09:00

Shinrarta Dezhra
- Jameson Holdings: +6 INF, Bounty vouchers 1.2M, Space CZ 2M
- Pilots' Federation Local Branch: Trade profit 850K

Hatchooe
- Jameson Holdings: +3 INF, Cartographic data 4.1M
```

And when one of your factions is in trouble:

```text
Jameson Holdings in Hatchooe: War pending
Jameson Holdings in Ross 128: Control at risk: Ross 128 Gold Mafia is 1.2 points behind
```

When it starts, it posts the danger alerts already standing, then only new ones. Run it on the PC you play on: the record fills as you fly, so the reports are your own work. If several of you run it into one channel, each posts their own report.

#### Way 2: the /bgs command

This adds to the bot from [Bot: commands for your server](#bot-commands-for-your-server); set that up first.

1. Open `discord-bot.py`. At the top, under the other `import` lines, add `from urllib.parse import quote`.
2. Paste the command below into the file, just above the last line (`bot.run(TOKEN)`).
3. Stop the bot (Ctrl+C in its window) and start it again: `python discord-bot.py`. Discord can take a few minutes to show a new command.
4. In your server, type `/bgs`. Leave `faction` empty for all your tracked factions, or fill it in for one.

**Example: the /bgs command, added to discord-bot.py** (Python)

```python
@bot.tree.command(description="How our factions stand")
@app_commands.describe(faction="A faction's name (leave empty for all tracked)")
async def bgs(interaction: discord.Interaction, faction: str = ""):
    if faction:
        found = await get(f"/bgs/factions/{quote(faction, safe='')}")
        if "error" in found:
            await interaction.response.send_message(found["error"]["message"], ephemeral=True)
            return
        lines = [f'**{found["name"]}**: controls {found["controlled"]} of {len(found["systems"])} systems']
        for system in found["systems"][:10]:
            lines.append(f'- {system["system"]}: {system["influence"] * 100:.1f}%{" (controls)" if system["controlling"] else ""}')
        lines += [f'- {alert["system"]}: {alert["text"]}' for alert in found["alerts"][:5]]
    else:
        overview = await get("/bgs")
        if "error" in overview:
            await interaction.response.send_message(overview["error"]["message"], ephemeral=True)
            return
        lines = [f'**BGS**, tick {overview["tick"]["current_label"]}']
        lines += [f'- **{row["name"]}**: controls {row["controlled"]} of {row["systems"]}, '
                  f'{row["danger"]} danger, {row["warn"]} warnings' for row in overview["tracked_factions"]]
        lines += [f'- {alert["system"]} / {alert["faction"]}: {alert["text"]}'
                  for alert in overview["alerts"] if alert["level"] == "danger"][:5]
    await interaction.response.send_message("\n".join(lines)[:1900])
```

What someone sees after typing `/bgs`:

```text
BGS, tick 16 Oct 09:00
- Jameson Holdings: controls 4 of 6, 1 danger, 2 warnings
- Hatchooe / Jameson Holdings: War pending
```

And after `/bgs faction: Jameson Holdings`:

```text
Jameson Holdings: controls 4 of 6 systems
- Shinrarta Dezhra: 42.3% (controls)
- Hatchooe: 38.0% (controls)
- Ross 128: 21.5%
- Hatchooe: War pending
```

**If something's not right**

- **No reports appear:** a report only comes when a tick ends with work in it. `http://127.0.0.1:7380/api/v1/bgs/activity` shows the ticks it knows about.
- **`/bgs` says the BGS record isn't open yet:** open the BGS page in Void Compass once.
- **`/bgs` lists nothing:** no factions are tracked yet. Press the star beside them on the BGS page.
- **`/bgs faction:` finds no faction by that name:** use the name exactly as the BGS page shows it; `/api/v1/bgs/factions?query=part` finds it.

<!-- group: Reference -->

## App and status

Is Void Compass running, which version, who's flying and whether the game is live.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1` | The API's name, version and every endpoint |
| GET | `/api/v1/ping` | Is Void Compass running? |
| GET | `/api/v1/docs` | This page |
| GET | `/api/v1/status` | The app: version, commander, journal, game, deck page, overlays hidden, voice |

```http
GET /api/v1/status
```

```json
{
  "version": "5.5.7",
  "commander": "Jameson",
  "profile": "jameson_f1234567",
  "journal": {"folder": "C:\\Users\\you\\Saved Games\\Frontier Developments\\Elite Dangerous",
              "last_event_seconds_ago": 4.2, "live": true},
  "game": {"version": "4.1.3.0", "build": "r310412/r0 ", "odyssey": true, "mode": "Solo"},
  "deck_page": "explore",
  "overlays_hidden": false,
  "voice": true
}
```

`journal.live` is true while the game is writing its journal (the Watcher's heartbeat), so it doubles as "is the game running?".

## Commander

Who you are, where you are, and the ship you're in, as the game last told Void Compass.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/commander` | Name, FID, credits, ranks, reputation, ship, home system and where you are |
| GET | `/api/v1/commander/location` | Where you are: system, body, station, docked or landed, on foot, surface position |
| GET | `/api/v1/commander/ship` | Your ship now: fuel, hull, cargo, frame shift drive, heat |

```http
GET /api/v1/commander/location
```

```json
{
  "system": "Shinrarta Dezhra",
  "system_address": 3932277478106,
  "coordinates": [55.71875, 17.59375, 27.15625],
  "body": "Jameson Memorial",
  "station": {"name": "Jameson Memorial", "type": "Orbis", "market_id": 128666762,
              "faction": "Pilots' Federation Local Branch", "government": "Democracy",
              "economy": "High Tech", "allegiance": "PilotsFederation", "distance_ls": 346.0,
              "services": ["dock", "autodock", "commodities"]},
  "docked": true, "landed": false, "on_foot": false, "in_srv": false,
  "in_fighter": false, "in_taxi": false, "multicrew": false,
  "surface": {"latitude": null, "longitude": null, "altitude_m": null, "heading": null, "planet_radius_m": null},
  "destination": null,
  "flight_state": "DOCKED",
  "legal_state": "Clean"
}
```

`station` is `null` when you're not at one. On a planet, `surface` carries your latitude, longitude, altitude and heading.

To put where you are on your stream, see [OBS Studio](#obs-studio).

## Journal

The game writes everything you do to its journal. Void Compass reads it as it's written, and the API passes it on: the same events, field for field, as the game wrote them. Frontier's journal manual lists every event.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/journal/events` | The newest live events since Void Compass started (up to 2000 kept) |
| GET | `/api/v1/journal/history` | Search the journal files on disk, newest first |
| GET | `/api/v1/journal/files` | The journal files, newest first |
| GET | `/api/v1/journal/status` | `Status.json` now: flags, fuel, position, heading, legal state |
| GET | `/api/v1/journal/cargo` | `Cargo.json` now |
| GET | `/api/v1/journal/navroute` | `NavRoute.json`: the route you plotted |
| GET | `/api/v1/journal/market` | `Market.json`: the last market you opened |
| GET | `/api/v1/journal/shiplocker` | `ShipLocker.json`: your on-foot items, components and data |

### Live events

`GET /api/v1/journal/events`

| Parameter | Default | Meaning |
|---|---|---|
| `since` | `0` | Only events after this number (each answer gives the newest `seq`) |
| `event` | all | Only these events, comma separated: `FSDJump,Scan` |
| `limit` | `100` | At most this many (1 to 1000) |

```http
GET /api/v1/journal/events?event=FSDJump&limit=1
```

```json
{"seq": 812, "events": [
  {"seq": 811, "timestamp": "2026-10-16T19:02:11Z", "event": "FSDJump",
   "StarSystem": "Colonia", "SystemAddress": 3238296097059, "StarPos": [-9530.5, -910.28125, 19808.125],
   "JumpDist": 39.12, "FuelUsed": 3.71, "FuelLevel": 28.29}
]}
```

Ask again with `since=812` to get only what's new. For events the moment they happen, use the event stream below instead of asking over and over.

### History

`GET /api/v1/journal/history` reads the journal files on your disk, so it reaches back before Void Compass started: last night, last month, your first jump.

| Parameter | Default | Meaning |
|---|---|---|
| `event` | all | Only these events, comma separated |
| `limit` | `50` | At most this many (1 to 500) |
| `files` | `20` | Look in at most this many journal files, newest first (1 to 200) |
| `after` | | Only events after this time, for example `2026-10-01T00:00:00Z` |
| `before` | | Only events before this time |

```http
GET /api/v1/journal/history?event=Died&files=200&limit=10
```

```json
{"events": [{"timestamp": "2026-09-30T21:14:55Z", "event": "Died", "KillerName": "Thargoid"}],
 "files_scanned": 200}
```

Journal files are big, so give `event` whenever you can: it's much quicker.

**Example: your ten longest jumps this month** (Python)

```python
jumps = requests.get(f"{API}/journal/history", params={
    "event": "FSDJump", "after": "2026-10-01T00:00:00Z", "limit": 500, "files": 200}).json()["events"]
for jump in sorted(jumps, key=lambda j: j["JumpDist"], reverse=True)[:10]:
    print(f'{jump["JumpDist"]:6.2f} ly  {jump["StarSystem"]}')
```

### Companion files

`/journal/status`, `/journal/cargo`, `/journal/navroute`, `/journal/market` and `/journal/shiplocker` give the newest copy of each file exactly as the game wrote it. If the game hasn't written one yet, you get `404`.

## Live events

Two ways to hear things the moment they happen: ask and wait (simple, works everywhere), or open a stream (instant, best for web pages and OBS).

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/events` | Everything since a number you give, waiting a while if there's nothing yet |
| GET | `/api/v1/events/stream` | An open stream that sends each event as it happens |

Every event looks like this:

```json
{"seq": 1044, "type": "journal", "at": 1760641331.42, "data": { "...the event...": true }}
```

| `type` | `data` is |
|---|---|
| `journal` | A journal event, as the game wrote it |
| `status` | `Status.json`, each time it changes |
| `cargo`, `navroute`, `market`, `shiplocker` | That file, each time the game rewrites it |
| `feed` | A line on the command deck's event feed: `at`, `tag`, `severity`, `message` |
| `thought` | The Watcher thought something: `id`, `text`, `heading`, `mood`, `kind` |
| `overlay` | An overlay was switched, moved or faded, or all were hidden or shown |
| `voice` | The voice said something: `text`, and `from` (`watcher` or `api`) |
| `music` | The music started, stopped or changed track: `playing`, `track_id`, `title`, `artist` |

### Ask and wait

`GET /api/v1/events`

| Parameter | Default | Meaning |
|---|---|---|
| `since` | `0` | Only events after this number |
| `types` | all | Only these types, comma separated: `journal,thought` |
| `event` | all | Only these journal events: `FSDJump,Docked` |
| `wait` | `0` | If nothing new, wait up to this many seconds (0 to 30) for something |
| `limit` | `200` | At most this many |

```http
GET /api/v1/events?types=journal,thought&wait=10
```

Keep asking with `since` set to the `seq` from the last answer and `wait=25`: you'll hear each event within moments, with almost no traffic in between.

**Example: tell Discord about every jump** (Python; a fuller feed and a bot are in [Discord](#discord))

```python
import requests

API = "http://127.0.0.1:7380/api/v1"
WEBHOOK = "https://discord.com/api/webhooks/..."

seq = requests.get(f"{API}/events", params={"limit": 1}).json()["seq"]
while True:
    answer = requests.get(f"{API}/events", timeout=40,
                          params={"since": seq, "types": "journal", "event": "FSDJump", "wait": 25}).json()
    seq = answer["seq"]
    for item in answer["events"]:
        jump = item["data"]
        requests.post(WEBHOOK, json={"content": f'Jumped {jump["JumpDist"]:.1f} ly to {jump["StarSystem"]}'})
```

### Stream

`GET /api/v1/events/stream` keeps the connection open and sends each event as it happens, as [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events). It takes `types`, `event` and `since` like `/events` (without `since` it starts from now). Each message's event name is the `type`, and a comment line keeps the connection awake every 15 seconds.

```http
GET /api/v1/events/stream?types=journal,thought,music
```

**Example: listen in a web page** (JavaScript)

```javascript
const stream = new EventSource("http://127.0.0.1:7380/api/v1/events/stream?types=journal,thought");
stream.addEventListener("journal", (message) => console.log("journal", JSON.parse(message.data).data.event));
stream.addEventListener("thought", (message) => console.log("thought", JSON.parse(message.data).data.text));
```

The browser reconnects by itself if Void Compass restarts. Ready-made stream widgets are in [OBS Studio](#obs-studio).

## Command deck

Everything the command deck shows is yours to read: one page at a time, or the whole deck at once.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/dashboard` | The whole deck's state, exactly as the deck draws it (large) |
| GET | `/api/v1/dashboard/pages` | The pages: `data` (readable with the call below) and `open` (any page you can open) |
| GET | `/api/v1/dashboard/pages/{page}` | One page's data, for example `explore`, `trading`, `bgs`, `powerplay` |
| POST | `/api/v1/dashboard/page` | Open a page on the deck: `{"page": "explore"}` |
| GET | `/api/v1/dashboard/feed` | The deck's event feed, newest first (`limit`, default 50) |
| POST | `/api/v1/dashboard/feed` | Add a line to the feed: `{"message": "Hello from the API", "tag": "BOT", "severity": "info"}` |
| GET | `/api/v1/themes` | The active theme, its colours, and every theme you can use |
| POST | `/api/v1/dashboard/theme` | Switch theme: `{"name": "Void Cyan"}` |

The pages you can read are: `achievements`, `bgs`, `build-planner`, `capsules`, `carrier`, `chronicle`, `colonisation`, `constellation`, `engineering`, `explore`, `ground`, `ledger`, `mining`, `mission`, `planet-materials`, `postcards`, `powerplay`, `profile`, `recon`, `screenshots`, `trading` and `watcher`. Their data has the same shape the deck uses, so the easiest way to find a value is to look at the page first: press **TRY** on `/api/v1/dashboard/pages/{page}` above, or open `http://127.0.0.1:7380/api/v1/dashboard/pages/explore` in your browser.

**Example: a feed line and a page switch from a script** (curl, Windows Command Prompt)

```bat
curl -X POST -H "Content-Type: application/json" ^
     -d "{\"message\": \"Carrier jump in 15 minutes\", \"tag\": \"FLEET\", \"severity\": \"warn\"}" ^
     http://127.0.0.1:7380/api/v1/dashboard/feed

curl -X POST -H "Content-Type: application/json" ^
     -d "{\"page\": \"carrier\"}" http://127.0.0.1:7380/api/v1/dashboard/page
```

`severity` is `info`, `warn`, `fail` or `success`. (The `^` carries a command on to the next line in Command Prompt; in PowerShell use a backtick.)

## BGS

The background simulation as Void Compass has recorded it: every faction and system you've seen, your tracked factions and their alerts, conflicts, and the work you've done each tick. It reads the same record as the BGS page, whatever tab the deck has open, and only reads, so it works with Allow control off.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/bgs` | The overview: the tick, your tracked factions, their alerts, the system you're in, and this tick's work |
| GET | `/api/v1/bgs/factions` | Every faction you've seen, tracked ones first (`query` to search by name) |
| GET | `/api/v1/bgs/factions/{name}` | One faction: each system it's in, its influence, states and conflicts, your work for it, its alerts |
| GET | `/api/v1/bgs/systems` | Every system you've recorded (`query` to search, `only=tracked` or `only=conflicts`) |
| GET | `/api/v1/bgs/systems/{address}` | One system by its SystemAddress: its factions, influence history (`days`, default 90) and your work there |
| GET | `/api/v1/bgs/conflicts` | Wars, civil wars and elections in progress or pending, tracked factions first |
| GET | `/api/v1/bgs/activity` | Your work per tick: the ticks with work, and one tick's detail (`tick`, default the newest) |

Influence is a fraction: `0.423` is 42.3%. Times (`ts`, a tick's `start`) are Unix seconds. An alert's `level` is `danger`, `warn`, `good` or `info`, worst first, with its words in `text`.

```http
GET /api/v1/bgs
```

```json
{
  "tick": {"last": 1760605200, "last_label": "16 Oct 09:00", "current": 1760605200, "current_label": "16 Oct 09:00", "estimated": false},
  "tracked_factions": [{"name": "Jameson Holdings", "systems": 6, "controlled": 4, "average": 0.38, "danger": 1, "warn": 2}],
  "alerts": [{"system": "Shinrarta Dezhra", "system_address": 3932277478106, "faction": "Jameson Holdings",
              "level": "danger", "text": "War pending", "ts": 1760610000}],
  "current_system": {"system": "Shinrarta Dezhra", "controlling": "Jameson Holdings", "factions": ["..."]},
  "this_tick": {"label": "16 Oct 09:00", "systems": ["..."], "report": "**BGS Report - Tick: 16 Oct 09:00** ..."}
}
```

`this_tick.report` (and `detail.report` from `/bgs/activity`) is the same Discord-ready report as the BGS page's copy button.

A faction's name goes in the address as it is, with spaces and all encoded: `/api/v1/bgs/factions/Jameson%20Holdings` (PowerShell, Python and JavaScript do this for you, as below). If the BGS record isn't open yet, every call answers `409`.

**Example: your tracked factions at a glance** (PowerShell)

```powershell
$bgs = Invoke-RestMethod http://127.0.0.1:7380/api/v1/bgs
"Tick: $($bgs.tick.current_label)"
foreach ($faction in $bgs.tracked_factions) {
  "{0}: {1} systems, controls {2}, {3} danger, {4} warnings" -f $faction.name, $faction.systems, $faction.controlled, $faction.danger, $faction.warn
}
$bgs.alerts | Where-Object level -eq "danger" | ForEach-Object { "!! $($_.system): $($_.faction), $($_.text)" }
```

**Example: copy this tick's report, ready to paste anywhere** (PowerShell)

```powershell
(Invoke-RestMethod http://127.0.0.1:7380/api/v1/bgs).this_tick.report | Set-Clipboard
```

Paste it into a squadron forum, Inara, a spreadsheet or a message. On a Stream Deck key: **System › Open** with `powershell -WindowStyle Hidden -Command "(Invoke-RestMethod http://127.0.0.1:7380/api/v1/bgs).this_tick.report | Set-Clipboard"`. Nothing is copied if you've done no BGS work this tick yet.

**Example: where to help today** (Python, `pip install requests`)

```python
from urllib.parse import quote

import requests

API = "http://127.0.0.1:7380/api/v1"

overview = requests.get(f"{API}/bgs").json()
for brief in overview["tracked_factions"]:
    faction = requests.get(f"{API}/bgs/factions/{quote(brief['name'], safe='')}").json()
    print(f'\n{faction["name"]}: controls {faction["controlled"]} of {len(faction["systems"])}')
    # Falling influence first, then the weakest: where your work counts most.
    for system in sorted(faction["systems"], key=lambda row: (row["delta"] or 0, row["influence"])):
        change = f'{system["delta"] * 100:+.1f}' if system["delta"] is not None else "new"
        states = ", ".join(state["label"] for state in system["pending"] + system["active"])
        mark = "*" if system["controlling"] else " "
        print(f'  {mark} {system["system"]:<26} {system["influence"] * 100:5.1f}%  {change:>6}  {states}')
```

```text
Jameson Holdings: controls 4 of 6
  * Hatchooe                    38.0%    -2.1  War
    Ross 128                    21.5%    -0.8
  * Shinrarta Dezhra            42.3%    +1.4  Boom
```

`*` marks the systems the faction controls; the change is in points since the update before.

**Example: BGS danger in your cockpit** (Python, `pip install requests`)

```python
import time

import requests

API = "http://127.0.0.1:7380/api/v1"
seen = set()
while True:
    try:
        alerts = requests.get(f"{API}/bgs", timeout=20).json().get("alerts", [])
    except requests.RequestException:
        alerts = []
    for alert in alerts:
        key = (alert["system"], alert["faction"], alert["text"])
        if alert["level"] == "danger" and key not in seen:
            seen.add(key)
            requests.post(f"{API}/overlays/notify", timeout=10, json={
                "title": "BGS", "severity": "warn", "seconds": 12,
                "message": f'{alert["faction"]} in {alert["system"]}: {alert["text"]}'})
            time.sleep(13)  # one at a time
    time.sleep(300)
```

A war or retreat coming for one of your factions pops up in the cockpit, over the game. It needs **Allow control** and the Cockpit Notifications overlay on.

**Example: a system's influence history, into a spreadsheet** (Python, `pip install requests`)

```python
import csv
from datetime import datetime, timezone

import requests

API = "http://127.0.0.1:7380/api/v1"
SYSTEM = "Shinrarta Dezhra"

found = requests.get(f"{API}/bgs/systems", params={"query": SYSTEM}).json()["systems"]
address = next((row["system_address"] for row in found if row["system"].casefold() == SYSTEM.casefold()), None)
if address is None:
    raise SystemExit(f"{SYSTEM} isn't in your BGS record yet")
system = requests.get(f"{API}/bgs/systems/{address}", params={"days": 365}).json()
with open(f"{SYSTEM} influence.csv", "w", newline="", encoding="utf-8") as out:
    sheet = csv.writer(out)
    sheet.writerow(["date", "faction", "influence %", "state", "source"])
    for series in system["history"]:
        for point in series["points"]:
            if point["influence"] is None:
                continue  # the faction wasn't in the system that day
            when = datetime.fromtimestamp(point["ts"], timezone.utc).strftime("%Y-%m-%d %H:%M")
            sheet.writerow([when, series["faction"], round(point["influence"] * 100, 2), point["state"], point["source"]])
print(f"Saved {out.name}")
```

Open the file in Excel or Google Sheets and insert a line chart: each faction's influence over the year, from your own visits and EDSM's history.

**Example: your factions on stream** (an OBS browser source)

```html
<!doctype html>
<meta charset="utf-8">
<style>
  body { margin: 0; font: 600 20px "Segoe UI", sans-serif; color: #fff; text-shadow: 0 0 4px #000; }
  .row { display: flex; gap: 12px; align-items: baseline; }
  .row b { color: #00d1ff; }
  .danger { color: #ff6b70; }
  small { color: #91a8b7; font-size: 14px; }
</style>
<div id="list"></div>
<script>
  const API = "http://127.0.0.1:7380/api/v1";
  const esc = (text) => String(text).replace(/[&<>]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"})[c]);
  async function draw() {
    try {
      const bgs = await (await fetch(`${API}/bgs`)).json();
      document.getElementById("list").innerHTML = (bgs.tracked_factions || []).map((f) =>
        `<div class="row"><b>${esc(f.name)}</b><span>controls ${f.controlled} of ${f.systems}</span>` +
        (f.danger ? `<span class="danger">${f.danger} in danger</span>` : "") + `</div>`).join("") +
        `<small>Tick ${esc(bgs.tick?.current_label || "")}</small>`;
    } catch {
      // Void Compass is closed: the next try puts it back.
    }
  }
  draw();
  setInterval(draw, 5 * 60 * 1000);
</script>
```

Save it as `bgs.html` and add it to OBS like the widgets in [OBS Studio](#obs-studio).

To use the BGS in Discord (a report every tick, danger alerts, and a `/bgs` command), follow [BGS for your squadron](#bgs-for-your-squadron).

## Overlays

Every cockpit overlay can be listed, read, switched on or off, moved and faded, and all of them can be hidden at once, like the hide-all hotkey.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/overlays` | Every overlay: on or off, shown, position, size, opacity |
| GET | `/api/v1/overlays/{id}` | One overlay, with `data`: exactly what its window is showing right now |
| POST | `/api/v1/overlays/{id}` | Change it: `{"enabled": true, "x": 40, "y": 600, "opacity": 80}` (any of them) |
| POST | `/api/v1/overlays/{id}/toggle` | Switch it on if it's off, off if it's on |
| POST | `/api/v1/overlays/hide-all` | Hide every overlay (each keeps its own on/off setting) |
| POST | `/api/v1/overlays/show-all` | Bring them back |
| POST | `/api/v1/overlays/notify` | Pop up a cockpit notification: `{"title": "CARRIER", "message": "Jump in 15 minutes", "severity": "warn", "seconds": 10}` |

The overlay ids are:

| id | Overlay |
|---|---|
| `navigation` | Navigation HUD |
| `survey` | Survey Operations |
| `heartbeat` | Journal Heartbeat (the Watcher) |
| `toast` | Cockpit Notifications |
| `achievements` | Achievements |
| `cargo` | Cargo Manifest |
| `carrier` | Fleet / Squadron Carrier |
| `prospector` | Prospector Analysis |
| `planet-materials` | Planet Materials |
| `powerplay` | Powerplay Operations |
| `gravity` | Gravity Warning |
| `station` | Station Information |
| `galnet-ticker` | Galnet Ticker |
| `music-player` | Music Player |
| `contact-scope` | Deep Space Contact Scope |
| `jump-info` | Jump Info |
| `colony-needs` | Construction Needs |
| `trade-route` | Trade Route |
| `galaxy-minimap` | Galaxy Minimap |
| `postcards` | Postcards |
| `ground-target` | Planet Waypoint Navigation |

`GET /api/v1/overlays` has the full list for your version, including any overlays added later. Studio's own ids (`survey_status_hud` and so on) work too.

`x` and `y` are screen pixels from the top-left of your main display (other displays can be negative). `opacity` is 40 to 100, or 0 to follow the opacity set for all overlays.

**Example: Stream Deck "hide everything for a screenshot"**

Save this as `hide-overlays.ps1`, then give a Stream Deck key a **System › Open** action that runs `powershell -WindowStyle Hidden -File C:\Scripts\hide-overlays.ps1` (use wherever you saved it). Each press hides every overlay, or brings them back:

```powershell
$state = Invoke-RestMethod http://127.0.0.1:7380/api/v1/overlays
$action = if ($state.hidden) { "show-all" } else { "hide-all" }
Invoke-RestMethod -Method Post http://127.0.0.1:7380/api/v1/overlays/$action
```

**Example: a cockpit notification**

```http
POST /api/v1/overlays/notify
{"title": "CARRIER", "message": "Jump in 15 minutes", "severity": "warn", "seconds": 10}
```

`severity` is `info`, `warn`, `fail` or `success`; `seconds` is 2 to 60. The Cockpit Notifications overlay must be on (otherwise `409`).

**Example: read what the Survey overlay shows** (Python)

```python
survey = requests.get(f"{API}/overlays/survey").json()
print(survey["enabled"], survey["data"])
```

`data` is the overlay's own model, the same JSON its window draws from: handy for building your own overlay or stream widget from Void Compass's numbers.

## The Watcher

Read the Watcher's mind, give it a thought of your own, or poke it.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/watcher` | Its nature, how often it talks, your bond, sessions and hours, the thought on screen, and its last 50 thoughts |
| POST | `/api/v1/watcher/thought` | Put a thought beside the orb: `{"text": "Hello from the API.", "heading": "From chat"}` |
| POST | `/api/v1/watcher/poke` | Poke it, like the hotkey: it looks up and answers |

```http
POST /api/v1/watcher/thought
{"text": "Follower count holding steady. Unlike the hull.", "heading": "From chat"}
```

```json
{"id": 412, "text": "Follower count holding steady. Unlike the hull.", "heading": "FROM CHAT", "spoken": true}
```

`text` is up to 400 characters. `heading` is the small line above it (it reads `RELAYED` if you leave it out). When the voice is on it's said aloud too, whatever the voice's level is set to; send `"speak": false` to keep it silent. The thought shows on the orb, joins the Watcher page's log, and goes out on the event stream like any other. The Watcher must be on (Journal Heartbeat in Overlay Studio), otherwise `409`.

## Voice

The Watcher's voice can say anything you give it.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/voice` | `enabled` (switched on), `installed` (downloaded), `ready` (both), `speaking` |
| POST | `/api/v1/voice/say` | Say this: `{"text": "Commander, your carrier departs in five minutes."}` |
| POST | `/api/v1/voice/stop` | Stop talking at once |

The voice must be switched on and downloaded on **The Watcher › VOICE** first, otherwise `409`. Something new to say replaces anything not yet said. Up to 400 characters at a time; the orb's pupil moves with the words.

**Example: talking reminders** (PowerShell)

```powershell
$say = @{ text = "Time to stretch, Commander. The galaxy will wait." } | ConvertTo-Json
Invoke-RestMethod -Method Post http://127.0.0.1:7380/api/v1/voice/say -ContentType "application/json" -Body $say
```

Run it from Windows Task Scheduler every hour.

## Music

The command deck's music player: what's playing, your library, and the transport buttons.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/music` | Playing or not, the track (title, artist, album), position, volume, shuffle, repeat |
| GET | `/api/v1/music/library` | Every track and playlist in your music library |
| POST | `/api/v1/music/play-pause` | Play or pause |
| POST | `/api/v1/music/next` | Next track |
| POST | `/api/v1/music/previous` | Previous track |

The music plays inside the command deck, so the controls work while the deck is open (`deck_open` in `/music` says whether it is). A "now playing" widget for your stream is in [OBS Studio](#obs-studio).

**Example: now playing** (Python)

```python
music = requests.get(f"{API}/music").json()
if music["playing"] and music["track"]:
    print(f'{music["track"]["title"]} by {music["track"]["artist"]}')
```

## Galnet

The news from the galaxy, as the Galnet ticker shows it.

| Method | Path | What it does |
|---|---|---|
| GET | `/api/v1/galnet` | The latest Galnet dispatches Void Compass has fetched |

<!-- group: Help -->

## Troubleshooting

The usual suspects, and what to do about each.

**Nothing answers.** Is the Local API switched on, and does Settings say **LISTENING**? Is the port the one in your address? Try `http://127.0.0.1:7380/api/v1/ping` in a browser.

**Settings says the port is in use.** Another program has it. Choose another port (for example 7381) and use it in your addresses.

**403 "Web pages may only call the API from this PC".** The page is on a website. Save it as a file on this PC (in OBS, tick **Local file**), or serve it from `localhost`.

**403 "Call the API by address".** Use `127.0.0.1` (or `localhost`, or with other devices allowed your PC's address) rather than a web address that points at your PC.

**403 from another device.** Switch on **Allow other devices**, and let Void Compass through the Windows firewall.

**403 on a POST.** **Allow control** is off.

**409.** The feature you asked for is switched off; the message says where to switch it on.

**The browser source shows nothing.** Open its file in a normal browser and press F12: the console shows what went wrong. Most often the API is off, or the source isn't a local file.

**504.** Void Compass was busy (rebuilding its cache, or loading a long journal). Try again in a moment.

## For developers

How the API works underneath, for anyone building something bigger.

- The API runs inside Void Compass; it starts and stops with it.
- Calls are answered on the app's own thread, one at a time, alongside the command deck, so a call never sees half-changed data. Keep frequent polling to a few times a second at most, or use the event stream.
- Journal events are passed on exactly as written. Their meaning is in Frontier's Player Journal manual.
- `GET /api/v1` lists every endpoint with whether it changes things (`control`): handy for checking what a version supports.
- Browsers: answers carry CORS headers for local pages only (`null` and `file://` origins, OBS's `http://absolute`, and `localhost` or loopback addresses; private network addresses too with other devices allowed). Calls by any other name in `Host` are refused, which stops DNS rebinding.
- Every answer is plain JSON (UTF-8). Times from the game are ISO 8601 UTC; times from Void Compass (`at`) are Unix seconds.
