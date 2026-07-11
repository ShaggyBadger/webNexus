function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content || "";
}

async function parseJsonSafe(response) {
  try {
    return await response.json();
  } catch (_error) {
    return null;
  }
}

function unwrapPayload(payload) {
  if (payload && payload.status === "success" && payload.data !== undefined) {
    return payload.data;
  }
  return payload;
}

function unwrapError(payload, fallbackMessage) {
  if (!payload) {
    return fallbackMessage;
  }
  if (payload.error && typeof payload.error.message === "string") {
    return payload.error.message;
  }
  if (typeof payload.error === "string") {
    return payload.error;
  }
  return fallbackMessage;
}

export async function initiateFeedback({ initiateUrl, payload }) {
  const response = await fetch(initiateUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
  const raw = await parseJsonSafe(response);
  if (!response.ok) {
    throw new Error(unwrapError(raw, "Failed to start feedback report."));
  }
  return unwrapPayload(raw);
}

export async function submitFeedback({ payload }) {
  const response = await fetch(`/feedback/api/v1/submit/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
  const raw = await parseJsonSafe(response);
  if (!response.ok) {
    throw new Error(unwrapError(raw, "Failed to submit feedback report."));
  }
  return unwrapPayload(raw);
}
