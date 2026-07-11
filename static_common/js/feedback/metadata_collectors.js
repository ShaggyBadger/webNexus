function parseJsonScript(scriptId) {
  const scriptTag = document.getElementById(scriptId);
  if (!scriptTag) {
    return {};
  }
  try {
    const parsed = JSON.parse(scriptTag.textContent || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch (_error) {
    return { _feedback_context_parse_error: true };
  }
}

function collectDynamicMetadata() {
  const detailContainer = { metadata: {} };
  const event = new CustomEvent("feedback-request-metadata", {
    detail: detailContainer,
  });
  window.dispatchEvent(event);
  return detailContainer.metadata || {};
}

function collectRegisteredProviderMetadata() {
  const providers = window.__webnexusFeedbackProviders;
  if (!Array.isArray(providers) || providers.length === 0) {
    return {};
  }

  const merged = {};
  providers.forEach((provider) => {
    if (typeof provider !== "function") {
      return;
    }
    try {
      const payload = provider();
      if (payload && typeof payload === "object") {
        Object.assign(merged, payload);
      }
    } catch (_error) {
      merged._provider_error = true;
    }
  });
  return merged;
}

function collectTankGaugeFromAlpine() {
  if (!window.Alpine || typeof window.Alpine.$data !== "function") {
    return {};
  }
  const root = document.querySelector(".tankgauge-spa[x-data]");
  if (!root) {
    return {};
  }

  try {
    const state = window.Alpine.$data(root);
    if (!state || typeof state !== "object") {
      return {};
    }
    return {
      tankgauge_alpine: {
        step: state.step ?? null,
        store_data: state.storeData ?? null,
        selected_tank: state.selectedTank ?? null,
        input_values: state.inputs ?? null,
        calculation_results: state.results ?? null,
        chart_data: state.chartData ?? null,
      },
    };
  } catch (_error) {
    return { _tankgauge_alpine_read_error: true };
  }
}

export function collectFeedbackMetadata() {
  const pageContext = parseJsonScript("feedback-context");
  const dynamicContext = collectDynamicMetadata();
  const providerContext = collectRegisteredProviderMetadata();
  const alpineContext = collectTankGaugeFromAlpine();
  return {
    path: window.location.pathname,
    query: window.location.search,
    hash: window.location.hash,
    collected_at: new Date().toISOString(),
    page_context: pageContext,
    dynamic_context: {
      ...dynamicContext,
      ...providerContext,
      ...alpineContext,
    },
  };
}

export function getViewportSize() {
  const width = window.innerWidth || 0;
  const height = window.innerHeight || 0;
  return `${width}x${height}`;
}
