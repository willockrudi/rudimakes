// Filament: the small things the room does. Each page sets data-theme
// itself in <head> before paint; this file runs after.
(() => {
  const root = document.documentElement;
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
  };

  // lights on / lights off
  const sw = document.querySelector(".lights");
  if (sw) {
    const sync = () => sw.setAttribute("aria-pressed", root.dataset.theme === "light" ? "true" : "false");
    sync();
    sw.addEventListener("click", () => {
      root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
      store.set("filament-lights", root.dataset.theme);
      sync();
    });
  }

  // a breath of static when moving between pages of the site, once
  if (!still && document.referrer) {
    try {
      if (new URL(document.referrer).origin === location.origin) {
        root.classList.add("static");
        setTimeout(() => root.classList.remove("static"), 320);
      }
    } catch {}
  }

  // today's date, like the top of a station log
  document.querySelectorAll("[data-today]").forEach((el) => {
    el.textContent = new Date()
      .toLocaleDateString("en-US", { weekday: "long", day: "numeric", month: "long" })
      .toLowerCase().replace(",", "");
  });

  // channels come in one at a time
  const items = document.querySelectorAll(".reveal");
  if (still || !("IntersectionObserver" in window)) {
    items.forEach((el) => el.classList.add("in"));
  } else {
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { rootMargin: "0px 0px -12% 0px" });
    items.forEach((el) => io.observe(el));
  }

  // the site is a television: type a channel number to tune. Never announced.
  const dial = { "01": "/tbx/", "02": "/hyperworld/", "99": "/99/" };
  let digits = "", osd = null, wait = 0;
  const show = (num, note) => {
    if (!osd) { osd = document.createElement("div"); osd.className = "osd"; osd.setAttribute("aria-live", "polite"); document.body.append(osd); }
    osd.innerHTML = num + (note ? "<small>" + note + "</small>" : "");
    osd.hidden = false;
  };
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || !/^[0-9]$/.test(e.key)) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable) return;
    digits = (digits + e.key).slice(-2);
    clearTimeout(wait);
    show(digits.padEnd(2, "-"));
    if (digits.length < 2) { wait = setTimeout(() => { digits = ""; osd.hidden = true; }, 2200); return; }
    const num = digits, to = dial[num];
    digits = "";
    if (to && location.pathname !== to) {
      wait = setTimeout(() => { location.href = to; }, 650);
    } else {
      show(num, to ? "" : "no signal");
      wait = setTimeout(() => { osd.hidden = true; }, 2200);
    }
  });

  // left open late at night, the tab signs off
  const title = document.title;
  document.addEventListener("visibilitychange", () => {
    const h = new Date().getHours();
    document.title = document.hidden && (h >= 23 || h < 5) ? "signing off" : title;
  });
})();
