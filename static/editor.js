const campaignId = new URLSearchParams(location.search).get("id");

const titleEl = document.getElementById("campaign-title");
const resultEl = document.getElementById("result");
const streamsEl = document.getElementById("streams");
const fetchBtn = document.getElementById("fetch-streams-btn");
const pushAllBtn = document.getElementById("push-all-btn");

const STATUS_LABELS = {
  active: "Live",
  pending_add: "Pending (not pushed)",
  pending_remove: "Pending removal",
  removed: "Removed from KT",
};

let campaign = null;

function showResult(message, isError) {
  resultEl.style.display = "block";
  resultEl.className = isError ? "error" : "success";
  resultEl.textContent = message;
}

async function api(path, options) {
  const res = await fetch(path, options);
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const message = data && typeof data.detail === "string"
      ? data.detail
      : data && data.detail
        ? JSON.stringify(data.detail)
        : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

async function loadCampaign() {
  campaign = await api(`/api/campaigns/${campaignId}/detail`);
  render();
}

async function fetchStreams() {
  fetchBtn.disabled = true;
  try {
    campaign = await api(`/api/campaigns/${campaignId}/fetch-streams`, { method: "POST" });
    showResult("Streams fetched from Keitaro.", false);
    render();
  } catch (err) {
    showResult(`Error: ${err.message}`, true);
  } finally {
    fetchBtn.disabled = false;
  }
}

function replaceStream(updatedStream) {
  const idx = campaign.streams.findIndex((s) => s.id === updatedStream.id);
  if (idx !== -1) campaign.streams[idx] = updatedStream;
  render();
}

function hasPendingChanges() {
  return campaign.streams.some((s) => s.pending_changes);
}

function render() {
  titleEl.textContent = `${campaign.name} (KT #${campaign.keitaro_campaign_id})`;
  pushAllBtn.disabled = !hasPendingChanges();
  streamsEl.innerHTML = "";
  campaign.streams
    .slice()
    .sort((a, b) => {
      const aHasOffers = a.offers.length > 0 ? 0 : 1;
      const bHasOffers = b.offers.length > 0 ? 0 : 1;
      if (aHasOffers !== bHasOffers) return aHasOffers - bHasOffers;
      return a.position - b.position;
    })
    .forEach((stream) => streamsEl.appendChild(renderStream(stream)));
}

function renderStream(stream) {
  const card = document.createElement("div");
  card.className = stream.pending_changes ? "stream-card stream-card-dirty" : "stream-card";

  const header = document.createElement("div");
  header.className = "stream-header";
  header.innerHTML = `
    <div>
      <h2>${escapeHtml(stream.name)}</h2>
      <div class="stream-meta">position ${stream.position} &middot; schema: ${escapeHtml(stream.kt_schema)}</div>
    </div>
    ${stream.pending_changes ? '<span class="status-badge dirty-badge">Not pushed to KT</span>' : ""}
  `;
  card.appendChild(header);

  const table = document.createElement("table");
  table.innerHTML = `
    <thead><tr><th>Offer ID</th><th>Name</th><th>Weight</th><th>Pin</th><th>Status</th><th></th></tr></thead>
    <tbody></tbody>
  `;
  const tbody = table.querySelector("tbody");
  stream.offers.forEach((offer) => tbody.appendChild(renderOfferRow(offer)));
  card.appendChild(table);

  card.appendChild(renderAddOfferRow(stream));

  return card;
}

function renderOfferRow(offer) {
  const tr = document.createElement("tr");
  tr.className = `status-${offer.status}`;

  let actionButtons = "";
  if (offer.status === "active") {
    actionButtons = `<button class="danger" data-action="remove">Remove</button>`;
  } else if (offer.status === "pending_add") {
    actionButtons = `<button class="secondary" data-action="cancel">Cancel</button>`;
  } else if (offer.status === "pending_remove" || offer.status === "removed") {
    actionButtons = `<button data-action="bring-back">Bring back</button>`;
  }

  tr.innerHTML = `
    <td>${offer.offer_id}</td>
    <td>${escapeHtml(offer.offer_name)}</td>
    <td>${offer.weight}%</td>
    <td><button class="pin-btn ${offer.pinned ? "pinned" : ""}" data-action="pin" title="Pin weight">📌</button></td>
    <td><span class="status-badge">${STATUS_LABELS[offer.status] || offer.status}</span></td>
    <td>${actionButtons}</td>
  `;

  tr.querySelector('[data-action="pin"]').addEventListener("click", () => togglePin(offer));
  tr.querySelector('[data-action="remove"]')?.addEventListener("click", () => removeOffer(offer));
  tr.querySelector('[data-action="cancel"]')?.addEventListener("click", () => cancelOffer(offer));
  tr.querySelector('[data-action="bring-back"]')?.addEventListener("click", () => bringBackOffer(offer));

  return tr;
}

function renderAddOfferRow(stream) {
  const wrap = document.createElement("div");
  wrap.className = "add-offer-row";

  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Offer ID or name...";
  wrap.appendChild(input);

  const addBtn = document.createElement("button");
  addBtn.textContent = "Add offer";
  wrap.appendChild(addBtn);

  const offerSearch = setupOfferSearch(input);

  addBtn.addEventListener("click", async () => {
    const offerId = offerSearch.getSelectedId();
    if (!offerId) {
      showResult("Pick an offer from the suggestions list, or type a numeric offer ID.", true);
      return;
    }
    addBtn.disabled = true;
    try {
      const updatedStream = await api(`/api/streams/${stream.id}/offers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ offer_id: offerId }),
      });
      replaceStream(updatedStream);
      showResult(`Offer ${offerId} added (pending push).`, false);
    } catch (err) {
      showResult(`Error: ${err.message}`, true);
    } finally {
      addBtn.disabled = false;
    }
  });

  return wrap;
}

async function togglePin(offer) {
  try {
    const updatedStream = await api(`/api/stream-offers/${offer.id}/pin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pinned: !offer.pinned }),
    });
    replaceStream(updatedStream);
  } catch (err) {
    showResult(`Error: ${err.message}`, true);
  }
}

