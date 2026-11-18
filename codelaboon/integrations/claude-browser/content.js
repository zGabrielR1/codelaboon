(async () => {
  const match = /^#codelaboon=([A-Za-z0-9_-]{43})$/.exec(location.hash);
  if (!match) return;
  const token = match[1];
  history.replaceState(null, "", location.pathname + location.search);

  async function until(predicate, timeout, error) {
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      const value = predicate();
      if (value) return value;
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    throw new Error(error);
  }

  let result;
  let background = false;
  try {
    const request = await browser.runtime.sendMessage({ action: "prompt", token });
    const { prompt } = request;
    background = request.background === true;
    const composer = await until(
      () => document.querySelector('.tiptap[contenteditable="true"], [contenteditable="true"][role="textbox"]'),
      15000, "Claude.ai chat did not open. Sign in through your usual browser tab and retry."
    );
    const responseSelector = [
      ".font-claude-response", '[data-testid="assistant-message"]',
    ].join(", ");
    const stopSelector = [
      'button[aria-label*="stop" i]', 'button[data-testid*="stop" i]',
    ].join(", ");
    if (document.querySelector(responseSelector)) throw new Error("Claude.ai did not open a new conversation.");

    composer.focus();
    if (!document.execCommand("insertText", false, prompt)) {
      throw new Error("Could not enter the prompt in Claude.ai.");
    }
    const send = await until(
      () => document.querySelector('button[aria-label="Send message"]:not(:disabled), button[data-testid="send-button"]:not(:disabled)'),
      10000, "Claude.ai's send button was unavailable."
    );
    send.click();

    let previousText = "";
    let stableSince = 0;
    const reply = await until(() => {
      const responses = [...document.querySelectorAll(responseSelector)];
      const last = responses.filter(node => !responses.some(other => other !== node && other.contains(node))).at(-1);
      const text = last?.innerText.trim() || "";
      if (text !== previousText) {
        previousText = text;
        stableSince = Date.now();
      }
      if (!text) return "";
      const streaming = last.closest("[data-is-streaming]") ||
        last.querySelector("[data-is-streaming]");
      const stopping = [...document.querySelectorAll(stopSelector)].some(
        button => button.getClientRects().length > 0 && !button.disabled
      );
      if (stopping || streaming?.dataset.isStreaming === "true") {
        stableSince = Date.now();
        return "";
      }
      if (streaming?.dataset.isStreaming === "false" || Date.now() - stableSince >= 3500) {
        return text;
      }
      return "";
    }, 175000, "Claude.ai did not return readable reply text. Check its browser tab for the response or a usage limit.");
    result = { reply };
  } catch (error) {
    result = { error: error.message };
  }
  await browser.runtime.sendMessage({ action: "reply", token, result, background });
})().catch(error => console.error("Codelaboon browser bridge:", error.message));
