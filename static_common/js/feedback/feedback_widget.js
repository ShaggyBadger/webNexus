import { initiateFeedback, submitFeedback } from "./api_client.js";
import {
  collectFeedbackMetadata,
  getViewportSize,
} from "./metadata_collectors.js";

function setStatus(statusEl, message, isError = false) {
  if (!statusEl) {
    return;
  }
  statusEl.textContent = message;
  statusEl.classList.toggle("text-tactical-danger", isError);
  statusEl.classList.toggle("text-tactical-success", !isError && !!message);
}

function initFeedbackWidget() {
  const root = document.getElementById("feedback-widget");
  if (!root) {
    return;
  }

  const initiateUrl = root.dataset.initUrl;
  const openBtn = document.getElementById("feedback-open-btn");
  const closeBtn = document.getElementById("feedback-close-btn");
  const backdrop = document.getElementById("feedback-modal-close-backdrop");
  const modal = document.getElementById("feedback-modal");
  const submitBtn = document.getElementById("feedback-submit-btn");
  const categoryInput = document.getElementById("feedback-category");
  const messageInput = document.getElementById("feedback-message");
  const statusEl = document.getElementById("feedback-status");

  let clickEventId = null;
  let initiating = false;
  let submitting = false;

  async function ensureInitiated() {
    if (clickEventId || initiating) {
      return;
    }
    initiating = true;
    setStatus(statusEl, "Capturing telemetry context...");
    try {
      const metadata = collectFeedbackMetadata();
      const payload = {
        url: `${window.location.pathname}${window.location.search}`,
        user_agent: window.navigator.userAgent,
        viewport_size: getViewportSize(),
        page_metadata: metadata,
      };
      const data = await initiateFeedback({ initiateUrl, payload });
      clickEventId = data.click_event_id;
      setStatus(
        statusEl,
        `Telemetry captured (Click ID: ${clickEventId}). Add details and submit.`,
      );
    } catch (error) {
      setStatus(statusEl, error.message, true);
    } finally {
      initiating = false;
    }
  }

  function openModal() {
    if (!modal) {
      return;
    }
    modal.hidden = false;
    ensureInitiated();
  }

  function closeModal() {
    if (!modal) {
      return;
    }
    modal.hidden = true;
  }

  async function handleSubmit() {
    if (submitting) {
      return;
    }
    if (!clickEventId) {
      setStatus(statusEl, "Telemetry report is not initialized yet. Try again.", true);
      return;
    }
    if (!categoryInput.value) {
      setStatus(statusEl, "Select a category before submitting.", true);
      return;
    }

    submitting = true;
    setStatus(statusEl, "Submitting report...");
    submitBtn.disabled = true;
    try {
      await submitFeedback({
        payload: {
          click_event_id: clickEventId,
          category: categoryInput.value,
          message: messageInput.value,
          page_metadata: collectFeedbackMetadata(),
        },
      });
      setStatus(statusEl, "Feedback submitted. Thank you.");
      categoryInput.value = "";
      messageInput.value = "";
      setTimeout(closeModal, 500);
    } catch (error) {
      setStatus(statusEl, error.message, true);
    } finally {
      submitBtn.disabled = false;
      submitting = false;
    }
  }

  openBtn?.addEventListener("click", openModal);
  closeBtn?.addEventListener("click", closeModal);
  backdrop?.addEventListener("click", closeModal);
  submitBtn?.addEventListener("click", handleSubmit);
}

document.addEventListener("DOMContentLoaded", initFeedbackWidget);
