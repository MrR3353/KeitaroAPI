const form = document.getElementById("create-form");
const submitBtn = document.getElementById("submit-btn");
const resultBox = document.getElementById("result");
const historyBody = document.getElementById("history-body");

function showResult(message, isError) {
  resultBox.style.display = "block";
  resultBox.className = isError ? "error" : "success";
  resultBox.textContent = message;
}

async function loadHistory() {
  const res = await fetch("/api/campaigns");
  const items = await res.json();
  historyBody.innerHTML = items
    .map(
      (item) => `
        <tr data-id="${item.id}" title="Open editor">
          <td>${item.keitaro_campaign_id}</td>
          <td>${item.name}</td>
          <td>${item.country_code}</td>
          <td>${item.offer_id}</td>
          <td>${new Date(item.created_at).toLocaleString()}</td>
        </tr>`
    )
    .join("");

  historyBody.querySelectorAll("tr[data-id]").forEach((row) => {
    row.addEventListener("click", () => {
      window.location.href = `editor.html?id=${row.dataset.id}`;
    });
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitBtn.disabled = true;
  resultBox.style.display = "none";

  const payload = {
    name: document.getElementById("name").value,
    country_code: document.getElementById("country_code").value,
    offer_id: Number(document.getElementById("offer_id").value),
  };

  try {
    const res = await fetch("/api/campaigns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = null;
    }

    if (!res.ok) {
      const message = data && typeof data.detail === "string"
        ? data.detail
        : data && data.detail
          ? JSON.stringify(data.detail)
          : "Internal server error";
      throw new Error(message);
    }
    showResult(`Done! Campaign ID: ${data.keitaro_campaign_id}, alias: ${data.alias}`, false);
    form.reset();
    await loadHistory();
  } catch (err) {
    showResult(`Error: ${err.message}`, true);
  } finally {
    submitBtn.disabled = false;
  }
});

loadHistory();
