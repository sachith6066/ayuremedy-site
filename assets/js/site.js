// Clinic & pharmacy hours (IST). Keep in sync with the footer and the schema in build.py.
var HOURS = { 0: [9, 13], 1: [9, 20], 2: [9, 20], 3: [9, 20], 4: [9, 20], 5: [9, 20], 6: [9, 20] };
var WHATSAPP = "919448150492";

function istNow() {
  var parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata", weekday: "short", hour: "numeric", minute: "numeric", hourCycle: "h23"
  }).formatToParts(new Date());
  var get = function (t) { return (parts.find(function (p) { return p.type === t; }) || {}).value; };
  var days = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  return { day: days[get("weekday")], mins: parseInt(get("hour"), 10) * 60 + parseInt(get("minute"), 10) };
}

function fmt(h) {
  var suffix = h >= 12 ? "PM" : "AM";
  var h12 = h % 12 === 0 ? 12 : h % 12;
  return h12 + " " + suffix;
}

function renderStatus() {
  var els = document.querySelectorAll("[data-open-status]");
  if (!els.length) return;
  var now = istNow();
  var today = HOURS[now.day];
  var open = now.mins >= today[0] * 60 && now.mins < today[1] * 60;
  var text;
  if (open) {
    text = "Open now, until " + fmt(today[1]);
  } else if (now.mins < today[0] * 60) {
    text = "Closed now, opens " + fmt(today[0]) + " today";
  } else {
    var next = HOURS[(now.day + 1) % 7];
    text = "Closed now, opens " + fmt(next[0]) + " tomorrow";
  }
  els.forEach(function (el) {
    el.textContent = text;
    el.setAttribute("data-open", String(open));
  });
}

function initForm() {
  var form = document.getElementById("visit-form");
  if (!form) return;
  var msg = document.getElementById("visit-form-msg");
  var dateInput = document.getElementById("visit-date");
  if (dateInput) {
    var t = new Date();
    dateInput.min = t.toISOString().slice(0, 10);
  }
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var name = form.elements["name"].value.trim();
    var phone = form.elements["phone"].value.trim();
    if (!name || phone.replace(/\D/g, "").length < 10) {
      msg.dataset.state = "error";
      msg.textContent = "Please add your name and a 10-digit phone number so the clinic can call you back.";
      return;
    }
    var lines = [
      "Appointment request (from ayuremedy.com)",
      "Name: " + name,
      "Phone: " + phone,
      "Preferred date: " + (form.elements["date"].value || "Any"),
      "Preferred time: " + form.elements["slot"].value,
      "Doctor: " + form.elements["doctor"].value,
      "Best time to call me: " + form.elements["calltime"].value
    ];
    var reason = form.elements["reason"].value.trim();
    if (reason) lines.push("Reason: " + reason);
    var url = "https://wa.me/" + WHATSAPP + "?text=" + encodeURIComponent(lines.join("\n"));
    msg.dataset.state = "";
    msg.innerHTML = "Your request is ready in WhatsApp. Press send there and the front desk will call you to confirm a time. " +
      "If WhatsApp did not open, <a href=\"" + url + "\" target=\"_blank\" rel=\"noopener\">open it here</a> or call 080-4854 2888.";
    track("booking_request", { doctor: form.elements["doctor"].value });
    window.open(url, "_blank", "noopener");
  });
}

function initCopy() {
  document.querySelectorAll("[data-copy]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var value = btn.getAttribute("data-copy");
      var done = function () { btn.textContent = "Copied"; setTimeout(function () { btn.textContent = "Copy"; }, 1600); };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(done, function () { btn.textContent = value; });
      } else {
        btn.textContent = value;
      }
    });
  });
}

function markSeason() {
  var seasons = document.querySelectorAll("#ritu .season");
  if (!seasons.length) return;
  var month = parseInt(new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", month: "numeric" }).format(new Date()), 10);
  seasons.forEach(function (el) {
    if (el.getAttribute("data-months").split(",").indexOf(String(month)) === -1) return;
    el.setAttribute("data-current", "true");
    var note = document.getElementById("ritu-note");
    if (note) {
      var name = el.querySelector("h3").textContent;
      note.insertAdjacentHTML("afterbegin", "It is <strong>" + name + " ritu</strong> now. ");
    }
  });
}

// Enquiry clicks for GA4 (and Google Ads, via imported key events). Only the event name and
// which button was used are sent, never form contents. Does nothing until build.py has a GA_ID.
function track(name, params) {
  if (typeof window.gtag === "function") window.gtag("event", name, params || {});
}

function placeOf(a) {
  if (a.closest(".action-bar")) return "mobile_bar";
  if (a.classList.contains("float-chat")) return "float_button";
  if (a.closest(".site-header")) return "header";
  if (a.closest("footer")) return "footer";
  return "page";
}

function initTracking() {
  document.addEventListener("click", function (e) {
    var a = e.target.closest("a[href]");
    if (!a) return;
    var href = a.getAttribute("href");
    var place = { link_location: placeOf(a) };
    if (href.indexOf("tel:") === 0) {
      place.line = href.indexOf("tel:+9180") === 0 ? "landline" : "mobile";
      track("call_click", place);
    } else if (href.indexOf("wa.me/") !== -1) {
      track("whatsapp_click", place);
    } else if (href.indexOf("google.com/maps") !== -1) {
      track("directions_click", place);
    } else if (href.indexOf("mailto:") === 0) {
      track("email_click", place);
    }
  });
}

// Facebook videos are links to the video until tapped; then Facebook's player replaces the poster.
function initReels() {
  document.querySelectorAll("a.reel[data-fb]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      var f = document.createElement("iframe");
      f.className = "reel-frame";
      f.src = "https://www.facebook.com/plugins/video.php?href=" + encodeURIComponent(a.href) + "&show_text=false&width=360&autoplay=true";
      f.title = a.getAttribute("aria-label").replace("Play video: ", "");
      f.allow = "autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share";
      f.allowFullscreen = true;
      a.replaceWith(f);
    });
  });
}

document.addEventListener("DOMContentLoaded", function () {
  renderStatus();
  initTracking();
  initReels();
  markSeason();
  initForm();
  initCopy();
  var y = document.getElementById("year");
  if (y) y.textContent = new Date().getFullYear();
});
