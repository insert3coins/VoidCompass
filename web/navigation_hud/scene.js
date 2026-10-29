import {ThreeSurface} from './scene-three.js';
(() => {
  'use strict';

  /*
   * Navigation scene
   * ----------------
   * Every navigation state projects its own animated Three.js hologram in the deck
   * beside the ship; the ship's bay keeps only its systems round it. The geometry
   * evokes the cockpit instrument for that state and never invents telemetry.
   * Anything that reads as a quantity (altitude, scan progress, probes used,
   * threat level, boost tier, shields) is drawn from the journal or
   * Status.json; everything else is decorative motion.
   *
   * One 30 fps clock draws both surfaces. It stops while the overlay is
   * hidden or the page is in the background, and under reduced motion each
   * change paints a single still frame instead. A state change re-projects
   * the hologram: the outgoing scene folds to a bright line and the new one
   * opens from it. Related states (supercruise to assist, say) cross-fade.
   */

  const TAU = Math.PI * 2;
  const FRAME_MS = 1000 / 30;
  // Hologram modes (Overlay Studio, 5.5.3). Full animates every frame.
  // Still, for low-end PCs, animates only while a state change re-projects
  // the hologram, then holds that state's settled still and draws nothing
  // until the next change. Off draws no hologram at all.
  const SCENE_MODES = new Set(['full', 'still', 'off']);
  // A still canvas has no next frame to restore it if WebView2 wipes it
  // (a graphics reset, memory reclaimed while hidden), so Still and reduced
  // motion repaint their one frame this often as a backstop.
  const STILL_REFRESH_MS = 5000;
  const REPROJECT_MS = 540;
  const CROSSFADE_MS = 380;
  const FOLD = .035;
  // Reduced motion paints one pose per state; this phase shows every scene
  // with its moving parts spread out rather than bunched at the origin.
  const STILL_PHASE = 1.37;
  const clamp = (value, low = 0, high = 1) => Math.max(low, Math.min(high, value));
  const lerp = (from, to, t) => from + (to - from) * t;
  const smooth = (value) => {
    const t = clamp(value);
    return t * t * (3 - 2 * t);
  };
  // ---------------------------------------------------------------------
  // State keys. Python publishes a motion family and a label; the scene
  // needs the finer distinction between, say, a system map and an orrery.
  // ---------------------------------------------------------------------

  const PLANETARY = new Set([
    'orbital_approach', 'glide', 'surface_approach', 'surface_hold',
    'surface_departure', 'orbital_departure',
  ]);

  function sceneKey(motionValue, labelValue, vehicleValue) {
    const motion = String(motionValue || 'flight');
    const label = String(labelValue || 'FLIGHT').toUpperCase();
    const vehicle = String(vehicleValue || '').toLowerCase();
    if (motion === 'scanner') return label.startsWith('DSS') ? 'dss' : 'fss';
    if (motion === 'supercruise' && label === 'TAXI') return 'taxi';
    if (motion === 'map') {
      return ({
        'GALAXY MAP': 'galaxy_map', 'SYSTEM MAP': 'system_map',
        'POWER MAP': 'power_map', ORRERY: 'orrery', CODEX: 'codex',
      })[label] || 'map';
    }
    if (motion === 'surface_vehicle') {
      for (const name of ['nomad', 'scorpion', 'rhino']) {
        if (label === name.toUpperCase() || vehicle === name) return name;
      }
      return label === 'SCARAB' || vehicle === 'scarab' ? 'scarab' : 'srv';
    }
    if (motion === 'fsd_charge') return label === 'HYPER CHARGE' ? 'hyper_charge' : 'fsd_charge';
    if (motion === 'jump') return label === 'JUMPING' ? 'jumping' : 'hyperspace';
    if (motion === 'arrival' && label === 'INTERDICTION EVADED') return 'interdiction_evaded';
    if (motion === 'fsd_lock') {
      if (label === 'MASS LOCK') return 'mass_lock';
      if (label.startsWith('FSD INJECTION')) return 'fsd_injection';
      if (label === 'SIGNAL DROP') return 'signal_drop';
      return label.startsWith('SIGNAL THREAT') ? 'signal_threat' : 'signal_lock';
    }
    if (motion === 'combat') {
      if (label === 'INTERDICTED') return 'interdicted';
      return label === 'INTERDICTION' ? 'interdiction' : 'combat';
    }
    if (motion === 'target_lock') {
      return ({
        'SYSTEM TARGET': 'target_system', 'BODY TARGET': 'target_body',
        'SIGNAL TARGET': 'target_signal', 'TARGET CLEARED': 'target_clear',
      })[label] || 'target_lock';
    }
    if (motion === 'docking_denied') {
      if (label === 'DOCK CANCELLED') return 'docking_cancelled';
      return label === 'DOCK TIMEOUT' ? 'docking_timeout' : 'docking_denied';
    }
    if (motion.startsWith('vehicle_')) {
      const kind = label.includes('NOMAD') || vehicle === 'nomad' ? 'nomad'
        : label.includes('FIGHTER') || vehicle === 'fighter' ? 'fighter'
          : label.includes('SCORPION') || vehicle === 'scorpion' ? 'scorpion'
            : label.includes('RHINO') || vehicle === 'rhino' ? 'rhino'
              : label.includes('SRV') || label.includes('SCARAB') || vehicle === 'scarab' ? 'srv'
                : label.includes('CREW') ? 'crew' : 'ship';
      return `${motion}_${kind}`;
    }
    if (motion === 'flight' && label === 'MULTICREW') return 'multicrew';
    if (motion === 'docked' && label === 'STATION') return 'station';
    if (motion === 'station') return label === 'CARRIER VICINITY' ? 'carrier_vicinity' : 'station_vicinity';
    return motion;
  }

  // Related states share a group. Moving between states in one group
  // cross-fades; anything else re-projects the whole hologram.
  const AURA_GROUPS = {
    cruise: ['supercruise', 'supercruise_overcharge', 'supercruise_assist', 'taxi',
      'local_arrival', 'interdiction_evaded'],
    charge: ['fsd_charge', 'hyper_charge', 'fsd_injection'],
    tunnel: ['hyperspace', 'jumping', 'carrier_transit'],
    flare: ['arrival', 'carrier_arrival'],
    cool: ['fsd_cooldown'],
    descent: [...PLANETARY],
    pad: ['landed', 'surface_station', 'settlement_area'],
    dock: ['docked', 'station', 'station_vicinity', 'docking_clearance', 'docking_denied',
      'docking_cancelled', 'docking_timeout', 'docking_assist', 'maintenance',
      'carrier_vicinity', 'carrier_preparing', 'carrier_lockdown'],
    ground: ['srv', 'scarab', 'scorpion', 'rhino', 'nomad', 'srv_handbrake', 'srv_turret',
      'srv_drive_assist'],
    foot: ['on_foot', 'carrier_deck'],
    sensor: ['fss', 'dss', 'map', 'galaxy_map', 'system_map', 'power_map', 'orrery', 'codex',
      'phenomena', 'exploration', 'target_lock', 'target_system', 'target_body',
      'target_signal', 'target_clear'],
    rocks: ['asteroid_field'],
    lock: ['mass_lock', 'signal_lock', 'signal_drop', 'capital_contact', 'unknown_contact'],
    alarm: ['combat', 'heavy_combat', 'srv_threat', 'interdiction', 'interdicted',
      'signal_threat', 'heat_critical', 'suit_hazard', 'jet_cone_damage', 'system_reboot'],
    panel: ['left_panel', 'right_panel', 'comms_panel', 'role_panel', 'station_services'],
  };
  const AURA_OF = new Map(Object.entries(AURA_GROUPS)
    .flatMap(([aura, keys]) => keys.map((key) => [key, aura])));
  const auraOf = (key) => (key.startsWith('vehicle_') ? 'handoff' : AURA_OF.get(key) || 'idle');

  // Seconds per animation cycle, per state. Faster states read as urgent.
  const PERIODS = {
    flight: 1.9, fighter: .82, multicrew: 1.5, exploration: 2.25,
    supercruise: .94, taxi: 1.56, supercruise_overcharge: .48,
    supercruise_assist: 1.28, flight_assist_off: .84, silent_running: 2.2,
    fsd_charge: .86, hyper_charge: .64, hyperspace: .58, jumping: .72,
    arrival: 1.15, interdiction_evaded: 1.05, fsd_cooldown: 1.55,
    local_arrival: 1.42, fsd_injection: 1.9, target_lock: 2.2,
    target_system: 1.9, target_body: 1.7, target_signal: 1.42, target_clear: 1.8,
    carrier_vicinity: 2.3, station_vicinity: 2.1, carrier_preparing: 1.6,
    carrier_lockdown: 1.4, carrier_transit: 1.08, carrier_arrival: 1.34, carrier_deck: 2.4,
    fss: 1.52, dss: 1.82, map: 2.1, galaxy_map: 2.35,
    system_map: 1.86, power_map: 1.7, orrery: 2.5, codex: 1.9,
    phenomena: 2.6, docking_assist: 1.34, settlement_area: 1.95,
    srv_threat: .72, capital_contact: 1.48, unknown_contact: 1.72, heavy_combat: .56,
    left_panel: 1.62, right_panel: 1.62, comms_panel: 1.34,
    role_panel: 1.78, station_services: 2.05,
    orbital_approach: 1.68, glide: .82, surface_approach: 1.38,
    surface_hold: 2.25, surface_departure: 1.28, orbital_departure: 1.55,
    landed: 2.4, on_foot: 1.32, srv: 1.18, scarab: 1.18,
    scorpion: .9, rhino: 1.04, nomad: 1.05,
    srv_handbrake: 1.8, srv_turret: 1.2, srv_drive_assist: 1.35,
    asteroid_field: 5.2, mass_lock: 1.12, signal_lock: 1.55,
    signal_drop: .92, signal_threat: .76, combat: .64,
    interdiction: .5, interdicted: .43, docked: 2.3, station: 2.1,
    surface_station: 1.72,
    heat_critical: .58, suit_hazard: .72, jet_cone_damage: .46,
    docking_clearance: 1.42, docking_denied: .68,
    docking_cancelled: 1.1, docking_timeout: .8,
    maintenance: 1.7, system_reboot: .92,
  };
  const periodOf = (key) => PERIODS[key] || (key.startsWith('vehicle_') ? 1.3 : 1.45);

  function dynamicsOf(raw) {
    const source = raw && typeof raw === 'object' ? raw : {};
    const number = (value, fallback, low, high) => {
      if (value == null || value === '') return fallback;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? clamp(parsed, low, high) : fallback;
    };
    return {
      gravity: number(source.gravity_g, 0, 0, 20),
      altitude: number(source.altitude_m, -1, -1, 100000000),
      vertical: number(source.vertical_mps, 0, -5000, 5000),
      scan: number(source.scan_percent, 0, 0, 1),
      landingGear: Boolean(source.landing_gear),
      cargoScoop: Boolean(source.cargo_scoop),
      hardpoints: Boolean(source.hardpoints_deployed),
      shieldsKnown: Boolean(source.shields_known),
      shieldsUp: Boolean(source.shields_up),
      nightVision: Boolean(source.night_vision),
      inMainShip: Boolean(source.in_main_ship),
      lowFuel: Boolean(source.low_fuel),
      fuelScooping: Boolean(source.fuel_scooping),
      overheating: Boolean(source.overheating),
      silentRunning: Boolean(source.silent_running),
      neutronBoost: Boolean(source.neutron_boost),
      neutronBoostValue: number(source.neutron_boost_value, 0, 0, 10),
      fsdInjection: Boolean(source.fsd_injection),
      fsdInjectionPercent: number(source.fsd_injection_percent, 0, 0, 100),
      // Where you're docked or on foot (5.5.17): the scene follows.
      dockPlace: ['orbital', 'outpost', 'carrier', 'surface'].includes(source.dock_place) ? source.dock_place : 'orbital',
      footPlace: ['planet', 'concourse', 'hangar', 'carrier'].includes(source.foot_place) ? source.foot_place : 'planet',
    };
  }

  // Frontier reports the boost multiplier; three tiers keep the jet-cone
  // threads readable without pretending to plot the exact value.
  function boostTier(dynamics) {
    if (!dynamics?.neutronBoost) return 0;
    const value = Number(dynamics.neutronBoostValue) || 0;
    return value >= 5.5 ? 3 : value >= 3.5 ? 2 : 1;
  }

  // Theme tokens as the page resolved them; app.js passes the live values.
  const TOKENS = ['hud', 'orange', 'accent', 'green', 'yellow', 'red', 'text', 'muted', 'dim', 'bg', 'inset'];
  function cssPalette() {
    const style = getComputedStyle(document.documentElement);
    const palette = {};
    for (const name of TOKENS) palette[name] = style.getPropertyValue(`--${name}`).trim();
    palette.hud = palette.hud || palette.orange;
    palette.state = palette.hud;
    return palette;
  }

  const DECK = new Set(["flight", "flight_assist_off", "silent_running", "fighter", "multicrew", "exploration", "supercruise", "supercruise_overcharge", "supercruise_assist", "taxi", "fsd_charge", "hyper_charge", "hyperspace", "jumping", "arrival", "local_arrival", "interdiction_evaded", "fsd_cooldown", "fsd_injection", "carrier_preparing", "carrier_lockdown", "carrier_transit", "carrier_arrival", "carrier_vicinity", "carrier_deck", "fss", "dss", "map", "galaxy_map", "system_map", "power_map", "orrery", "codex", "phenomena", "target_lock", "target_system", "target_body", "target_signal", "target_clear", "orbital_approach", "orbital_departure", "glide", "surface_approach", "surface_hold", "surface_departure", "landed", "surface_station", "settlement_area", "asteroid_field", "mass_lock", "signal_lock", "signal_drop", "signal_threat", "capital_contact", "unknown_contact", "combat", "heavy_combat", "srv_threat", "interdiction", "interdicted", "heat_critical", "suit_hazard", "jet_cone_damage", "system_reboot", "docked", "station", "station_vicinity", "docking_clearance", "docking_denied", "docking_cancelled", "docking_timeout", "docking_assist", "maintenance", "srv", "scarab", "scorpion", "rhino", "nomad", "srv_handbrake", "srv_turret", "srv_drive_assist", "on_foot", "left_panel", "right_panel", "comms_panel", "role_panel", "station_services"]);

  class NavigationScene {
    constructor({deck = null, bay = null} = {}) {
      this.surfaces = [];
      if (deck?.getContext) this.surfaces.push(new ThreeSurface(deck, 'deck'));
      if (bay?.getContext) this.surfaces.push(new ThreeSurface(bay, 'bay'));
      this.state = null;
      this.previous = null;
      this.transition = null;
      this.palette = cssPalette();
      this.energy = 1;
      this.reduced = false;
      this.mode = 'full';
      this.visible = true;
      this.textScale = 0;
      this.clock = performance.now();
      this.lastFrame = 0;
      this.event = null;
      this.eventSequence = null;
      this.gear = null;
      this.frameId = 0;
      this.frames = 0;
      this.frameCallback = (now) => this.frame(now);
      this.stillTimer = 0;
      this.handleVisibility = () => {
        this.clock = performance.now();
        this.schedule();
        if (!document.hidden) this.repaint(true);
      };
      // A reset graphics context comes back blank: draw it again.
      this.handleRestored = () => {
        this.clock = performance.now();
        this.repaint(true);
        this.schedule();
      };
      this.surfaces.forEach((surface) => surface.canvas.addEventListener('contextrestored', this.handleRestored));
      document.addEventListener('visibilitychange', this.handleVisibility);
      if (typeof ResizeObserver === 'function') {
        // Resizing clears a canvas. Observers run before the browser paints,
        // so repainting here means a resize (a ship name appearing under the
        // portrait, say) never flashes an empty frame.
        this.observer = new ResizeObserver(() => {
          this.surfaces.forEach((surface) => surface.resize());
          this.repaint(true);
        });
        this.surfaces.forEach((surface) => this.observer.observe(surface.canvas));
      }
    }

    get key() {
      return this.state?.key || '';
    }

    get running() {
      return Boolean(this.frameId);
    }

    get renderer() {
      return this.surfaces.some(surface => surface.failed) ? 'unavailable' : 'three';
    }

    update(input = {}) {
      const now = performance.now();
      this.advance(now);
      this.palette = {...cssPalette(), ...(input.palette || {})};
      this.energy = clamp(Number(input.energy) || 1, .55, 1.6);
      this.reduced = Boolean(input.reduced);
      const mode = SCENE_MODES.has(input.mode) ? input.mode : 'full';
      const modeChanged = mode !== this.mode;
      this.mode = mode;
      this.visible = input.visible !== false;
      // The text size zooms the page without resizing the canvases' CSS
      // boxes, so ResizeObserver never hears of it; re-measure on change.
      const textScale = Number(input.textScale) || 1;
      const rescaled = textScale !== this.textScale;
      if (rescaled) {
        this.textScale = textScale;
        this.surfaces.forEach((surface) => surface.resize());
      }
      const next = this.makeState(input);
      const current = this.state;
      if (current && next.d.inMainShip && current.d.inMainShip
          && next.d.landingGear !== current.d.landingGear && !this.reduced && this.mode === 'full') {
        this.gear = {down: next.d.landingGear, start: now};
      }
      if (!current) this.state = next;
      else if (next.identity !== current.identity) this.changeTo(next, now);
      else this.refresh(next);
      if (input.eventSequence != null && input.eventSequence !== this.eventSequence) {
        this.eventSequence = input.eventSequence;
        if (input.eventKind && !this.reduced && this.mode === 'full') {
          this.event = {kind: String(input.eventKind), tone: String(input.eventTone || ''), start: now};
        }
      }
      if (this.reduced || this.mode === 'off') {
        this.previous = null;
        this.transition = null;
      }
      if (this.reduced || this.mode !== 'full') {
        // Still and Off spend no frames on journal pulses or the gear.
        this.event = null;
        this.gear = null;
      }
      if (this.mode === 'still' && !this.transition) this.settle(this.state);
      this.schedule();
      this.repaint(rescaled || modeChanged);
    }

    // Still and reduced motion both show each state's settled pose.
    settled() {
      return this.reduced || this.mode === 'still';
    }

    settle(state) {
      if (!state) return;
      Object.assign(state, {p: STILL_PHASE, terrain: STILL_PHASE, age: 30});
      Object.assign(state.d, state.target);
    }

    makeState(input) {
      const label = String(input.label || 'FLIGHT').toUpperCase();
      const vehicleKey = String(input.vehicleKey || '').toLowerCase();
      const shipKey = String(input.shipKey || '').toLowerCase();
      const key = sceneKey(input.motion, label, vehicleKey);
      const d = dynamicsOf(input.dynamics);
      const palette = {...this.palette, ...(input.palette || {})};
      return {
        key,
        label,
        vehicleKey,
        shipKey,
        aura: auraOf(key),
        identity: `${key}|${label}|${vehicleKey}|${shipKey}|${boostTier(d)}|${key === 'docked' ? d.dockPlace : ['on_foot','suit_hazard'].includes(key) ? d.footPlace : ''}`,
        c: palette.state || palette.hud,
        d,
        target: {altitude: d.altitude, vertical: d.vertical, gravity: d.gravity},
        starTone: String(input.starTone || ''),
        starFamily: String(input.starFamily || ''),
        targetTone: String(input.targetTone || ''),
        targetFamily: String(input.targetFamily || ''),
        // Silent running seals the ship's emissions; its hologram dims too.
        halo: d.silentRunning ? .35 : 1,
        level: input.quiet ? .8 : 1,
        p: 0,
        terrain: 0,
        age: 0,
      };
    }

    changeTo(next, now) {
      const current = this.state;
      next.p = current.p;
      next.terrain = current.terrain;
      // Planetary phases share one physical frame, so altitude and descent
      // keep easing from where they were rather than jumping.
      if (PLANETARY.has(next.key) && PLANETARY.has(current.key)) {
        for (const field of ['altitude', 'vertical', 'gravity']) next.d[field] = current.d[field];
      }
      if (this.reduced || !this.visible || this.mode === 'off') {
        this.state = next;
        this.previous = null;
        this.transition = null;
        return;
      }
      if (this.mode === 'still') {
        // Still re-projects between the two settled poses.
        this.settle(current);
        this.settle(next);
      }
      // An interrupted change continues from exactly what is on screen.
      let from = current, fromScale = 1;
      if (this.transition && this.previous) {
        const k = this.progress(now);
        if (this.transition.crossfade) {
          from = k < .5 ? this.previous : current;
        } else if (k < .5) {
          from = this.previous;
          fromScale = this.foldScale(k);
        } else {
          fromScale = this.openScale(k);
        }
      }
      const crossfade = from.aura === next.aura;
      this.previous = from;
      this.state = next;
      this.transition = {start: now, duration: crossfade ? CROSSFADE_MS : REPROJECT_MS, crossfade, fromScale};
    }

    refresh(next) {
      const state = this.state;
      state.c = next.c;
      state.starTone = next.starTone;
      state.starFamily = next.starFamily;
      state.targetTone = next.targetTone;
      state.targetFamily = next.targetFamily;
      state.halo = next.halo;
      state.level = next.level;
      for (const [field, value] of Object.entries(next.d)) {
        if (field in state.target) state.target[field] = value;
        else state.d[field] = value;
      }
      if (this.settled()) Object.assign(state.d, state.target);
    }

    progress(now) {
      return this.transition ? clamp((now - this.transition.start) / this.transition.duration) : 1;
    }

    foldScale(k) {
      return lerp(this.transition.fromScale, FOLD, smooth(k * 2));
    }

    openScale(k) {
      return lerp(FOLD, 1, smooth((k - .5) * 2));
    }

    advance(now) {
      const dt = clamp((now - this.clock) / 1000, 0, .1);
      this.clock = now;
      if (!dt || this.settled() || !this.visible || document.hidden) return;
      const blend = 1 - Math.exp(-dt / .3);
      for (const state of [this.state, this.previous]) {
        if (!state) continue;
        state.age += dt;
        for (const field of ['altitude', 'vertical', 'gravity']) {
          const target = state.target[field], old = state.d[field];
          state.d[field] = field === 'altitude' && (old < 0 || target < 0) ? target : old + (target - old) * blend;
        }
        const rate = this.energy / periodOf(state.key);
        state.p += dt * rate;
        state.terrain += dt * rate * (.65 + clamp(Math.abs(state.d.vertical) / 160));
      }
    }

    active() {
      if (!this.state || !this.surfaces.length || !this.visible || this.reduced || document.hidden) return false;
      if (this.surfaces.find(surface => surface.role === 'deck')?.failed) return false;
      if (this.mode === 'off') return false;
      // Still runs only while a change re-projects the hologram.
      return this.mode === 'full' || Boolean(this.transition);
    }

    schedule() {
      if (this.active()) {
        if (!this.frameId) this.frameId = requestAnimationFrame(this.frameCallback);
      } else if (this.frameId) {
        cancelAnimationFrame(this.frameId);
        this.frameId = 0;
      }
      clearTimeout(this.stillTimer);
      this.stillTimer = 0;
      const still = (this.mode === 'still' || this.reduced) && this.mode !== 'off';
      if (still && this.state && this.visible && !document.hidden && !this.frameId) {
        this.stillTimer = setTimeout(() => {
          this.stillTimer = 0;
          this.repaint(true);
          this.schedule();
        }, STILL_REFRESH_MS);
      }
    }

    frame(now) {
      this.frameId = 0;
      if (!this.active()) return;
      // Moving to a monitor with another scale factor changes no CSS size.
      const rescaled = this.surfaces.some((surface) => surface.dpr !== (window.devicePixelRatio || 1));
      if (rescaled) this.surfaces.forEach((surface) => surface.resize());
      this.advance(now);
      const elapsed = now - this.lastFrame;
      if (elapsed >= FRAME_MS - .1 || rescaled) {
        // Keep the remainder so 60 Hz displays get an even 30 fps.
        this.lastFrame += Math.floor((elapsed + .1) / FRAME_MS) * FRAME_MS;
        this.draw(now);
      }
      if (!this.active()) {
        // Still: the change has landed. Hold its settled pose, no more frames.
        this.repaint(true);
        this.schedule();
        return;
      }
      this.frameId = requestAnimationFrame(this.frameCallback);
    }

    // Keep the canvases truthful whenever the loop will not: reduced motion
    // gets a settled still, a hidden overlay is current the moment it shows,
    // and `force` covers a canvas the browser has just cleared.
    repaint(force = false) {
      if (!this.state || (this.running && !force)) return;
      if (this.mode === 'off') {
        for (const surface of this.surfaces) surface.begin();
        return;
      }
      if (!this.settled()) {
        this.draw(performance.now());
        return;
      }
      const state = this.state;
      const saved = {p: state.p, terrain: state.terrain, age: state.age};
      Object.assign(state, {p: STILL_PHASE, terrain: STILL_PHASE, age: 30});
      Object.assign(state.d, state.target);
      this.draw(performance.now());
      Object.assign(state, saved);
    }

    draw(now) {
      if (!this.state) return;
      const k = this.progress(now);
      if (this.transition && k >= 1) { this.transition = null; this.previous = null; }
      let layers = [{state: this.state, alpha: 1, fold: 1}];
      if (this.transition && this.previous) {
        if (this.transition.crossfade) layers = [
          {state: this.previous, alpha: 1 - smooth(k), fold: 1},
          {state: this.state, alpha: smooth(k), fold: 1},
        ];
        else layers = k < .5
          ? [{state: this.previous, alpha: 1, fold: this.foldScale(k)}]
          : [{state: this.state, alpha: 1, fold: this.openScale(k)}];
      }
      if (this.event && now - this.event.start > 2200) this.event = null;
      if (this.gear && now - this.gear.start > 1080) this.gear = null;
      for (const surface of this.surfaces) surface.render(
        surface.role === 'bay' ? [{state:this.state, alpha:1, fold:1}] : layers,
        this.palette, {event:this.event, gear:this.gear, now});
      this.frames += 1;
    }

    pixels(id = 'deck-canvas') {
      return this.surfaces.find(surface => surface.canvas.id === id)?.pixels() || new Uint8Array();
    }

    dispose() {
      if (this.frameId) cancelAnimationFrame(this.frameId);
      this.frameId = 0;
      this.observer?.disconnect();
      this.surfaces.forEach(surface => surface.dispose());
      document.removeEventListener('visibilitychange', this.handleVisibility);
      clearTimeout(this.stillTimer);
    }
  }

  NavigationScene.sceneKey = sceneKey;
  NavigationScene.auraOf = auraOf;
  NavigationScene.hasScene = (key) => DECK.has(key) || key.startsWith('vehicle_');
  NavigationScene.renderer = 'three';
  window.NavigationScene = NavigationScene;
})();