async function removeOffer(offer) {
  try {
    const updatedStream = await api(`/api/stream-offers/${offer.id}/remove`, { method: "POST" });
    replaceStream(updatedStream);
  } catch (err) {
    showResult(`Error: ${err.message}`, true);
  }
}

async function cancelOffer(offer) {
  try {
    const updatedStream = await api(`/api/stream-offers/${offer.id}`, { method: "DELETE" });
    replaceStream(updatedStream);
  } catch (err) {
    showResult(`Error: ${err.message}`, true);
  }
}

async function bringBackOffer(offer) {
  try {
    const updatedStream = await api(`/api/stream-offers/${offer.id}/bring-back`, { method: "POST" });
    replaceStream(updatedStream);
  } catch (err) {
    showResult(`Error: ${err.message}`, true);
  }
}

async function pushAll() {
  const streamsWithChanges = campaign.streams.filter((s) => s.pending_changes);

  if (streamsWithChanges.length === 0) {
    showResult("No pending changes to push.", false);
    return;
  }

  pushAllBtn.disabled = true;
  let pushedCount = 0;
  try {
    for (const stream of streamsWithChanges) {
      const updatedStream = await api(`/api/streams/${stream.id}/push`, { method: "POST" });
      const idx = campaign.streams.findIndex((s) => s.id === updatedStream.id);
      if (idx !== -1) campaign.streams[idx] = updatedStream;
      pushedCount += 1;
    }
    showResult(`Pushed changes for ${pushedCount} stream(s) to Keitaro.`, false);
  } catch (err) {
    showResult(`Error after pushing ${pushedCount}/${streamsWithChanges.length} stream(s): ${err.message}`, true);
  } finally {
    render();
  }
}

fetchBtn.addEventListener("click", fetchStreams);
pushAllBtn.addEventListener("click", pushAll);
loadCampaign().catch((err) => showResult(`Error: ${err.message}`, true));
