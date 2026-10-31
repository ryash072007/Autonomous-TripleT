import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import "./console2.css";
import "./console3.css";
import "./console4.css";
import "./mobile.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Layout audit helper (only with #...dbg in the URL): reports horizontal overflow and the elements that cause it.
if (window.location.hash.includes("dbg")) {
  window.addEventListener("load", () => window.setTimeout(() => {
    const w = window.innerWidth;
    const clipped = (el: Element) => {
      for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        const o = getComputedStyle(p).overflowX;
        if (o === "auto" || o === "scroll" || o === "hidden") return true;
      }
      return false;
    };
    const bad = Array.from(document.querySelectorAll("body *"))
      .filter((e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.right > w + 1 && getComputedStyle(e).position !== "fixed" && !clipped(e); })
      .slice(0, 10).map((e) => `${e.tagName}.${(e as HTMLElement).className || ""}:${Math.round(e.getBoundingClientRect().right)}`);
    document.body.setAttribute("data-dbg", JSON.stringify({ iw: w, sw: document.documentElement.scrollWidth, bad }));
  }, 7000));
}

// Perf probe (only with #...fps in the URL): frames per second and long-task time over 5 s, after 4 s of settling.
if (window.location.hash.includes("fps")) {
  let long = 0, nlong = 0;
  try { new PerformanceObserver((l) => l.getEntries().forEach((e) => { long += e.duration; nlong++; })).observe({ entryTypes: ["longtask"] }); } catch { /* unsupported */ }
  window.setTimeout(() => {
    let n = 0; const l0 = long, c0 = nlong; const t0 = performance.now();
    const f = () => { n++; if (performance.now() - t0 < 5000) requestAnimationFrame(f); else
      { const r = JSON.stringify({ fps: +(n / 5).toFixed(1), longMs: Math.round(long - l0), longN: nlong - c0 }); document.body.setAttribute("data-fps", r); fetch("http://127.0.0.1:8099/?r=" + encodeURIComponent(r), { mode: "no-cors" }).catch(() => {}); } };
    requestAnimationFrame(f);
  }, 4000);
}
