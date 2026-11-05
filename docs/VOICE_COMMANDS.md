# Voice controls in Elite


Choose Aster, Axiom, Meridian or The Watcher with the switcher at the top of the companion page. The same editable command catalogue, bindings and sequences serve either companion. Aster accepts an optional address, for example `Aster, open the galaxy map`, `Aster, where are we?`, `Hello Aster` or `Aster, what can you do?`. Enable its spoken replies on that page’s **VOICE** tab; recognition and the talk key are configured in **Settings → Voice**. [Aster setup](ASTER_COMPANION.md).

Type a command on the Watcher page, or hold the talk key and say it. Turn on hearing in **Settings > Voice**; its Talk control card links to **Hotkeys** to choose the talk key or controller button. Commands use the same path whether spoken or typed.

Spoken replies and Watcher lines play in order. Each line finishes, followed by a 0.6-second pause before the next. Hush, turning voice off, or starting the talk microphone still stops speech and clears waiting lines.

**Settings > Voice > What you can say** lists app and Elite commands. App actions need no Elite keys; ship commands show their keyboard bindings and any missing actions. Give those actions keyboard keys in Elite's own controls; a secondary key is fine. The current controller preset can remain in use. Void Compass reads the active General, Ship, SRV and On-foot presets and uses their actual bindings, including modifier combinations. It brings Elite forward and stops pressing if it loses focus.

## Maps, panels and menus

Try “open the galaxy map”, “show me the star map”, “open the system map”, “close the system map”, “open the FSS”, “close the FSS”, “open the codex”, “open the left panel”, “show navigation”, “open contacts”, “show modules”, “open comms” or “open the role panel”. “Please” and “can you” are optional. “Toggle” also works for maps and panels. The Orrery counts as an open system map.

Elite remembers each panel's tab. “Open contacts” focuses the left panel; it does not promise to select the Contacts tab. Status.json reports the panel, but not its tab or highlighted item. Use “next tab”, “previous tab”, “next page”, “previous page”, “menu up”, “menu down”, “menu left”, “menu right”, “select” and “go back” to navigate. Menu commands require an open screen.

Open and close requests check the reported state again when they run, so a queued request does not blindly toggle a screen that is already in the requested state. Cockpit panels close with the bound UI Back action.

## Sequences

These follow Starling's approach: several Elite actions, using the commander's keys, with waits between steps.

| Command | Behaviour and starting point |
| --- | --- |
| Request docking | Focus the left panel, next tab twice, up, right, select, then return two tabs and close. Starts from Navigation with the intended port targeted. Based on Starling's recorded sequence. |
| Deploy the Nomad | Focus the role panel, down, right, select. Depends on the role panel's current selection. |
| Launch the ship | Down, then select in the docked cockpit menu. Requires the ship to be docked with other screens closed. |
| Assist wingman one / two / three | Target the wingman, wait, then select their target. |

Expand **Edit sequence** beside any of these in Settings > Voice. Enter one step per line; changes save when the field loses focus. **Restore default steps** removes that command's override. Custom steps belong to the current commander profile.

Every catalogue command now has an editor, including **Maps and panels > open the galaxy map / open the system map**. Screens have separate open and close editors, and each vehicle has its own steps. The default map steps are `GalaxyMapOpen` and `SystemMapOpen` in the ship, with the SRV and on-foot action names in their own editors. These press the keyboard bindings assigned to those Elite actions, including modifiers. A controller-only action still needs a keyboard binding in Elite; a sequence can instead use other already-bound actions to navigate the menu. Restore default steps to return to the direct map binding.

| Step | Meaning |
| --- | --- |
| `UI_Select` | Press the keyboard binding for that Elite action. |
| `UI_Down x3` | Press the action three times, with gaps. |
| `wait 0.5` | Wait half a second. |
| `hold UI_Select 1.2` | Hold the action's key and modifiers for 1.2 seconds. |
| `focus FocusLeftPanel 2` | Open the left panel if needed and wait for its reported focus. If another screen is open, stop. |
| `ensure FocusLeftPanel 2` | The same conditional focus step; useful after menu keys that also have flight bindings. |
| `leave UI_Back 2` | Close the left panel only while it is the current screen; skip if already in the cockpit. |

