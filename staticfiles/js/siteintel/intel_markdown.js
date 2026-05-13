/**
 * INTEL_MARKDOWN_MODULE
 * Provides a simple tactical toolbar for markdown formatting.
 */
export const IntelMarkdown = {
    /**
     * Initializes the markdown toolbar.
     * @param {string} textareaId - The ID of the textarea to control.
     * @param {string} toolbarContainerId - The ID of the toolbar container.
     */
    init: function(textareaId, toolbarContainerId) {
        const textarea = document.getElementById(textareaId);
        const toolbar = document.getElementById(toolbarContainerId);
        if (!textarea || !toolbar) return;

        toolbar.querySelectorAll('[data-md-cmd]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const cmd = btn.dataset.mdCmd;
                this.applyFormat(textarea, cmd);
            });
        });

        console.log("INTEL_MARKDOWN_READY");
    },

    /**
     * Applies markdown formatting to the selected text.
     */
    applyFormat: function(textarea, cmd) {
        const start = textarea.selectionStart;
        const end = textarea.selectionEnd;
        const text = textarea.value;
        const selection = text.substring(start, end);

        let formatted = "";
        let newCursorStart = start;
        let newCursorEnd = end;

        switch(cmd) {
            case 'bold':
                formatted = `**${selection || "BOLD_TEXT"}**`;
                if (!selection) {
                    newCursorStart = start + 2;
                    newCursorEnd = start + 11;
                } else {
                    newCursorEnd = start + formatted.length;
                }
                break;
            case 'italic':
                formatted = `*${selection || "ITALIC_TEXT"}*`;
                if (!selection) {
                    newCursorStart = start + 1;
                    newCursorEnd = start + 12;
                } else {
                    newCursorEnd = start + formatted.length;
                }
                break;
            case 'list':
                // Check if we need a leading newline
                const needsNewline = start !== 0 && text[start - 1] !== '\n';
                const prefix = needsNewline ? '\n' : '';
                
                if (selection.length > 0) {
                    // Turn every line in the selection into a list item
                    formatted = prefix + selection.split('\n').map(line => `- ${line}`).join('\n');
                    newCursorEnd = start + formatted.length;
                } else {
                    formatted = prefix + `- LIST_ITEM`;
                    newCursorStart = start + prefix.length + 2;
                    newCursorEnd = start + formatted.length;
                }
                break;
            case 'link':
                formatted = `[${selection || "LINK_TEXT"}](https://URL)`;
                if (!selection) {
                    newCursorStart = start + 1;
                    newCursorEnd = start + 10;
                } else {
                    newCursorStart = start + selection.length + 3; // Position after [selection](
                    newCursorEnd = start + formatted.length - 1;   // Select the URL part
                }
                break;
        }

        // Apply the change
        textarea.value = text.substring(0, start) + formatted + text.substring(end);
        
        // Refocus and set cursor
        textarea.focus();
        textarea.setSelectionRange(newCursorStart, newCursorEnd);
        
        // Trigger change event for any listeners
        const event = new Event('input', { bubbles: true });
        textarea.dispatchEvent(event);
        
        console.log(`MD_FORMAT_APPLIED: ${cmd}`);
    }
};
