(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const token = params.get("token") || "";
  const overlay = params.get("overlay") || "rhino-minimap";
  const suffix = `token=${encodeURIComponent(token)}&overlay=${encodeURIComponent(overlay)}`;
  const root = document.getElementById("panel");
  const canvas = document.getElementById("map");
  const ctx = canvas.getContext("2d");
  const byId = (id) => document.getElementById(id);
  let revision = -1, polling = false, ready = false, palette = {};
  const set = (id, value, fallback = "—") => { const node = byId(id); if (node) node.textContent = value === null || value === undefined || value === "" ? fallback : String(value); };
  const number = (value, fallback = null) => { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback; };
  function applyTheme(theme = {}, effects = {}) {
    const mapping = {bg:"bg",panel:"panel",panel_alt:"alt",panel_raised:"raised",border:"border",border_soft:"soft",accent:"accent",orange:"orange",text:"text",muted:"muted",dim:"dim",green:"green",yellow:"yellow",red:"red"};
    for (const [key, css] of Object.entries(mapping)) { const value = String(theme[key] || ""); if (/^#[0-9a-f]{6}$/i.test(value)) document.documentElement.style.setProperty(`--${css}`, value); }
    palette = Object.fromEntries(Object.entries(mapping).map(([key, css]) => [css, theme[key] || getComputedStyle(document.documentElement).getPropertyValue(`--${css}`).trim()]));
    const scale = number(effects.text_scale, 1); document.documentElement.style.setProperty("--scale", String(Math.max(.75, Math.min(2, scale))));
    document.body.style.opacity = String(Math.max(.4, Math.min(1, number(effects.opacity, 1))));
    root.classList.toggle("no-crt", !effects.crt); root.classList.toggle("reduced-motion", Boolean(effects.reduced_motion));
  }
  function compass(degrees) {
    if (degrees === null || degrees === undefined) return "";
    const names = ["N","NE","E","SE","S","SW","W","NW"];
    return names[Math.round(((Number(degrees) % 360) + 360) % 360 / 45) % 8];
  }
  function distance(metres) { const value = number(metres, 0); return value >= 1000 ? `${(value / 1000).toFixed(1)} km` : `${Math.round(value)} m`; }
  function fitCanvas() {
    const side = Math.max(180, Math.round(canvas.getBoundingClientRect().width));
    const ratio = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const actual = Math.round(side * ratio);
    if (canvas.width !== actual || canvas.height !== actual) { canvas.width = actual; canvas.height = actual; }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return side;
  }
  function draw(model) {
    const side = fitCanvas(), view = number(model.view_m, 6000), current = model.position || {x:0,y:0};
    const scale = side / (2 * view), px = (x) => side / 2 + (number(x,0) - number(current.x,0)) * scale, py = (y) => side / 2 - (number(y,0) - number(current.y,0)) * scale;
    ctx.clearRect(0, 0, side, side); ctx.fillStyle = palette.bg || "#070b10"; ctx.fillRect(0,0,side,side);
    ctx.save();
    if (model.border_m !== null && model.border_m !== undefined) { ctx.beginPath(); ctx.arc(px(0),py(0),number(model.border_m)*scale,0,Math.PI*2); ctx.clip(); }
    const coverageRadius = number(model.scan_radius_m,2000)*scale;
    ctx.fillStyle = palette.accent || "#00d1ff"; ctx.globalAlpha = .68;
    for (const stamp of model.stamps || []) { ctx.beginPath(); ctx.arc(px(stamp.x),py(stamp.y),coverageRadius+Math.max(1,side/260),0,Math.PI*2); ctx.fill(); }
    ctx.globalAlpha = .23;
    for (const stamp of model.stamps || []) { ctx.beginPath(); ctx.arc(px(stamp.x),py(stamp.y),coverageRadius,0,Math.PI*2); ctx.fill(); }
    ctx.restore(); ctx.globalAlpha = 1;
    const grid = number(model.grid_m,1000), minX = number(current.x)-view, maxX = number(current.x)+view, minY = number(current.y)-view, maxY = number(current.y)+view;
    ctx.strokeStyle = palette.muted || "#91a8b7"; ctx.globalAlpha = .18; ctx.lineWidth = 1;
    ctx.beginPath(); for(let x=Math.ceil(minX/grid)*grid;x<=maxX;x+=grid){ctx.moveTo(px(x),0);ctx.lineTo(px(x),side);} for(let y=Math.ceil(minY/grid)*grid;y<=maxY;y+=grid){ctx.moveTo(0,py(y));ctx.lineTo(side,py(y));} ctx.stroke();
    const anchor = model.anchor || {x:0,y:0};
    ctx.globalAlpha = .55; ctx.strokeStyle = palette.green || "#54e39a"; ctx.lineWidth = 1;
    const rings = model.border_m !== null && model.border_m !== undefined ? model.drive_rings || [] : model.range_rings || [];
    for(const radius of rings){ if(number(radius)<=0) continue; ctx.beginPath();ctx.arc(px(anchor.x),py(anchor.y),number(radius)*scale,0,Math.PI*2);ctx.stroke(); }
    ctx.globalAlpha = 1; ctx.fillStyle = model.centered ? (palette.accent||"#00d1ff") : (palette.green||"#54e39a"); ctx.strokeStyle=palette.bg||"#070b10";ctx.lineWidth=2;ctx.beginPath();ctx.arc(px(anchor.x),py(anchor.y),Math.max(4,side*.012),0,Math.PI*2);ctx.fill();ctx.stroke();
    if(model.border_m !== null && model.border_m !== undefined){ctx.strokeStyle=palette.text||"#dcebf3";ctx.setLineDash([5,5]);ctx.beginPath();ctx.arc(px(0),py(0),number(model.border_m)*scale,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);}
    for(const mark of model.bookmarks || []) { const cx=px(mark.x),cy=py(mark.y),r=Math.max(4,side*.014),colour=mark.depleted?(palette.red||"#ff6b70"):(palette.green||"#54e39a"); if(cx<-r||cy<-r||cx>side+r||cy>side+r)continue;ctx.fillStyle=colour;ctx.strokeStyle=palette.bg||"#070b10";ctx.lineWidth=2;ctx.beginPath();ctx.arc(cx,cy,r,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.font=`bold ${Math.max(10,side*.038)}px Consolas`;ctx.textBaseline="middle";ctx.lineWidth=3;ctx.strokeText(mark.code||"",cx+r+3,cy);ctx.fillText(mark.code||"",cx+r+3,cy); }
    const scanRadius=number(model.scan_radius_m,2000)*scale;ctx.strokeStyle=palette.orange||"#ff8a3d";ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(side/2,side/2,scanRadius,0,Math.PI*2);ctx.stroke();
    const heading=number(current.heading,0)*Math.PI/180,r=Math.max(10,side*.036);ctx.save();ctx.translate(side/2,side/2);ctx.rotate(heading);ctx.fillStyle=palette.orange||"#ff8a3d";ctx.strokeStyle=palette.bg||"#070b10";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(0,-r);ctx.lineTo(r*.7,r*.8);ctx.lineTo(0,r*.45);ctx.lineTo(-r*.7,r*.8);ctx.closePath();ctx.fill();ctx.stroke();ctx.restore();
    const bar=grid*scale,bx=10,by=side-12;ctx.strokeStyle=palette.text||"#dcebf3";ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(bx,by);ctx.lineTo(bx+bar,by);ctx.stroke();ctx.fillStyle=palette.text||"#dcebf3";ctx.font=`${Math.max(9,side*.03)}px Consolas`;ctx.fillText("1.0 km",bx+bar+5,by+3);
  }
  function render(snapshot = {}) {
    applyTheme(snapshot.theme || {}, snapshot.effects || {});
    const model = snapshot.rhino_minimap || {};
    if (!model.active) return;
    set("location", model.header || model.body, "RHINO COVERAGE"); set("map-name", String(model.map_name || "MAP").toUpperCase());
    const targetName = model.centered ? "CENTER" : "DROP POINT"; const bearing = number(model.bearing);
    set("anchor", `${targetName} ${distance(model.distance_m)}${bearing === null ? "" : ` ${compass(bearing)} · ${Math.round(bearing)}°`}`);
    set("area", `${number(model.painted_km2,0).toFixed(2)} KM² PAINTED`);
    set("center-key", `SET CENTER · ${model.hotkeys?.center || "UNBOUND"}`); set("border-key", `SET BORDER · ${model.hotkeys?.border || "UNBOUND"}`); set("reset-key", `RESET MAP · ${model.hotkeys?.reset || "UNBOUND"}`);
    set("border", model.border_m === null || model.border_m === undefined ? "BORDER OPEN" : `BORDER ${distance(model.border_m).toUpperCase()}`);
    const warning = byId("warning"), message = model.notice || (!model.in_reach ? "OUTSIDE SAVED MAP RANGE" : ""); warning.textContent = message; warning.hidden = !message;
    draw(model);
  }
  function contentHeight(){return Math.max(430,Math.ceil(root.getBoundingClientRect().height+2));}
  async function refresh(nextRevision){const response=await fetch(`/api/snapshot?${suffix}`,{cache:"no-store"});if(!response.ok)return;render(await response.json());await new Promise(resolve=>requestAnimationFrame(resolve));revision=nextRevision;try{await fetch(`/api/rendered?${suffix}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision:nextRevision,content_height:contentHeight()})});if(!ready){ready=true;await fetch(`/api/ready?${suffix}`,{method:"POST",body:"{}"});}}catch(_){}}
  async function poll(){if(polling)return;polling=true;try{const response=await fetch(`/api/health?${suffix}`,{cache:"no-store"});if(response.ok){const next=Number((await response.json()).revision);if(Number.isFinite(next)&&next!==revision)await refresh(next);}}catch(_){}finally{polling=false;}}
  window.addEventListener("resize",()=>{if(revision>=0)poll();});poll();window.setInterval(poll,180);
})();