Panel focus numbers are right panel **1**, left panel **2**, comms **3**, role panel **4**. Sequences can contain up to 60 steps after expansion, repeats up to 12 and waits/holds up to 5 seconds each. All required bindings are checked before the sequence starts. Opening a panel must be confirmed by Status.json before subsequent menu steps run. An unexpected screen, changed vehicle or focus loss stops the sequence.

Elite does not report enough UI state to verify every tab, menu item or docking request. Adjust these recorded defaults to your menu layout and timing. There are no literal desktop keys or shell steps; cargo ejection and self-destruct actions are excluded.

### Record a sequence in Elite

Every bound-action sequence has **RECORD IN ELITE**, including separate open/close and vehicle sequences. **ADD COMMAND** also offers a recorder for a new custom command.

1. Start Elite with your usual bindings. Open **Settings > Voice**, find the command, choose **EDIT COMMAND** and select the sequence you want to replace. For a new command, choose **ADD COMMAND** and select **RECORD FOR: Ship / SRV / On foot**.
2. Choose **RECORD IN ELITE**, then switch to Elite. The editor stays in place; recording status and a Stop button appear beside its Record control. Choose **REVIEW RECORDING** when finished to open the review panel. Release any controls held while switching windows. Perform the sequence using your keyboard, controller buttons, hat or button combinations.
3. Return to VoidCompass to stop automatically, or choose **STOP RECORDING**. Leaving Elite, changing vehicles or reaching the two-minute limit ends capture. App shortcuts and automated ship commands pause while the recorder is armed or recording.
4. Review the captured actions. Each captured key or button has an action preselected. Shared bindings use the current panel, observed panel changes, the sequence being edited and the recorded keyboard combination to suggest a match. Review the suggestion, change it if needed, or choose **Skip this input**. The recorder captures General controls and the selected vehicle's controls. Controller actions still need keyboard bindings for playback.
5. Review the generated steps and edit the timing if needed. **USE & SAVE SEQUENCE** replaces only the selected sequence through the normal settings save. Once the save succeeds, the recording review closes and you return to that sequence editor. A rejected save keeps the review and draft open. For a new command, **USE IN NEW COMMAND** fills its default sequence and selects the recorded vehicle; finish its name, spoken phrase and aliases, then choose **CREATE COMMAND**. **DISCARD RECORDING** leaves saved steps unchanged.

Only bound inputs are read while Elite has focus. Mouse movement and joystick axes are not recorded. Input holds and gaps become action names and waits, with playback's existing minimum gaps accounted for. Panel focus keys add conditional `focus` / `leave` steps where the reported state allows it. Initial waiting before the first input is omitted.

For **Request docking**, begin in the cockpit with the left panel on Navigation and the intended port targeted. Record opening the left panel, moving to Contacts, selecting the port and requesting docking. Then move left out of the request column, restore Navigation and close the panel. Returning the menu to the same state is needed for a second request: Elite does not report the selected tab or highlighted contact. Record and review both the request and that return path.

Capture allows up to 30 bound inputs; the generated sequence must fit the existing 60-step limit. Holds longer than five seconds and overlapping actions need a new recording or a skipped input. Modifier combinations are recorded as the combined action. Shared bindings are assigned automatically and remain editable during review. Switching commander discards the transient recording, and nothing is saved until you use it.

## Power and other controls

“Four pips to systems”, “max engines”, “full power to weapons”, “4 sys 2 wep”, “pips 4 0 2”, “power to weapons” and “balance power” work as before. The distributor is read back after each press when setting a target allocation.

The catalogue also covers flight, throttle, ship switches, targeting, combat utilities, fighter orders, SRV controls and on-foot tools, equipment and menus. The examples below show every registered command; a command only works in the vehicle or on-foot context where its Elite action exists. “Lights on/off” selects ship lights, SRV headlights or the on-foot torch as appropriate.

### Maps and panels

