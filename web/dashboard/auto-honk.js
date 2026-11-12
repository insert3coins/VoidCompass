const NAMED_KEYS = {
  Space: "Space", Enter: "Enter", NumpadEnter: "Numpad_Enter", Backspace: "Backspace", Tab: "Tab",
  ArrowUp: "UpArrow", ArrowDown: "DownArrow", ArrowLeft: "LeftArrow", ArrowRight: "RightArrow",
  Home: "Home", End: "End", PageUp: "PageUp", PageDown: "PageDown", Insert: "Insert", Delete: "Delete",
  Minus: "Minus", Equal: "Equals", BracketLeft: "LeftBracket", BracketRight: "RightBracket",
  Semicolon: "SemiColon", Quote: "Apostrophe", Backquote: "Grave", Backslash: "BackSlash",
  Comma: "Comma", Period: "Period", Slash: "Slash", CapsLock: "CapsLock", NumLock: "NumLock", ScrollLock: "ScrollLock",
  NumpadAdd: "Numpad_Add", NumpadSubtract: "Numpad_Subtract", NumpadMultiply: "Numpad_Multiply",
  NumpadDivide: "Numpad_Divide", NumpadDecimal: "Numpad_Decimal",
};

export function autoHonkBinding(value, escapeHtml) {
  return `<div class="setting-row auto-honk-binding" data-auto-honk-binding data-search="auto honk scanner fire key hotkey bind keyboard"><span class="setting-copy"><b>Discovery Scanner key</b><small>Record the keyboard key you use for Primary or Secondary Fire in Elite. Assign the Discovery Scanner to that button in your arrival fire group. A key on its own works; Escape cancels recording.</small><small data-auto-honk-note role="status">${value ? "Scanner key ready." : "Record a scanner key to use auto honk."}</small></span><span class="setting-control hotkey-cell"><input data-setting="auto_honk_key" value="${escapeHtml(value || "")}" placeholder="No scanner key" readonly aria-label="Discovery Scanner key"><button type="button" data-auto-honk-record>RECORD</button><button type="button" class="hotkey-x" data-auto-honk-clear aria-label="Clear Discovery Scanner key"${value ? "" : " disabled"}>✕</button></span><span class="setting-flag" aria-live="polite"></span></div>`;
}

export function installAutoHonkBinding(command) {
  let recording = null;
  let expiry = 0;
  let generation = 0;
  const note = (row, text) => { const node = row?.querySelector("[data-auto-honk-note]"); if (node) node.textContent = text; };
  async function finish(message) {
    ++generation;
    clearTimeout(expiry);
    const row = recording;
    recording = null;
    row?.classList.remove("recording");
    note(row, message);
    if (row) await command("workspace", {page: "settings", operation: "capture_end"});
  }
  document.addEventListener("click", async (event) => {
    const row = event.target.closest?.("[data-auto-honk-binding]");
    if (recording && row !== recording) await finish("Recording cancelled.");
    if (!row) return;
    if (event.target.closest("[data-auto-honk-clear]")) {
      if (recording) await finish("Scanner key cleared.");
      const input = row.querySelector("[data-setting]");
      input.value = "";
      input.dispatchEvent(new Event("change", {bubbles: true}));
      note(row, "Record a scanner key to use auto honk.");
      row.querySelector("[data-auto-honk-clear]").disabled = true;
    } else if (event.target.closest("[data-auto-honk-record]")) {
      if (recording) { await finish("Recording cancelled."); return; }
      const request = ++generation;
      recording = row;
      const accepted = await command("workspace", {page: "settings", operation: "capture_begin"});
      if (request !== generation || !row.isConnected) { if (recording === row) await finish("Recording cancelled."); return; }
      if (!accepted) { await finish("Could not start recording. Try again."); return; }
      row.classList.add("recording");
      row.querySelector("[data-auto-honk-record]").focus({preventScroll: true});
      note(row, "PRESS YOUR SCANNER KEY · ESC TO CANCEL");
      expiry = setTimeout(() => finish("Recording timed out. Press RECORD to try again."), 20000);
    }
  });
  window.addEventListener("keydown", async (event) => {
    if (!recording || !recording.classList.contains("recording")) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.repeat) return;
    if (event.key === "Escape") { await finish("Recording cancelled."); return; }
    if (/^(?:Control|Alt|Shift|Meta)(?:Left|Right)?$/.test(event.code || event.key)) {
      note(recording, "KEEP HOLDING · PRESS THE FINAL KEY");
      return;
    }
    const code = event.code || "";
    const key = NAMED_KEYS[code] || (/^Key[A-Z]$/.test(code) ? code.slice(3) : /^Digit[0-9]$/.test(code) ? code.slice(5)
      : /^Numpad[0-9]$/.test(code) ? `Numpad_${code.slice(6)}` : /^F(?:[1-9]|1[0-9]|2[0-4])$/.test(code) ? code : "");
    if (!key) { note(recording, "Use a keyboard key, with optional Ctrl, Alt or Shift."); return; }
    const modifiers = [];
    if (event.ctrlKey) modifiers.push("Ctrl");
    if (event.altKey) modifiers.push("Alt");
    if (event.shiftKey) modifiers.push("Shift");
    if (event.metaKey) modifiers.push("Win");
    const chord = [...modifiers, key].join("+");
    const row = recording;
    const input = row.querySelector("[data-setting]");
    input.value = chord;
    await finish(`Captured ${chord}.`);
    if (input.isConnected) {
      input.dispatchEvent(new Event("change", {bubbles: true}));
      row.querySelector("[data-auto-honk-clear]").disabled = false;
    }
  }, true);
  window.addEventListener("blur", () => { if (recording) finish("Recording cancelled."); });
}
