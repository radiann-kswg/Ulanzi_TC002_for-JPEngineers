chrome.runtime.onMessage.addListener((items, sender, respond) => {
  if (sender.frameId !== 0 || !/^https:\/\/chatgpt\.com\/dots(?:[/?#]|$)/.test(sender.url) ||
      !Array.isArray(items)) return;
  chrome.runtime.sendNativeMessage("jp.tc002.dot", items)
    .then(respond, () => respond({ok: false}));
  return true;
});