| Say | Available in |
| --- | --- |
| open the galaxy map | Ship, SRV, On foot |
| open the system map | Ship, SRV, On foot |
| open the FSS | Ship |
| open the codex | Ship, SRV |
| open the left panel | Ship, SRV |
| open the right panel | Ship, SRV |
| open comms | Ship, SRV, On foot |
| open the role panel | Ship, SRV |
| camera suite | Ship, SRV, On foot |

### Menus

| Say | Available in |
| --- | --- |
| next tab | Ship, SRV, On foot |
| previous tab | Ship, SRV, On foot |
| next page | Ship, SRV, On foot |
| previous page | Ship, SRV, On foot |
| menu up | Ship, SRV, On foot |
| menu down | Ship, SRV, On foot |
| menu left | Ship, SRV, On foot |
| menu right | Ship, SRV, On foot |
| select | Ship, SRV, On foot |
| go back | Ship, SRV, On foot |

### The ship

| Say | Available in |
| --- | --- |
| gear down | Ship |
| deploy hardpoints | Ship |
| open the cargo scoop | Ship, SRV |
| lights on | Ship, SRV, On foot |
| night vision on | Ship, On foot |
| silent running on | Ship |
| flight assist off | Ship |
| analysis mode | Ship, SRV |
| combat mode | Ship, SRV |
| toggle orbit lines | Ship |
| head look | Ship, SRV |

### Flight

| Say | Available in |
| --- | --- |
| engage supercruise | Ship |
| jump | Ship |
| boost | Ship |
| all stop | Ship |
| quarter throttle | Ship |
| half throttle | Ship |
| three quarter throttle | Ship |
| full throttle | Ship |

### Targets

| Say | Available in |
| --- | --- |
| target the next system | Ship |
| next target | Ship |
| previous target | Ship |
| target ahead | Ship, SRV |
| target the highest threat | Ship |
| next hostile | Ship |
| previous hostile | Ship |
| target's target | Ship |
| next subsystem | Ship |
| previous subsystem | Ship |
| target wingman one | Ship |
| target wingman two | Ship |
| target wingman three | Ship |
| wing nav lock | Ship |
| assist wingman one | Ship |
| assist wingman two | Ship |
| assist wingman three | Ship |

### Combat

| Say | Available in |
| --- | --- |
| heat sink | Ship |
| shield cell | Ship |
| chaff | Ship |
| ECM | Ship |
| next fire group | Ship, SRV |
| previous fire group | Ship, SRV |
| radar range up | Ship |
| radar range down | Ship |

### Fighter

| Say | Available in |
| --- | --- |
| open fighter orders | Ship |
| fighter attack my target | Ship |
| fighter defend | Ship |
| fighter aggressive | Ship |
| hold fire | Ship |
| hold position | Ship |
| fighter follow me | Ship |
| recall the fighter | Ship |

### The SRV

| Say | Available in |
| --- | --- |
| recall the ship | SRV |
| drive assist on | SRV |
| turret mode | SRV |

### On foot

| Say | Available in |
| --- | --- |
| holster | On foot |
| reload | On foot |
| primary weapon | On foot |
| secondary weapon | On foot |
| toggle suit shields | On foot |
| use a medical pack | On foot |
| use an energy cell | On foot |
| next weapon | On foot |
| previous weapon | On foot |
| select utility slot | On foot |
| swap weapons | On foot |
| equip energy link | On foot |
| equip composition scanner | On foot |
| equip suit tool | On foot |
| toggle tool mode | On foot |
| open item wheel | On foot |
| open emote wheel | On foot |
| show mission help | On foot |
| open access panel | On foot |
| next grenade type | On foot |
| previous grenade type | On foot |
| select frag grenade | On foot |
| select EMP grenade | On foot |
| select shield grenade | On foot |
| throw a grenade | On foot |
| melee | On foot |
| interact | On foot |
| secondary interact | On foot |
| crouch | On foot |
| sprint | On foot |
| walk | On foot |
| hop | On foot |
| aim | On foot |
| ping | On foot |

### Sequences

| Say | Available in |
| --- | --- |
| request docking | Ship |
| deploy the Nomad | Ship |
| launch the ship | Ship |

### Faster speech recognition

