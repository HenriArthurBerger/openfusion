// Mouse and trackpad settings: how to orbit, pan and zoom, as presets from other CAD programs or
// your own. Asked once on first start; Settings (⚙ in the top bar) changes them any time.
// Kept in this browser (in the Mac app: on this Mac).
import { $, esc, toast } from "./api.js";
import { IS_MAC } from "./tools.js";

const KEY = "of-nav-v1";

// each action: the bindings that start it ("button" or "mods+button")
export const PRESETS = {
  openfusion: { label: "OpenFusion", note: "right-drag orbits, middle-drag pans, wheel zooms", orbit: ["right"], pan: ["middle"], zoom: [] },
  fusion: { label: "Fusion 360", note: "middle-drag pans, Shift + middle-drag orbits, wheel zooms", orbit: ["shift+middle"], pan: ["middle"], zoom: [] },
  solidworks: { label: "SolidWorks", note: "middle-drag orbits, Ctrl + middle pans, Shift + middle zooms", orbit: ["middle"], pan: ["ctrl+middle"], zoom: ["shift+middle"] },
  onshape: { label: "Onshape", note: "right-drag orbits, middle-drag (or Ctrl + right) pans, wheel zooms", orbit: ["right"], pan: ["middle", "ctrl+right"], zoom: [] },
  blender: { label: "Blender", note: "middle-drag orbits, Shift + middle pans, Ctrl + middle zooms", orbit: ["middle"], pan: ["shift+middle"], zoom: ["ctrl+middle"] },
};

const DEFAULT = { preset: "openfusion", invertZoom: false, trackpad: "pan" };
const MODS = [["ctrl", IS_MAC ? "⌃ Control" : "Ctrl"], ["shift", IS_MAC ? "⇧ Shift" : "Shift"], ["alt", IS_MAC ? "⌥ Option" : "Alt"], ["meta", IS_MAC ? "⌘ Command" : "Win"]];
const BUTTONS = [["", "—"], ["left", "Left"], ["middle", "Middle"], ["right", "Right"]];

export function load() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "null");
    return v && typeof v === "object" ? { ...DEFAULT, ...v } : null;
  } catch (e) { return null; }
}

function save(s) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* storage unavailable */ } }

// the bindings the viewport uses
export function navOf(s) {
  const src = s.preset === "custom" ? s.custom || PRESETS.openfusion : PRESETS[s.preset] || PRESETS.openfusion;
  return { orbit: src.orbit || [], pan: src.pan || [], zoom: src.zoom || [], invertZoom: !!s.invertZoom, trackpad: s.trackpad || "pan" };
}

export function apply(app, s) { app.vp.setNav(navOf(s)); app.navSettings = s; }

function words(b) {
  if (!b) return "—";
  const parts = b.split("+"), btn = parts.pop();
  const m = Object.fromEntries(MODS);
  return [...parts.map((p) => m[p].replace(/^\S+ /, "")), { left: "left", middle: "middle", right: "right" }[btn] + "-drag"].join(" + ");
}

export class SettingsPanel {
  constructor(app, first = false) {
    this.app = app; this.first = first;
    this.s = JSON.parse(JSON.stringify(load() || DEFAULT));
    this.el = $("settings-panel"); this.el.hidden = false;
    this.el.onclick = (e) => { if (e.target === this.el) this.app.closeSettings(); };
    this.render();
  }

  close() { this.el.hidden = true; this.el.innerHTML = ""; this.el.onclick = null; }

  custom() {
    if (!this.s.custom) { const p = PRESETS[this.s.preset] || PRESETS.openfusion; this.s.custom = { orbit: [...p.orbit], pan: [...p.pan], zoom: [...p.zoom] }; }
    return this.s.custom;
  }

  row(action, label) {
    const b = (this.custom()[action] || [])[0] || "";
    const parts = b ? b.split("+") : [];
    const btn = parts.length ? parts[parts.length - 1] : "";
    return `<tr data-action="${action}"><td>${label}</td>
      <td>${MODS.map(([k, l]) => `<label class="st-mod"><input type="checkbox" data-mod="${k}" ${parts.includes(k) ? "checked" : ""}> ${esc(l.replace(/^\S+ /, ""))}</label>`).join("")}</td>
      <td><select data-btn aria-label="${label} button">${BUTTONS.map(([v, l]) => `<option value="${v}" ${v === btn ? "selected" : ""}>${l}</option>`).join("")}</select></td></tr>`;
  }

