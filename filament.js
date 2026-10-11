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

  // resonance: Rudi's weekly reading, from /resonance.json. Each entry's date is a
  // Sunday; it appears at 6pm Eastern that evening, for everyone. The homepage shows the
  // title and opening line for 9 days, so a missed week shows nothing there;
  // /resonance/ always shows the most recent reading in full.
  const res = document.getElementById("resonance");
  if (res) {
    // the real moon today: days since a known new moon, over the synodic month
    const SYNODIC = 29.530588853, NEW = Date.UTC(2000, 0, 6, 18, 14);
    const p = ((((Date.now() - NEW) / 864e5) % SYNODIC) + SYNODIC) % SYNODIC / SYNODIC;
    const r = 6.5, rx = Math.abs(Math.cos(2 * Math.PI * p)) * r;
    const waxing = p < .5, gibbous = p > .25 && p < .75;
    // lit limb on the right while waxing (northern sky), then the terminator back up
    const limb = `M0,${-r}A${r},${r} 0 0 ${waxing ? 1 : 0} 0,${r}`;
    const term = `A${rx},${r} 0 0 ${waxing === gibbous ? 1 : 0} 0,${-r}Z`;
    const names = [[.03, "new"], [.22, "waxing crescent"], [.28, "first quarter"], [.47, "waxing gibbous"],
      [.53, "full"], [.72, "waning gibbous"], [.78, "last quarter"], [.97, "waning crescent"], [1, "new"]];
    const moon = res.querySelector(".moon");
    moon.querySelector("path").setAttribute("d", p < .03 || p > .97 ? "" : limb + term);
    moon.setAttribute("aria-label", names.find(([t]) => p < t)[1] + " moon");

    // a paragraph of plain text: *words* in italics, a single line break kept as a break
    const para = (text) => {
      const el = document.createElement("p");
      text.trim().split("\n").forEach((line, n) => {
        if (n) el.append(document.createElement("br"));
        line.trim().split(/\*([^*]+)\*/).forEach((bit, i) => {
          if (!bit) return;
          if (i % 2) { const em = document.createElement("em"); em.textContent = bit; el.append(em); }
          else el.append(bit);
        });
      });
      return el;
    };
    // Times are Eastern (Rudi's clock), so a reading signs on at the same moment for
    // everyone: "2026-10-11" = 6pm that day in New York, "2026-10-10T12:00" = noon there.
    const ZONE = "America/New_York";
    const eastern = (s) => {
      const [d, t = "18:00"] = String(s).split("T");
      const [y, m, dd] = d.split("-").map(Number);
      const [hh, mm = 0, ss = 0] = t.split(":").map(Number);
      const guess = Date.UTC(y, m - 1, dd, hh, mm, ss);
      try {
        const parts = new Intl.DateTimeFormat("en-US", { timeZone: ZONE, hourCycle: "h23",
          year: "numeric", month: "numeric", day: "numeric", hour: "numeric", minute: "numeric", second: "numeric" })
          .formatToParts(guess);
        const v = (k) => Number(parts.find((x) => x.type === k).value);
        return guess - (Date.UTC(v("year"), v("month") - 1, v("day"), v("hour"), v("minute"), v("second")) - guess);
      } catch { return new Date(y, m - 1, dd, hh, mm, ss).getTime(); }
    };
    const day = (t) => {
      const o = { weekday: "long", day: "numeric", month: "long" };
      let s;
      try { s = new Date(t).toLocaleDateString("en-US", { ...o, timeZone: ZONE }); }
      catch { s = new Date(t).toLocaleDateString("en-US", o); }
      return s.toLowerCase().replace(",", "");
    };
    const full = res.dataset.view === "full";

    fetch("/resonance.json", { cache: "no-cache" }).then((x) => x.json()).then((list) => {
      const now = Date.now();
      // "live" (optional, e.g. "2026-10-03T12:00") posts a reading early; its date stays its Sunday
      const published = list
        .map((e) => ({ ...e, at: eastern(e.date) }))
        .map((e) => ({ ...e, from: e.live ? eastern(e.live) : e.at }))
        .filter((e) => e.text && e.from <= now)
        .sort((a, b) => b.at - a.at);
      // the full page can show any earlier reading: /resonance/?r=2026-10-04
      const asked = full && new URLSearchParams(location.search).get("r");
      const entry = (asked && published.find((e) => e.date === asked))
        || published.find((e) => full || now < e.at + 9 * 864e5);
      if (!entry) return;
      const paras = String(entry.text).split(/\n\s*\n/);
      res.querySelector(".title").textContent = entry.title || "";
      const when = res.querySelector(".when");
      if (when) when.textContent = day(entry.at);
      const box = res.querySelector(".reading");
      (full ? paras : paras.slice(0, 1)).forEach((t) => box.append(para(t)));
      res.hidden = false;
      const empty = document.getElementById("resonance-empty");
      if (empty) empty.hidden = true;

      // the archive: every other published reading, newest first, split around this one
      const archive = document.getElementById("resonance-archive");
      if (!archive || published.length < 2) return;
      archive.replaceChildren();
      [["later", published.filter((e) => e.at > entry.at)],
       ["earlier", published.filter((e) => e.at < entry.at)]].forEach(([label, group]) => {
        if (!group.length) return;
        const head = document.createElement("p");
        head.className = "mono";
        head.textContent = label;
        const ul = document.createElement("ul");
        group.forEach((e) => {
          const li = document.createElement("li"), a = document.createElement("a");
          a.href = e === published[0] ? "/resonance/" : "/resonance/?r=" + e.date;
          a.textContent = e.title || e.date;
          const d = document.createElement("span");
          d.className = "mono";
          d.textContent = day(e.at);
          li.append(a, d);
          ul.append(li);
        });
        archive.append(head, ul);
      });
      archive.hidden = false;
    }).catch(() => {});
  }

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