Settings → Voice has visible cards for recognition, microphone and talk control, followed by searchable command rows. Use **Fast** for commands: Whisper Base English (148 MB), with a single decoding pass. **Accuracy** keeps Whisper Small English (488 MB) and its fallback decoding for difficult speech and unusual system names. Existing installations keep their current Small model until you choose Fast; new installations start with Fast. Switching to a model that is not installed downloads it while voice is enabled. Both models can stay installed, so switching back needs no download.

Recognition warms in the background when the Watcher starts or hearing is enabled, without opening the microphone. It sleeps after ten unused minutes. Releasing the talk key sends the recording immediately; quiet ends are trimmed with padding, and the Watcher starts its reply as soon as the words are recognised. The page shows the last release-to-recognition time; synthesis and any online lookup add their own time. Hold mode avoids waiting for a second tap. Speech stays on this PC.

Use **All**, **Ready**, **Needs keys** or **Custom**, or search for a command. **Edit command** opens that command’s sequence; the buttons choose its vehicle and open/close action. Missing Elite keyboard bindings are shown alongside the phrase. Spoken replies also require Watcher → Voice enabled and the orb enabled in Overlay Studio.

## Your command catalogue

Settings → Voice now lists app actions alongside all ship commands. Every row has **Edit command**: change its display name, main spoken phrase, aliases (one complete phrase per line), group and enabled state. **Also accept original built-in phrases** keeps the original grammar available; turn it off to replace those phrases. Display names label the rows; the main phrase and aliases are what you say. Restore name & phrases restores the original metadata without changing your sequence overrides.

Music, clipboard actions, showing/hiding/enabling/disabling each overlay, voice hush, greetings and the capability rundown are editable too. App actions do not need Elite key bindings. Market-search main phrases and aliases use **{commodity}**, such as `find sellers for {commodity}` on the buy command. The commodity is passed to the same Spansh lookup; renaming a command does not change what it does.

**Add command** creates a command from a name, spoken phrase, aliases, group, reply, available vehicles and an initial bound-action sequence. Its vehicle-specific sequences can then be edited separately. Custom commands can be deleted; built-in commands can be disabled or restored. Names, aliases, groups and sequences follow the current commander. A phrase already used by another enabled command is rejected, and invalid definitions do not partially save. Sequences retain the normal bound-key, focus and size checks.

Filters show all commands, ready commands, missing keys, custom commands, edited commands or disabled commands. Search includes names, phrases, aliases, groups and action names. Command metadata saves with **Save name & phrases**, so incomplete edits are not applied while you type. Sequence edits save when you leave their field.

### Docking request default

The docking sequence starts with the left panel on Navigation and the intended station targeted. After selecting Request docking it moves left before returning the two tabs, leaving the panel ready for a later request. Elite does not report the selected tab or highlighted item, so these remain timing-dependent menu steps. The default is:

```text
focus FocusLeftPanel 2
wait 0.5
hold CycleNextPanel 0.15
wait 0.5
hold CycleNextPanel 0.15
wait 1.15
ensure FocusLeftPanel 2
hold UI_Right 0.15
wait 1.2
ensure FocusLeftPanel 2
hold UI_Select 0.15
wait 1.2
hold UI_Left 0.15
wait 1.2
ensure FocusLeftPanel 2
hold CyclePreviousPanel 0.15
wait 0.7
hold CyclePreviousPanel 0.15
wait 0.85
leave UI_Back 2
```

Existing custom docking sequences are preserved. Use **Restore default steps** on that sequence to adopt the revised default.

### Conversation

“Hello”, “hello Watcher” and similar greetings have 50 written replies. “Watcher, what can you do?” has ten written rundowns of Void Compass. Each pool is used before repeating, with no immediate repeat at a cycle boundary. Replies appear in Talk and beside the orb, and are spoken in full when the Watcher's voice is on. The greetings keep to the Watcher's established character without revealing later story chapters. You can rename these commands and replace their spoken phrases just like other app actions.

## Worked examples

### Rename the galaxy-map command

1. Open Settings > Voice, search for `galaxy map`, and choose **Edit command** on the galaxy-map row.
2. Set **Display name** to `Star chart` and **Main spoken phrase** to `open star chart`.
3. Put these complete phrases in **Aliases**, one per line:

   ```text
   show star chart
   close star chart
   ```

