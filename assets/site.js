(function () {
  var slot = document.getElementById("stardate");
  if (slot) {
    var now = new Date();
    var start = new Date(now.getFullYear(), 0, 1);
    var day = Math.round((new Date(now.getFullYear(), now.getMonth(), now.getDate()) - start) / 86400000) + 1;
    slot.textContent = now.getFullYear() + "." + String(day).padStart(3, "0");
    slot.setAttribute("datetime", now.toISOString().slice(0, 10));
  }

  var form = document.querySelector(".search");
  var query = document.getElementById("q");
  if (!form || !query) return;

  var cards = Array.prototype.slice.call(document.querySelectorAll(".card"));
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  var empty = document.getElementById("empty");
  var count = document.getElementById("count");
  var total = cards.length;
  var active = new Set();

  function selectedTags() {
    var params = new URLSearchParams(window.location.search);
    params.getAll("tag").forEach(function (value) {
      value.split(",").forEach(function (part) {
        var tag = part.trim().toLowerCase();
        if (tag) active.add(tag);
      });
    });
    var initialQuery = params.get("q");
    if (initialQuery) query.value = initialQuery;
  }

  function paint() {
    chips.forEach(function (chip) {
      var on = active.has(chip.getAttribute("data-filter"));
      chip.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function writeUrl() {
    var url = new URL(window.location.href);
    url.searchParams.delete("tag");
    Array.from(active).sort().forEach(function (tag) {
      url.searchParams.append("tag", tag);
    });
    if (query.value.trim()) url.searchParams.set("q", query.value);
    else url.searchParams.delete("q");
    history.replaceState(null, "", url);
  }

  function apply() {
    var needle = query.value.trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (card) {
      var tags = (card.getAttribute("data-tags") || "").split(",");
      var hay = card.getAttribute("data-hay") || "";
      var tagsOk = Array.from(active).every(function (tag) {
        return tags.indexOf(tag) !== -1;
      });
      var textOk = !needle || hay.indexOf(needle) !== -1;
      var on = tagsOk && textOk;
      card.hidden = !on;
      if (on) shown += 1;
    });
    if (empty) empty.hidden = shown !== 0;
    if (count) {
      count.textContent = shown === total
        ? total + " retired " + (total === 1 ? "box" : "boxes")
        : "Showing " + shown + " of " + total;
    }
  }

  selectedTags();
  paint();
  apply();

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    apply();
    writeUrl();
  });

  query.addEventListener("input", function () {
    apply();
    writeUrl();
  });

  query.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      query.value = "";
      apply();
      writeUrl();
      query.blur();
    }
  });

  document.addEventListener("click", function (event) {
    var chip = event.target.closest(".chip");
    if (!chip) return;
    event.preventDefault();
    var tag = chip.getAttribute("data-filter");
    if (!tag) return;
    if (active.has(tag)) active.delete(tag);
    else active.add(tag);
    paint();
    apply();
    writeUrl();
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "/" || event.altKey || event.ctrlKey || event.metaKey) return;
    var target = event.target;
    var typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
    if (typing) return;
    event.preventDefault();
    query.focus();
    query.select();
  });
})();
