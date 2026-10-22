function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

// Wraps a text input with a debounced Keitaro offer autocomplete dropdown
// backed by GET /api/offers/search. Returns { getSelectedId, clear }.
function setupOfferSearch(input) {
  let selectedOfferId = null;
  let debounceTimer = null;

  const wrap = document.createElement("div");
  wrap.className = "offer-search-wrap";
  input.parentNode.insertBefore(wrap, input);
  wrap.appendChild(input);

  const suggestions = document.createElement("div");
  suggestions.className = "offer-suggestions";
  suggestions.style.display = "none";
  wrap.appendChild(suggestions);

  function hideSuggestions() {
    suggestions.style.display = "none";
  }

  input.addEventListener("input", () => {
    selectedOfferId = null;
    const query = input.value.trim();
    clearTimeout(debounceTimer);
    if (!query) {
      hideSuggestions();
      suggestions.innerHTML = "";
      return;
    }
    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/offers/search?q=${encodeURIComponent(query)}`);
        const results = res.ok ? await res.json() : [];
        suggestions.innerHTML = results
          .map((o) => `<div data-id="${o.id}" data-name="${escapeHtml(o.name)}">#${o.id} — ${escapeHtml(o.name)}</div>`)
          .join("");
        suggestions.style.display = results.length ? "block" : "none";
      } catch {
        hideSuggestions();
      }
    }, 250);
  });

  suggestions.addEventListener("click", (event) => {
    const target = event.target.closest("[data-id]");
    if (!target) return;
    selectedOfferId = Number(target.dataset.id);
    input.value = `#${target.dataset.id} — ${target.dataset.name}`;
    hideSuggestions();
  });

  document.addEventListener("click", (event) => {
    if (!wrap.contains(event.target)) hideSuggestions();
  });

  return {
    getSelectedId() {
      if (selectedOfferId) return selectedOfferId;
      const typed = input.value.trim();
      return /^\d+$/.test(typed) ? Number(typed) : null;
    },
    clear() {
      selectedOfferId = null;
      input.value = "";
      hideSuggestions();
    },
  };
}