4. Leave **Also accept original built-in phrases** on to keep requests such as "open the galaxy map", or turn it off to replace them.
5. Choose **Save name & phrases**. The name changes in the catalogue; existing bindings and vehicle-specific sequences are preserved.

"Open star chart" opens the map; "close star chart" closes it. Open and close still check the game's reported screen state. Each vehicle still needs a suitable keyboard binding, or its own configured sequence.

### Give a music action a new phrase

Find **play music**, choose **Edit command**, then use:

| Field | Example |
| --- | --- |
| Display name | Ship soundtrack |
| Main spoken phrase | spin a record |
| Aliases | start the soundtrack |
| Group | Music |

Save the command. "Spin a record" now uses the existing music Play action. To replace the original requests too, turn off **Also accept original built-in phrases**. The selected music and playback behaviour come from the Music page; renaming does not select a particular song.

### Add a custom cockpit sequence

Choose **Add command** and fill in:

| Field | Example |
| --- | --- |
| Display name | Status peek |
| Main spoken phrase | show cockpit status |
| Aliases | quick status peek |
| Group | My cockpit |
| Watcher's reply | Showing the right panel briefly. |
| Available in | Ship |

Use these default steps:

```text
focus FocusRightPanel 1
wait 2
leave UI_Back 1
```

Choose **Create command**. Starting from the cockpit with other panels closed, "show cockpit status" opens the right panel, waits two seconds, then closes it. It uses the panel's remembered tab; it does not choose a particular tab. `FocusRightPanel` and `UI_Back` must have keyboard bindings in Elite, and Elite must remain in front.

Find it again under **Custom commands** or search for `Status peek`. Its editor lets you change the name, aliases, reply and group, or edit the sequence. Selecting more vehicles creates separate sequence editors: use the correct bound actions for each vehicle. **Delete custom command** removes its definition and saved sequence overrides.

### Rename a market search

In **Market uplink**, edit the buy command. For example:

| Field | Example |
| --- | --- |
| Display name | Find a supplier |
| Main spoken phrase | find sellers for {commodity} |
| Aliases | source {commodity} |

Save it, then say or type "find sellers for tritium" or "source gold". Keep `{commodity}` in every phrase for this command; replace it with the actual commodity when speaking. It remains a **buy** search regardless of its display name. Edit the separate sell command for buyer searches.

For **where to sell** questions, the Watcher asks for prices updated within the last **24 hours** first and returns **two distinct stations**, ranked by sell price within that recent group. If fewer than two recent stations are found, it fills the remaining places with older reports and states their age; unknown ages are labelled. It gives fewer results when Spansh knows fewer buyers, and does not add a third nearest-station result. Your Sell cargo radius, pad, carrier and planetary filters still apply. Buying searches keep their existing best-price and nearest-station answers.

Trading searches must be enabled in Settings > Integrations. The uplink uses the Trading page's search options and returns the market data it receives; renaming does not change its search radius or station filters.

### Change a greeting or the programme rundown

Under **Conversation**, edit `hello watcher` or `what can you do`. You might label the greeting `Old friend`, give it the main phrase `awake old friend`, and add `are you there watcher` as an alias. Keep the original phrases enabled if you still want "hello" to work.

The greeting still draws from its 50 written replies; the rundown still draws from its ten explanations. Changing names and aliases changes how you call them, while each command keeps its response pool. Ask "Watcher, what can you do?" for the default rundown. Replies appear as text and are spoken in full when the Watcher's voice is enabled and not hushed.

### Adopt the revised docking default

Search for `request docking`, open its command editor, and choose **Restore default steps** for its Ship sequence if you previously saved different steps. Leave the sequence field so the change saves. The default includes `hold UI_Left 0.15` after selecting the docking request, before the two `CyclePreviousPanel` steps. This resets the column before returning the tabs.

Start from the left panel's Navigation tab with the intended station targeted. The Watcher can verify the open panel, but Elite does not report its selected tab or highlighted contact. If your layout or timings differ, edit and check the sequence for your setup.
