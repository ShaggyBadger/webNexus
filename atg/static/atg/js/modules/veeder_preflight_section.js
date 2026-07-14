(() => {
  function reset(host) {
    window.VeederGraphSection.destroyCharts(host);
    host.preflightRows = [];
    host.preflightReadings = [];
    host.overrideReasons = {};
    host.confirmedTokens = {};
  }

  function canConfirm(host) {
    if (!host.preflightRows || host.preflightRows.length === 0) {
      return false;
    }

    for (const row of host.preflightRows) {
      if (!host.confirmedTokens[row.preflight_token]) {
        return false;
      }
      if (row.decision === "outside_threshold_requires_override") {
        const reason = `${host.overrideReasons[row.preflight_token] ?? ""}`.trim();
        if (reason.length < 5) {
          return false;
        }
      }
    }

    return true;
  }

  async function runPreflight(host, readings) {
    host.submitting = true;
    host.showStatus("Validating readings...", "info");

    try {
      const response = await fetch("/atg/api/v1/readings/validate-preflight/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: JSON.stringify({
          store: host.selectedStore.store_pk,
          readings,
        }),
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload?.error?.message || "Preflight validation failed.");
      }

      host.preflightRows = payload?.data?.rows || [];
      host.preflightReadings = readings;
      host.confirmedTokens = {};
      host.overrideReasons = {};

      host.preflightRows.forEach((row) => {
        host.confirmedTokens[row.preflight_token] = false;
        host.overrideReasons[row.preflight_token] = "";
      });

      host.$nextTick(() => window.VeederGraphSection.renderCharts(host));
      host.showStatus("Preflight complete. Review each row and confirm before transmit.", "info");
    } catch (error) {
      host.showStatus(error.message, "error");
    } finally {
      host.submitting = false;
    }
  }

  async function confirmAndTransmit(host) {
    if (!canConfirm(host)) {
      host.showStatus("Confirm all rows and provide required override reasons.", "error");
      return;
    }

    host.submitting = true;
    host.showStatus("Transmitting data package...", "info");

    const formData = new FormData();
    formData.append("store", host.selectedStore.store_pk);
    formData.append("notes", host.notes || "");
    if (host.ticketTimestamp) {
      formData.append("ticket_timestamp", host.ticketTimestamp);
    }
    formData.append("readings_json", JSON.stringify(host.preflightReadings));
    formData.append(
      "preflight_tokens_json",
      JSON.stringify(host.preflightRows.map((row) => row.preflight_token)),
    );
    formData.append("preflight_override_reasons_json", JSON.stringify(host.overrideReasons));

    try {
      const response = await fetch("/atg/api/v1/tickets/", {
        method: "POST",
        headers: {
          "X-CSRFToken": document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
        body: formData,
      });

      const rawText = await response.text();
      let result = {};
      if (rawText) {
        try {
          result = JSON.parse(rawText);
        } catch (error) {
          result = { error: rawText };
        }
      }

      if (!response.ok) {
        let errMsg = "Transmission failed.";
        if (typeof result.error === "string") {
          errMsg = result.error;
        } else if (result.error?.message) {
          errMsg = result.error.message;
        } else if (result.error) {
          errMsg = JSON.stringify(result.error);
        }
        throw new Error(errMsg);
      }

      host.showStatus("Mission complete. Ticket ingested successfully.", "success");
      reset(host);
      setTimeout(() => {
        window.location.href = "/";
      }, 1400);
    } catch (error) {
      host.showStatus(error.message, "error");
    } finally {
      host.submitting = false;
    }
  }

  function cancelReview(host) {
    reset(host);
    host.showStatus("Preflight review dismissed. You can edit values and re-run.", "info");
  }

  window.VeederPreflightSection = {
    reset,
    canConfirm,
    runPreflight,
    confirmAndTransmit,
    cancelReview,
  };
})();
