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
