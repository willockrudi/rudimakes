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

  // glowworm: the founding members, from /glowworm.json so the number can be edited
  // and pushed without touching the page.
  //
  // founding and goal are the same number now, because founding means you joined
  // before it existed and goal is when it starts existing. It is a milestone, not
  // a cap: anyone can still join after, so the counter has to turn around rather
  // than sit at zero looking shut. Below it, count down:
  // "93 founding places left" is a reason to act today, where "7 of 100" only
  // advertises how empty it is. Above it, count up, because by then the number is
  // its own argument.
  // someone who just bought one of the twenty lands on glowworm with ?from=twenty
  const thanks = document.getElementById("gw-thanks");
  if (thanks && new URLSearchParams(location.search).get("from") === "twenty") thanks.hidden = false;

  const left = document.getElementById("gw-left");
  if (left) {
    const count = document.getElementById("gw-count");
    const fill = document.getElementById("gw-fill");
    const mark = document.getElementById("gw-mark");
    fetch("/glowworm.json", { cache: "no-cache" }).then((x) => x.json()).then((g) => {
      const members = Math.max(0, g.members ?? 0);
      const founding = g.founding ?? 100, goal = g.goal ?? 250;

      // There is no cap. The track measures the goal until the goal is passed, and
      // the members after that, so the bar never pins at full and quietly stops
      // telling the story. Past the goal the mark shows where it was.
      const max = Math.max(goal, members);
      count.textContent = members + " of " + goal;
      count.hidden = false;
      if (members > goal) {
        mark.style.left = (goal / max * 100) + "%";
        mark.hidden = false;
      }

      // The second line is the scarce thing, while it is still scarce. After that
      // the count above is the whole story and a second number is just noise.
      const places = founding - members;
      if (places > 0) {
        left.textContent = places + (places === 1 ? " founding place left" : " founding places left");
        left.hidden = false;
      }

      // One frame late so the width animates from zero: the bar filling is the
      // point, it is what makes signing up feel like adding to something.
      const width = members ? Math.max(members / max * 100, 1.5) : 0;
      requestAnimationFrame(() => { fill.style.width = width + "%"; });
    }).catch(() => {});
  }

  // twenty: the paper cuts on the homepage, from /twenty.json so a scan can be added
  // or a piece marked sold without touching the page. A piece is one of three things:
  // not cut yet (a numbered empty square), for sale (its picture, linked to its own
  // Stripe link), or sold (its picture, dimmed, no link). Nothing shows until at
  // least one piece has a picture.
  const twenty = document.getElementById("twenty");
  if (twenty) {
    fetch("/twenty.json", { cache: "no-cache" }).then((x) => x.json()).then((t) => {
      const pieces = t.pieces || [];
      if (!pieces.some((p) => p.img)) return;
      const grid = document.getElementById("twenty-grid");
      const el = (tag, cls, text) => {
        const e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text != null) e.textContent = text;
        return e;
      };
      pieces.forEach((p) => {
        const num = String(p.n).padStart(2, "0");
        const open = p.img && !p.sold && String(p.link || "").startsWith("https://");
        const li = el("li", p.sold ? "sold" : p.img ? "" : "blank");
        const box = el(open ? "a" : "div", "piece");
        if (open) { box.href = p.link; box.setAttribute("aria-label", "No. " + num + ", buy"); }
        const pic = el("div", "pic");
        if (p.img) {
          const img = el("img");
          img.src = "/" + String(p.img).replace(/^\//, "");
          img.alt = p.alt || "Paper cut no. " + num;
          img.loading = "lazy";
          pic.append(img);
        }
        const cap = el("div", "cap mono");
        cap.append(el("span", "", num), el("span", "", p.sold ? "sold" : open ? "$" + t.price : ""));
        box.append(pic, cap);
        li.append(box);
        grid.append(li);
      });
      const left = pieces.filter((p) => !p.sold).length;
      document.getElementById("twenty-left").textContent = left + " of " + pieces.length + " left";
      document.getElementById("twenty-price").textContent = "$" + t.price + " each, shipped in the US.";
      twenty.hidden = false;
    }).catch(() => {});
  }

  // Anything waiting on a payment link stays switched off until a real one is pasted
  // into data-link. A join button that 404s costs more than one that admits it isn't
  // open, and this way the page can be live before Stripe is.
  document.querySelectorAll("[data-link]").forEach((el) => {
    const to = el.dataset.link || "";
    if (to.startsWith("https://")) { el.href = to; return; }
    el.removeAttribute("href");
    el.setAttribute("aria-disabled", "true");
    if (el.classList.contains("join")) el.textContent = "not open yet";
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
