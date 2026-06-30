import { IntelMarkdown } from "./intel_markdown.js";

document.addEventListener("DOMContentLoaded", () => {
  const toolbarId = "intel-md-toolbar";
  const toolbar = document.getElementById(toolbarId);
  if (!toolbar) {
    return;
  }

  const textarea = document.querySelector("textarea");
  if (!textarea) {
    console.error("SITEINTEL_MARKDOWN_INIT_FAILED_NO_TEXTAREA");
    return;
  }

  if (!textarea.id) {
    textarea.id = "site-intel-notes-textarea";
  }

  IntelMarkdown.init(textarea.id, toolbarId);
});
