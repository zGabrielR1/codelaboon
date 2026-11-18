browser.runtime.onMessage.addListener((message, sender) => {
  if (new URL(sender.url || "about:blank").origin !== "https://claude.ai" ||
      !["prompt", "reply"].includes(message.action) ||
      !/^[A-Za-z0-9_-]{43}$/.test(message.token)) return;

  const sendReply = message.action === "reply";
  return fetch("http://127.0.0.1:18767/" + message.action, {
    method: sendReply ? "POST" : "GET",
    headers: {
      Authorization: "Bearer " + message.token,
      "Content-Type": "application/json",
    },
    body: sendReply ? JSON.stringify(message.result) : undefined,
  }).then(async response => {
    if (!response.ok) throw new Error("Codelaboon bridge rejected the request.");
    const data = await response.json();
    const tab = sender.tab;
    if (!tab) return data;
    if (!sendReply && data.background && tab.active) {
      const tabs = await browser.tabs.query({ windowId: tab.windowId });
      const previous = tabs.filter(candidate => candidate.id !== tab.id)
        .sort((first, second) => second.lastAccessed - first.lastAccessed)[0];
      if (previous) {
        await browser.tabs.update(previous.id, { active: true }).catch(() => {});
      }
    }
    if (sendReply && message.background && message.result.reply) {
      setTimeout(() => browser.tabs.remove(tab.id).catch(() => {}), 250);
    }
    return data;
  });
});
