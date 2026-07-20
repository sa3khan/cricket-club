// Westbridge CC — progressive enhancement.
// Everything here is additive: forms and links still work with JS disabled.
(function () {
  "use strict";

  /* ---------- Toasts ---------- */
  function toast(message, kind) {
    var wrap = document.getElementById("toasts");
    if (!wrap) {
      wrap = document.createElement("div");
      wrap.id = "toasts";
      document.body.appendChild(wrap);
    }
    var el = document.createElement("div");
    el.className = "toast toast-" + (kind || "success");
    el.textContent = message;
    wrap.appendChild(el);
    requestAnimationFrame(function () { el.classList.add("in"); });
    setTimeout(function () {
      el.classList.remove("in");
      setTimeout(function () { el.remove(); }, 300);
    }, 2600);
  }

  /* ---------- AJAX availability ---------- */
  var STATUS_LABEL = {
    available: "You're in ✅",
    maybe: "Marked as maybe",
    unavailable: "Marked unavailable",
  };

  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.classList.contains("statusform")) return;
    // Which button was clicked?
    var btn = form.querySelector("button:focus") ||
              document.activeElement;
    var status = btn && btn.name === "status" ? btn.value : null;
    if (!status) return; // let it submit normally

    e.preventDefault();
    var data = new URLSearchParams();
    data.append("status", status);

    form.classList.add("busy");
    fetch(form.action, {
      method: "POST",
      headers: {
        "X-Requested-With": "fetch",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: data.toString(),
      credentials: "same-origin",
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
      .then(function (j) {
        // Update the active chip.
        form.querySelectorAll(".chip").forEach(function (c) {
          c.classList.toggle("active", c.value === j.status);
        });
        // Update the fixture's "N in" counter, if present.
        var card = form.closest(".fixture");
        if (card) {
          var counter = card.querySelector(".incount");
          if (counter) {
            counter.textContent = j.in_count + " in";
            counter.classList.toggle("short", j.short);
            counter.classList.remove("pop");
            void counter.offsetWidth; // restart animation
            counter.classList.add("pop");
          }
        }
        toast(STATUS_LABEL[j.status] || "Availability updated");
      })
      .catch(function () {
        toast("Couldn't save — try again", "danger");
      })
      .finally(function () { form.classList.remove("busy"); });
  });

  /* ---------- Theme toggle ---------- */
  var root = document.documentElement;
  function effectiveTheme() {
    var t = root.getAttribute("data-theme");
    if (t) return t;
    return window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark" : "light";
  }
  function paintToggle(btn) {
    var dark = effectiveTheme() === "dark";
    btn.textContent = dark ? "☀️  Light mode" : "🌙  Dark mode";
    btn.setAttribute("aria-pressed", dark ? "true" : "false");
  }
  var toggleBtn = document.getElementById("themeToggle");
  if (toggleBtn) {
    paintToggle(toggleBtn);
    toggleBtn.addEventListener("click", function () {
      var next = effectiveTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      paintToggle(toggleBtn);
    });
  }

  /* ---------- Captain's matrix — pick the XI ---------- */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!form.classList.contains("pickform")) return;
    e.preventDefault();
    var row = form.closest("[data-row]");
    var uid = form.querySelector("[name=user_id]").value;
    var data = new URLSearchParams();
    data.append("user_id", uid);
    form.classList.add("busy");
    fetch(form.action, {
      method: "POST",
      headers: { "X-Requested-With": "fetch", "Content-Type": "application/x-www-form-urlencoded" },
      body: data.toString(),
      credentials: "same-origin",
    })
      .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
      .then(function (j) {
        if (row) row.classList.toggle("picked", j.selected);
        var btn = form.querySelector(".pick-btn");
        if (btn) btn.classList.toggle("on", j.selected);
        var counter = document.getElementById("xiCount");
        if (counter) {
          counter.textContent = j.count;
          counter.classList.remove("pop"); void counter.offsetWidth; counter.classList.add("pop");
        }
        var hint = document.getElementById("xiHint");
        if (hint) hint.textContent = j.full ? "Squad complete ✅" : "players selected";
        document.body.classList.toggle("xi-full", j.full);
      })
      .catch(function () { toast("Couldn't update selection", "danger"); })
      .finally(function () { form.classList.remove("busy"); });
  });

  /* ---------- Password reveal ---------- */
  document.querySelectorAll("[data-pw-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.parentNode.querySelector("input");
      if (!input) return;
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.textContent = show ? "Hide" : "Show";
      btn.setAttribute("aria-pressed", show ? "true" : "false");
      btn.setAttribute("aria-label", show ? "Hide password" : "Show password");
      input.focus();
    });
  });

  /* ---------- Account dropdown menu ---------- */
  document.querySelectorAll("[data-usermenu]").forEach(function (menu) {
    var trigger = menu.querySelector(".usermenu-trigger");
    var panel = menu.querySelector(".usermenu-panel");
    if (!trigger || !panel) return;
    function close() { panel.hidden = true; trigger.setAttribute("aria-expanded", "false"); }
    function open() { panel.hidden = false; trigger.setAttribute("aria-expanded", "true"); }
    trigger.addEventListener("click", function (e) {
      e.stopPropagation();
      panel.hidden ? open() : close();
    });
    // Keep the menu open when toggling the theme; close on any other item.
    panel.addEventListener("click", function (e) {
      if (!e.target.closest("#themeToggle")) close();
    });
    document.addEventListener("click", function (e) {
      if (!menu.contains(e.target)) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  });

  /* ---------- Role → team field toggle (player edit) ---------- */
  (function () {
    var roles = document.querySelectorAll("[data-role]");
    var teamField = document.querySelector("[data-team-field]");
    if (!roles.length || !teamField) return;
    function sync() {
      var picked = document.querySelector("[data-role]:checked");
      teamField.style.display =
        picked && picked.value === "organizer" ? "none" : "";
    }
    roles.forEach(function (r) { r.addEventListener("change", sync); });
    sync();
  })();

  /* ---------- Interactive tabs ---------- */
  document.querySelectorAll("[data-tabs]").forEach(function (nav) {
    var links = nav.querySelectorAll("a[data-tab]");
    function activate(name, push) {
      links.forEach(function (l) {
        l.classList.toggle("active", l.dataset.tab === name);
      });
      document.querySelectorAll("[data-panel]").forEach(function (p) {
        p.hidden = p.dataset.panel !== name;
      });
      if (push && history.replaceState) {
        history.replaceState(null, "", "#" + name);
      }
    }
    links.forEach(function (l) {
      l.addEventListener("click", function (e) {
        e.preventDefault();
        activate(l.dataset.tab, true);
      });
    });
    var initial = (location.hash || "").replace("#", "");
    var names = Array.prototype.map.call(links, function (l) { return l.dataset.tab; });
    activate(names.indexOf(initial) >= 0 ? initial : names[0], false);
  });

  /* ---------- Reveal on scroll ---------- */
  var reveals = document.querySelectorAll(".reveal");
  if (reveals.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("in");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.08 });
    reveals.forEach(function (el, i) {
      el.style.transitionDelay = Math.min(i * 40, 240) + "ms";
      io.observe(el);
    });
  } else {
    reveals.forEach(function (el) { el.classList.add("in"); });
  }

  /* ---------- Count-up numbers ---------- */
  function countUp(el) {
    var target = parseFloat(el.dataset.count);
    var suffix = el.dataset.suffix || "";
    var dur = 900, start = performance.now();
    function tick(now) {
      var t = Math.min((now - start) / dur, 1);
      var eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased) + suffix;
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }
  document.querySelectorAll("[data-count]").forEach(countUp);

  /* ---------- Animate bar widths in ---------- */
  window.addEventListener("load", function () {
    document.querySelectorAll(".bar-fill[data-w]").forEach(function (b) {
      requestAnimationFrame(function () { b.style.width = b.dataset.w + "%"; });
    });
  });
})();
