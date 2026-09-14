(() => {
  "use strict";
  const params=new URLSearchParams(location.search), token=params.get("token")||"", overlay=params.get("overlay")||"gravity";
  const root=document.getElementById("gravity");
  const set=(id,value)=>{const node=document.getElementById(id);if(node)node.textContent=value;};
  function render(snapshot={}){VoidCompassOverlay.applyTheme(root,snapshot.theme,snapshot.effects);const data=snapshot.gravity||{},g=Number(data.g),threshold=Number(data.threshold)||3,severity=["warning","high","critical"].includes(data.severity)?data.severity:"warning";root.className=`gravity ${severity}${snapshot.effects?.crt?"":" no-crt"}${snapshot.effects?.reduced_motion?" reduced-motion":""}`;set("severity",severity.toUpperCase());set("body",String(data.body||"UNKNOWN BODY").toUpperCase());set("value",Number.isFinite(g)?g.toFixed(2):"—");set("detail",Number.isFinite(g)?`THRESHOLD ${threshold.toFixed(1)} G · DESCENT ENVELOPE REDUCED`:`THRESHOLD ${threshold.toFixed(1)} G`);document.getElementById("load-fill").style.setProperty("--load",`${Math.min(100,Math.max(0,(Number(data.ratio)||0)*50))}%`);}
  VoidCompassOverlay.startPolling({token, overlay, render, interval: 220});
})();
