/* Adapt IQ — global loading states.
 *
 * Progressive enhancement: every form keeps working without JS. With JS:
 *  - forms marked data-busy="<kind>" show a themed status line (rotating
 *    math glyph + cycling messages) while the server thinks;
 *  - the mentor form additionally shows a "typing" bubble in the thread;
 *  - links marked data-busy-link="<kind>" show a floating status pill;
 *  - a slim progress bar runs along the top during any navigation;
 *  - every form (marked or not) is protected against double submission;
 *  - everything resets when a page is restored from the back/forward cache;
 *  - prefers-reduced-motion swaps animation for a calm static state.
 */
(function () {
  "use strict";

  var GLYPHS = ["∫", "∑", "π", "√", "Δ", "θ", "∂", "∞"];
  var GLYPH_MS = 600;   // glyph carousel step
  var MSG_MS = 2600;    // status message dwell time
  var FADE_MS = 220;    // message cross-fade

  var MESSAGES = {
    mentor:   ["Reading your thinking…", "Working out the next step…",
               "Choosing a question, not an answer…", "Nearly there…"],
    practice: ["Composing a fresh problem…", "Picking numbers you haven't seen…",
               "Building the hint ladder…", "Double-checking the answer…"],
    quiz:     ["Reviewing your recent scores…", "Writing six fresh questions…",
               "Balancing the difficulty…", "Adding one tricky one…"],
    revision: ["Choosing chapters to revisit…", "Mixing in missed concepts…",
               "Writing fresh questions…", "Spacing the repetition…"],
    grade:    ["Checking every answer…", "Writing feedback for each question…",
               "Tracing the concepts you used…"],
    draft:    ["Drafting questions for your review…", "Matching the chapter syllabus…",
               "Writing answer explanations…"],
    lesson:   ["Searching the library…", "Selecting licensed sources…",
               "Composing a cited lesson…", "Formatting the mathematics…"],
    docqa:    ["Reading the document…", "Finding the right passage…",
               "Writing a grounded answer…"],
    notes:    ["Reading your notes…", "Finding the key ideas…",
               "Writing the summary…"],
    search:   ["Searching by meaning…", "Ranking the best matches…"],
    upload:   ["Uploading…", "Extracting the text…", "Indexing for search…"],
    score:    ["Scoring your responses…", "Reading your written answers…",
               "Building your learning profile…", "Preparing your report…"],
    save:     ["Saving…"],
    dflt:     ["Working on it…", "One moment…"]
  };

  var reduceMotion = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var timers = [];

  function later(fn, ms, repeat) {
    var id = repeat ? setInterval(fn, ms) : setTimeout(fn, ms);
    timers.push({ id: id, repeat: repeat });
    return id;
  }

  /* ---- slim top progress bar ------------------------------------------ */
  function pagebar() {
    var bar = document.getElementById("pagebar");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "pagebar";
      bar.setAttribute("aria-hidden", "true");
      document.body.appendChild(bar);
    }
    bar.classList.add("on");
  }

  /* ---- glyph + message status line ------------------------------------ */
  function statusNode(kind, extraClass) {
    var msgs = MESSAGES[kind] || MESSAGES.dflt;
    var el = document.createElement("p");
    el.className = "busy-status" + (extraClass ? " " + extraClass : "");
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    el.innerHTML = '<span class="busy-glyph"></span><span class="busy-msg"></span>';
    var glyphEl = el.querySelector(".busy-glyph");
    var msgEl = el.querySelector(".busy-msg");
    var g = Math.floor(Math.random() * GLYPHS.length);
    var m = 0;
    glyphEl.textContent = GLYPHS[g];
    msgEl.textContent = msgs[0];
    if (!reduceMotion) {
      later(function () {
        g = (g + 1) % GLYPHS.length;
        glyphEl.textContent = GLYPHS[g];
      }, GLYPH_MS, true);
    }
    if (msgs.length > 1) {
      later(function () {
        msgEl.style.opacity = "0";
        later(function () {
          m = (m + 1) % msgs.length;
          msgEl.textContent = msgs[m];
          msgEl.style.opacity = "1";
        }, FADE_MS, false);
      }, MSG_MS, true);
    }
    return el;
  }

  /* ---- mentor "typing" bubble ------------------------------------------ */
  function typingBubble(form) {
    var thread = document.querySelector(".mentor-thread");
    if (!thread) {
      thread = document.createElement("div");
      thread.className = "mentor-thread";
      form.parentNode.insertBefore(thread, form);
    }
    var text = (form.querySelector("textarea[name=message]") || {}).value;
    if (text) {                       // echo the student's message immediately
      var mine = document.createElement("div");
      mine.className = "mentor-answer asked-row";
      mine.innerHTML = '<p class="asked">You</p><p></p>';
      mine.lastElementChild.textContent = text;
      thread.appendChild(mine);
    }
    var bubble = document.createElement("div");
    bubble.className = "mentor-answer ok thinking";
    bubble.innerHTML = '<p class="asked">Mentor</p>' +
      '<p class="t-line"><span class="busy-dots"><i></i><i></i><i></i></span></p>';
    thread.appendChild(bubble);
    bubble.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
  }

  function markButtonBusy(form) {
    var btn = form.querySelector("button[type=submit], button:not([type])");
    if (!btn) return;
    // Disable AFTER the browser serializes the form, so button values submit.
    setTimeout(function () {
      btn.classList.add("is-busy");
      btn.setAttribute("aria-disabled", "true");
      btn.disabled = true;
    }, 0);
  }

  /* ---- form submissions ------------------------------------------------ */
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.dataset.busyActive) {          // double-submit guard (all forms)
      e.preventDefault();
      return;
    }
    form.dataset.busyActive = "1";
    markButtonBusy(form);
    pagebar();
    var kind = form.dataset.busy;
    if (!kind) return;                       // guarded, but no themed visuals
    if (kind === "mentor") typingBubble(form);
    form.appendChild(statusNode(kind));
  });

  /* ---- slow links (e.g. “Teach me this →”) ----------------------------- */
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest && e.target.closest("a[data-busy-link]");
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || a.target === "_blank") return;
    pagebar();
    if (!document.querySelector(".busy-toast")) {
      document.body.appendChild(statusNode(a.dataset.busyLink, "busy-toast"));
    }
  });

  /* ---- restore from back/forward cache: undo everything ---------------- */
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    timers.forEach(function (t) { t.repeat ? clearInterval(t.id) : clearTimeout(t.id); });
    timers = [];
    var bar = document.getElementById("pagebar");
    if (bar) bar.classList.remove("on");
    document.querySelectorAll(".busy-status, .thinking").forEach(function (n) { n.remove(); });
    document.querySelectorAll("form[data-busy-active]").forEach(function (f) {
      delete f.dataset.busyActive;
      f.querySelectorAll("button.is-busy").forEach(function (b) {
        b.classList.remove("is-busy");
        b.removeAttribute("aria-disabled");
        b.disabled = false;
      });
    });
  });
})();
