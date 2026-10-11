(function () {
  "use strict";

  // Everything below builds DOM with textContent. Log lines and model output are untrusted.
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var SVGNS = "http://www.w3.org/2000/svg";
  var STATUS = {
    verified: { label: "Backed by the log", cls: "s-ok" },
    unchecked: { label: "Nothing to check", cls: "s-none" },
    unsupported: { label: "Lines do not back it", cls: "s-warn" },
    invalid: { label: "Broken citation", cls: "s-bad" }
  };
  var ORDER = ["verified", "unchecked", "unsupported", "invalid"];
  var PATHS = {
    verified: "M4 8.5l2.6 2.6L12 5.6",
    unchecked: "M4.5 8h7",
    unsupported: "M8 4.2v4.6M8 11.3v.1",
    invalid: "M4.8 4.8l6.4 6.4M11.2 4.8l-6.4 6.4"
  };
  var KIND = { headline: "Headline", finding: "Finding", action: "Action" };

  var state = { runId: DATA.default, sel: null, lastLine: null };
  var $ = function (id) { return document.getElementById(id); };
  var tip = $("tip");

  function el(tag, props) {
    var node = document.createElement(tag);
    if (props) {
      Object.keys(props).forEach(function (k) {
        var v = props[k];
        if (v === null || v === undefined || v === false) return;
        if (k === "class") node.className = v;
        else if (k === "text") node.textContent = v;
        else if (k.slice(0, 2) === "on") node.addEventListener(k.slice(2), v);
        else node.setAttribute(k, v === true ? "" : v);
      });
    }
    for (var i = 2; i < arguments.length; i++) {
      var kid = arguments[i];
      if (kid === null || kid === undefined || kid === false) continue;
      if (Array.isArray(kid)) kid.forEach(function (k) { if (k) node.append(k); });
      else node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return node;
  }

  function glyph(status, size) {
    var svg = document.createElementNS(SVGNS, "svg");
    svg.setAttribute("viewBox", "0 0 16 16");
    svg.setAttribute("width", size || 14);
    svg.setAttribute("height", size || 14);
    svg.setAttribute("aria-hidden", "true");
    var p = document.createElementNS(SVGNS, "path");
    p.setAttribute("d", PATHS[status]);
    p.setAttribute("fill", "none");
    p.setAttribute("stroke", "currentColor");
    p.setAttribute("stroke-width", "1.9");
    p.setAttribute("stroke-linecap", "round");
    p.setAttribute("stroke-linejoin", "round");
    svg.append(p);
    return svg;
  }
  function dot(status) {
    return el("span", { class: "dot " + STATUS[status].cls }, glyph(status));
  }

  // Backticks in claim text mark names, addresses and commands.
  function rich(text) {
    var frag = document.createDocumentFragment();
    String(text).split("`").forEach(function (part, i) {
      if (!part) return;
      frag.append(i % 2 ? el("code", { text: part }) : document.createTextNode(part));
    });
    return frag;
  }

  function ranges(nums) {
    var sorted = Array.from(new Set(nums)).sort(function (a, b) { return a - b; });
    var out = [];
    sorted.forEach(function (n) {
      var last = out[out.length - 1];
      if (last && n === last[1] + 1) last[1] = n;
      else out.push([n, n]);
    });
    return out;
  }
  function fmt(r) { return r[0] === r[1] ? "L" + r[0] : "L" + r[0] + "–L" + r[1]; }
  function fmtAll(nums) { return ranges(nums).map(fmt).join(", "); }

  function currentRun() {
    return DATA.runs.filter(function (r) { return r.id === state.runId; })[0];
  }
  function facts(run) { return run.claims.filter(function (c) { return c.kind !== "action"; }); }
  function claimById(run, id) { return run.claims.filter(function (c) { return c.id === id; })[0]; }

  // ------------------------------------------------------------ tooltip
  function showTip(target, title, rows) {
    tip.replaceChildren(el("strong", { text: title }));
    (rows || []).forEach(function (r) { tip.append(el("div", { text: r })); });
    tip.classList.add("on");
    var r = target.getBoundingClientRect();
    var x = Math.min(Math.max(8, r.left), window.innerWidth - tip.offsetWidth - 8);
    var y = r.bottom + 8;
    if (y + tip.offsetHeight > window.innerHeight - 8) y = Math.max(8, r.top - tip.offsetHeight - 8);
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }
  function hideTip() { tip.classList.remove("on"); }
  function tipOn(node, title, rows) {
    node.addEventListener("pointerenter", function () { showTip(node, title, rows); });
    node.addEventListener("focus", function () { showTip(node, title, rows); });
    node.addEventListener("pointerleave", hideTip);
    node.addEventListener("blur", hideTip);
  }
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideTip(); });
  window.addEventListener("scroll", hideTip, true);

  // ------------------------------------------------------------ run tabs
  function renderTabs() {
    var host = $("tabs");
    host.replaceChildren();
    DATA.runs.forEach(function (run, idx) {
      var f = facts(run);
      var s = run.score;
      var mini = el("div", { class: "mini", "aria-hidden": "true" });
      f.forEach(function (c) { mini.append(el("span", { class: STATUS[c.verdict.status].cls })); });
      var summary = run.parse_error
        ? "Reply unreadable"
        : s.facts + " claims, " + s.grounded + " backed";
      var tab = el("button", {
        class: "tab", type: "button", role: "tab", id: "tab-" + run.id,
        "aria-selected": String(run.id === state.runId),
        tabindex: run.id === state.runId ? "0" : "-1",
        onclick: function () { selectRun(run.id); },
        onkeydown: function (e) {
          var step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
          if (!step) return;
          e.preventDefault();
          var next = DATA.runs[(idx + step + DATA.runs.length) % DATA.runs.length];
          selectRun(next.id);
          $("tab-" + next.id).focus();
        }
      },
        el("span", { class: "tab-head" },
          el("span", { class: "tab-name", text: run.label }),
          el("span", { class: "tab-src", text: run.source === "scripted" ? "Scripted demo" : "Local model" })),
        mini,
        el("span", { class: "tab-foot" },
          el("span", { text: summary }),
          s.events_total ? el("span", { text: s.events_found + " of " + s.events_total + " events" }) : null));
      host.append(tab);
    });
  }

  function selectRun(id) {
    state.runId = id;
    state.sel = null;
    state.lastLine = null;
    renderAll();
  }

  // ------------------------------------------------------------ hero, strip, legend
  function renderHero(run) {
    $("hero-text").textContent = run.hero;
    var meta = $("runmeta");
    meta.replaceChildren();
    if (run.source !== "scripted") {
      meta.append(el("span", { text: "Model " + run.model }));
      if (run.prompt_version) meta.append(el("span", { text: "Prompt " + run.prompt_version }));
      if (run.elapsed_s) meta.append(el("span", { text: run.elapsed_s.toFixed(1) + " s" }));
      if (run.options && run.options.temperature !== undefined) {
        meta.append(el("span", { text: "Temperature " + run.options.temperature }));
        meta.append(el("span", { text: "Seed " + run.options.seed }));
      }
      meta.append(el("span", { text: "Run " + run.created.slice(0, 10) }));
    }
    var note = $("note");
    if (run.source === "scripted") {
      note.hidden = false;
      note.textContent = run.note;
    } else if (run.parse_error) {
      note.hidden = false;
      note.textContent = run.parse_error;
    } else {
      note.hidden = true;
    }
  }

  function renderStrip(run) {
    var strip = $("strip");
    strip.replaceChildren();
    facts(run).forEach(function (c) {
      var st = STATUS[c.verdict.status];
      var seg = el("button", {
        class: "seg " + st.cls, type: "button", "data-claim": c.id,
        "aria-pressed": "false",
        "aria-label": c.id + ", " + st.label + ". " + c.text.replace(/`/g, ""),
        onclick: function () {
          pickClaim(c.id, true);
          var row = $("claim-" + c.id);
          if (row) row.scrollIntoView({ block: "nearest" });
        }
      }, el("span", { class: "cid", text: c.id }), glyph(c.verdict.status, 16));
      tipOn(seg, c.id + ": " + st.label, [c.text.replace(/`/g, "")]);
      strip.append(seg);
    });
    var legend = $("legend");
    legend.replaceChildren();
    ORDER.forEach(function (k) {
      legend.append(el("li", null, dot(k), el("span", null, STATUS[k].label + " ", el("b", { text: String(run.score.by_status[k]) }))));
    });
  }

  // ------------------------------------------------------------ claims
  function claimRow(run, c) {
    var v = c.verdict;
    var st = STATUS[v.status];
    var ranged = ranges(v.cited);
    var chips = ranged.map(function (r) {
      return el("button", {
        class: "chip", type: "button",
        "aria-label": "Show " + fmt(r) + " in the log",
        onclick: function () { pickClaim(c.id, false); scrollLog(r[0]); }
      }, fmt(r));
    });
    v.out_of_range.forEach(function (n) {
      chips.push(el("span", { class: "chip gone", title: "This line is not in the log", text: "L" + n }));
    });
    var why = v.reasons.map(function (r) { return el("li", { class: st.cls }, rich(r.message)); });
    if (c.over_read) {
      why.push(el("li", { class: "pad" }, "Rated " + c.severity + ", but every line it cites is routine activity."));
    }
    if (v.padding.length && v.status !== "invalid") {
      why.push(el("li", { class: "pad" }, "Cited but never mentioned in the claim: " + fmtAll(v.padding) + "."));
    }
    return el("li", { class: "claim " + st.cls, id: "claim-" + c.id, "data-claim": c.id },
      dot(v.status),
      el("div", null,
        el("button", {
          class: "pick", type: "button", "aria-pressed": "false",
          onclick: function () { pickClaim(c.id, true); }
        },
          el("span", { class: "meta" },
            el("span", { class: "cid", text: c.id }),
            el("span", { text: KIND[c.kind] }),
            el("span", { class: "sev " + c.severity }, el("i"), c.severity),
            el("span", { class: "sr", text: "Result: " + st.label })),
          el("span", { class: "ctext" }, rich(c.text))),
        el("div", { class: "cites" }, chips),
        why.length ? el("ul", { class: "why" }, why) : null));
  }

  function renderClaims(run) {
    var host = $("claims");
    host.replaceChildren();
    if (!run.claims.length) {
      host.append(el("p", { text: run.parse_error || "This run made no claims." }));
      return;
    }
    [["headline", "Headline"], ["finding", "Findings"], ["action", "Recommended actions"]].forEach(function (g) {
      var rows = run.claims.filter(function (c) { return c.kind === g[0]; });
      if (!rows.length) return;
      host.append(el("h3", { text: g[1] }));
      if (g[0] === "action") {
        var ok = run.score.action_status.verified;
        host.append(el("p", { class: "sub", text: ok + " of " + rows.length + (ok === 1 ? " is backed by the lines it cites." : " are backed by the lines they cite.") }));
      }
      host.append(el("ol", { class: "claims" }, rows.map(function (c) { return claimRow(run, c); })));
    });
  }

  // ------------------------------------------------------------ log
  var citeMap = {};
  function buildCiteMap(run) {
    citeMap = {};
    run.claims.forEach(function (c) {
      c.verdict.cited.forEach(function (n) { (citeMap[n] = citeMap[n] || []).push(c); });
    });
  }

  function fillText(node, text, tokens) {
    node.replaceChildren();
    if (!tokens.length || !text) { node.append(document.createTextNode(text)); return; }
    var spans = [];
    tokens.slice().sort(function (a, b) { return b.length - a.length; }).forEach(function (tok) {
      var from = 0, at;
      while ((at = text.indexOf(tok, from)) !== -1) {
        var end = at + tok.length;
        if (!spans.some(function (s) { return at < s[1] && end > s[0]; })) spans.push([at, end]);
        from = end;
      }
    });
    spans.sort(function (a, b) { return a[0] - b[0]; });
    var pos = 0;
    spans.forEach(function (s) {
      if (s[0] > pos) node.append(document.createTextNode(text.slice(pos, s[0])));
      node.append(el("mark", { text: text.slice(s[0], s[1]) }));
      pos = s[1];
    });
    if (pos < text.length) node.append(document.createTextNode(text.slice(pos)));
  }

  function renderLog(run) {
    buildCiteMap(run);
    $("logname").replaceChildren(DATA.log.name, el("span", { text: DATA.log.lines.length + " lines" }));
    var body = $("logbody");
    body.replaceChildren();
    DATA.log.lines.forEach(function (line) {
      var cites = citeMap[line.no] || [];
      var gut = el("span", { class: "gut" });
      var shown = cites.length > 4 ? 3 : cites.length;
      cites.slice(0, shown).forEach(function (c) {
        gut.append(el("i", { class: "m " + STATUS[c.verdict.status].cls }));
      });
      if (cites.length > shown) gut.append(el("span", { class: "more", text: "+" + (cites.length - shown) }));
      if (cites.length) {
        tipOn(gut, "L" + line.no + " is cited by " + cites.length + (cites.length === 1 ? " claim" : " claims"),
          cites.map(function (c) { return c.id + ": " + STATUS[c.verdict.status].label; }));
      }
      var row = el("div", {
        class: "ln", id: "L" + line.no, "data-no": line.no,
        onclick: function () { lineInfo(line.no); }
      },
        gut,
        el("span", { class: "no", text: String(line.no) }),
        el("span", { class: "txt" },
          el("span", { class: "head" }), document.createTextNode(" "),
          el("span", { class: "proc" }), el("span", { class: "msg" })),
        el("span", { class: "tag", title: line.events.map(eventTitle).join("; "), text: line.events.join(" ") }));
      fillText(row.querySelector(".head"), line.head, []);
      fillText(row.querySelector(".proc"), line.proc, []);
      fillText(row.querySelector(".msg"), line.msg, []);
      body.append(row);
    });
  }

  function eventTitle(id) {
    var e = DATA.events.filter(function (x) { return x.id === id; })[0];
    return e ? id + ": " + e.title : id;
  }

  function scrollLog(no) {
    var body = $("logbody");
    var row = $("L" + no);
    if (!row) return;
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    body.scrollTo({ top: Math.max(0, row.offsetTop - 56), behavior: reduce ? "auto" : "smooth" });
  }

  function lineInfo(no) {
    state.lastLine = no;
    var run = currentRun();
    var cites = citeMap[no] || [];
    var foot = $("logfoot");
    foot.replaceChildren();
    var line = DATA.log.lines[no - 1];
    foot.append("L" + no + (cites.length ? " is cited by " : " is not cited by any claim."));
    cites.forEach(function (c, i) {
      foot.append(el("button", { type: "button", onclick: function () { pickClaim(c.id, true); } }, c.id));
      if (i < cites.length - 1) foot.append(" ");
    });
    if (line.events.length) foot.append(" Planted: " + line.events.map(eventTitle).join("; ") + ".");
    document.querySelectorAll(".ln.is-last").forEach(function (n) { n.classList.remove("is-last"); });
    var row = $("L" + no);
    if (row) row.classList.add("is-last");
    void run;
  }

  // ------------------------------------------------------------ selection
  function pickClaim(id, scroll) {
    state.sel = state.sel && state.sel.kind === "claim" && state.sel.id === id && scroll ? null : { kind: "claim", id: id };
    applySelection();
    if (state.sel && scroll) {
      var c = claimById(currentRun(), id);
      if (c.verdict.cited.length) scrollLog(Math.min.apply(null, c.verdict.cited));
    }
  }
  function pickEvent(id) {
    state.sel = state.sel && state.sel.kind === "event" && state.sel.id === id ? null : { kind: "event", id: id };
    applySelection();
    if (state.sel) {
      var e = DATA.events.filter(function (x) { return x.id === id; })[0];
      scrollLog(e.lines[0]);
    }
  }

  function applySelection() {
    var run = currentRun();
    var lines = {}, tokens = {};
    if (state.sel && state.sel.kind === "claim") {
      var c = claimById(run, state.sel.id);
      c.verdict.cited.forEach(function (n) { lines[n] = true; });
      c.verdict.tokens.forEach(function (t) {
        if (!t.found) return;
        t.lines.forEach(function (n) { (tokens[n] = tokens[n] || []).push(t.text); });
      });
    } else if (state.sel && state.sel.kind === "event") {
      DATA.events.filter(function (x) { return x.id === state.sel.id; })[0].lines.forEach(function (n) { lines[n] = true; });
    }
    document.querySelectorAll(".ln").forEach(function (row) {
      var no = Number(row.dataset.no);
      row.classList.toggle("is-cited", !!lines[no]);
      var want = (tokens[no] || []).join("\u0000");
      if (row.dataset.tok !== want) {
        row.dataset.tok = want;
        var line = DATA.log.lines[no - 1];
        var t = tokens[no] || [];
        fillText(row.querySelector(".head"), line.head, t);
        fillText(row.querySelector(".proc"), line.proc, t);
        fillText(row.querySelector(".msg"), line.msg, t);
      }
    });
    document.querySelectorAll(".claim").forEach(function (row) {
      var on = !!state.sel && state.sel.kind === "claim" && state.sel.id === row.dataset.claim;
      row.classList.toggle("is-sel", on);
      row.querySelector(".pick").setAttribute("aria-pressed", String(on));
    });
    document.querySelectorAll(".seg").forEach(function (seg) {
      seg.setAttribute("aria-pressed", String(!!state.sel && state.sel.kind === "claim" && state.sel.id === seg.dataset.claim));
    });
    document.querySelectorAll("tr.pickrow").forEach(function (tr) {
      tr.classList.toggle("is-sel", !!state.sel && state.sel.kind === "event" && state.sel.id === tr.dataset.event);
    });
  }

  // ------------------------------------------------------------ planted events
  function renderEvents(run) {
    var sec = $("eventsec");
    if (!DATA.events.length) { sec.hidden = true; return; }
    sec.hidden = false;
    var t = $("events");
    t.replaceChildren(
      el("thead", null, el("tr", null,
        el("th", { text: "Event" }), el("th", { text: "What was planted" }),
        el("th", { text: "Lines" }), el("th", { text: "Result" }))));
    var body = el("tbody");
    DATA.events.forEach(function (ev) {
      var res = run.score.events.filter(function (x) { return x.id === ev.id; })[0];
      var found = res && res.found;
      body.append(el("tr", {
        class: "pickrow", "data-event": ev.id, tabindex: "0",
        onclick: function () { pickEvent(ev.id); },
        onkeydown: function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pickEvent(ev.id); } }
      },
        el("td", { class: "mono", text: ev.id }),
        el("td", { text: ev.title }),
        el("td", { class: "mono", text: fmtAll(ev.lines) }),
        el("td", null, el("span", { class: "found" },
          dot(found ? "verified" : "unsupported"),
          el("span", { text: found ? "Found by " + res.by.join(", ") : "Not found" })))));
    });
    t.append(body);
  }

  // ------------------------------------------------------------ tables
  function renderClaimTable(run) {
    var t = $("claimtable");
    t.replaceChildren(el("thead", null, el("tr", null,
      ["Claim", "Kind", "Severity", "Result", "Lines", "Why"].map(function (h) { return el("th", { text: h }); }))));
    var body = el("tbody");
    run.claims.forEach(function (c) {
      var v = c.verdict;
      body.append(el("tr", null,
        el("td", { class: "mono", text: c.id }),
        el("td", { text: KIND[c.kind] }),
        el("td", { text: c.severity }),
        el("td", { text: STATUS[v.status].label }),
        el("td", { class: "mono", text: fmtAll(v.cited.concat(v.out_of_range)) }),
        el("td", { text: v.reasons.map(function (r) { return r.message.replace(/`/g, ""); }).join(" ") })));
    });
    t.append(body);
  }
  function renderRuleTable() {
    var t = $("ruletable");
    t.replaceChildren(el("thead", null, el("tr", null,
      ["Rule", "If it fails", "What it checks", "What it cannot catch"].map(function (h) { return el("th", { text: h }); }))));
    var body = el("tbody");
    DATA.rules.forEach(function (r) {
      body.append(el("tr", null,
        el("td", { class: "mono", text: r.code }),
        el("td", { text: STATUS[r.outcome].label }),
        el("td", { text: r.checks.replace(/`/g, "") }),
        el("td", { text: r.misses.replace(/`/g, "") })));
    });
    t.append(body);
  }

  // ------------------------------------------------------------ theme
  function effectiveTheme() {
    return document.documentElement.dataset.theme ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  function themeLabel() { $("theme").textContent = effectiveTheme() === "dark" ? "Use light theme" : "Use dark theme"; }
  try {
    var saved = localStorage.getItem("citedlog-theme");
    if (saved === "light" || saved === "dark") document.documentElement.dataset.theme = saved;
  } catch (e) { /* storage can be blocked; the page works without it */ }
  $("theme").addEventListener("click", function () {
    var next = effectiveTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("citedlog-theme", next); } catch (e) { /* ignore */ }
    themeLabel();
  });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", themeLabel);
  themeLabel();

  $("keytoggle").addEventListener("change", function (e) {
    $("log").classList.toggle("show-key", e.target.checked);
  });

  // ------------------------------------------------------------ go
  function renderAll() {
    var run = currentRun();
    renderTabs();
    renderHero(run);
    renderStrip(run);
    renderClaims(run);
    renderLog(run);
    renderEvents(run);
    renderClaimTable(run);
    $("logfoot").textContent = "Select a line to see which claims cite it.";
    $("keytoggle").parentElement.hidden = !DATA.events.length;
    applySelection();
  }
  renderRuleTable();
  renderAll();
})();