  render() {
    const s = this.s, nav = navOf(s);
    this.el.innerHTML = `<div class="st-card2" role="dialog" aria-label="Settings">
      <div class="pp-head"><b>${this.first ? "How do you like to move around?" : "Mouse and trackpad"}</b>
        <span>${this.first ? "Pick the program your hands know; change it any time with ⚙ Settings." : "Orbit, pan and zoom, like the program your hands know."}</span>
        <button type="button" class="pp-x" aria-label="Close">×</button></div>
      <div class="st-presets">${Object.entries(PRESETS).map(([id, p]) => `<button type="button" data-preset="${id}" aria-pressed="${s.preset === id}"><b>${esc(p.label)}</b><span>${esc(p.note)}</span></button>`).join("")}
        <button type="button" data-preset="custom" aria-pressed="${s.preset === "custom"}"><b>My own</b><span>choose a button and keys for each</span></button></div>
      ${s.preset === "custom" ? `<table class="st-custom"><thead><tr><th></th><th>Hold</th><th>and drag with</th></tr></thead><tbody>
        ${this.row("orbit", "Orbit")}${this.row("pan", "Pan")}${this.row("zoom", "Zoom")}</tbody></table>
        <p class="st-note">A plain left drag stays the selection box. Right-click without dragging still opens the menu.</p>` : ""}
      <div class="st-opts">
        <label><input type="checkbox" data-opt="invertZoom" ${s.invertZoom ? "checked" : ""}> Invert zoom (wheel and drag)</label>
        <label>Two fingers on a trackpad <select data-opt="trackpad"><option value="pan" ${s.trackpad !== "orbit" ? "selected" : ""}>pan (Shift: orbit)</option><option value="orbit" ${s.trackpad === "orbit" ? "selected" : ""}>orbit (Shift: pan)</option></select></label>
      </div>
      <p class="st-now">Now: orbit ${esc(nav.orbit.map(words).join(" or ") || "—")} · pan ${esc(nav.pan.map(words).join(" or ") || "—")} · zoom wheel${nav.zoom.length ? " or " + esc(nav.zoom.map(words).join(" or ")) : ""}${IS_MAC ? " or pinch" : ""}. The ✋ and ⟳ buttons by the view cube make a left drag pan or orbit.</p>
      <div class="st-foot"><button type="button" class="primary" data-done>${this.first ? "Start" : "Done"}</button></div>
    </div>`;
    this.bind();
  }

  bind() {
    const q = (x) => this.el.querySelector(x);
    q(".pp-x").onclick = () => this.done();
    q("[data-done]").onclick = () => this.done();
    this.el.querySelectorAll("[data-preset]").forEach((b) => (b.onclick = () => { this.s.preset = b.dataset.preset; if (b.dataset.preset === "custom") this.custom(); this.changed(); }));
    this.el.querySelectorAll("[data-opt]").forEach((i) => (i.onchange = () => { this.s[i.dataset.opt] = i.type === "checkbox" ? i.checked : i.value; this.changed(); }));
    this.el.querySelectorAll("tr[data-action]").forEach((tr) => {
      const upd = () => {
        const btn = tr.querySelector("[data-btn]").value;
        const mods = [...tr.querySelectorAll("[data-mod]")].filter((x) => x.checked).map((x) => x.dataset.mod);
        const b = btn ? [...mods, btn].join("+") : "";
        if (b === "left") { toast("A plain left drag is the selection box: hold a key with it", true); tr.querySelector("[data-btn]").value = ""; return; }
        this.custom()[tr.dataset.action] = b ? [b] : [];
        // one binding does one thing
        for (const other of ["orbit", "pan", "zoom"]) if (other !== tr.dataset.action && b) this.custom()[other] = (this.custom()[other] || []).filter((x) => x !== b);
        this.changed();
      };
      tr.querySelectorAll("input, select").forEach((x) => (x.onchange = upd));
    });
  }

  changed() { save(this.s); apply(this.app, this.s); this.render(); }

  done() { save(this.s); apply(this.app, this.s); this.app.closeSettings(); }
}
