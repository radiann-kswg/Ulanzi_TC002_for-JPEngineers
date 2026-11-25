// Dot marks incoming articles separately from the user's own messages.
const opened = Date.now();
const delivered = new Map();
let scanning = false;
let scheduled = false;

function schedule(delay = 250) {
  if (scheduled) return;
  scheduled = true;
  setTimeout(scan, delay);
}

async function scan() {
  scheduled = false;
  if (scanning || !location.pathname.startsWith("/dots/")) return;
  scanning = true;
  try {
    const cutoff = Math.max(opened, Date.now() - 60000);
    for (const [id, at] of delivered) if (at < cutoff) delivered.delete(id);
    const items = [];
    for (const row of document.querySelectorAll('article[data-dot-message="true"][data-message-id]')) {
      const id = row.dataset.messageId;
      const at = Date.parse(row.querySelector("time[datetime]")?.dateTime);
      if (id && at >= cutoff && !delivered.has(id)) items.push({id, at});
    }
    if (items.length) {
      const batch = items.slice(0, 128);
      const reply = await chrome.runtime.sendMessage(batch);
      if (reply?.ok) {
        for (const {id, at} of batch) delivered.set(id, at);
        schedule();
      } else schedule(3000);
    }
  } catch {
    schedule(3000);
  } finally {
    scanning = false;
  }
}

new MutationObserver(() => schedule()).observe(document, {
  subtree: true, childList: true, attributes: true,
  attributeFilter: ["datetime", "data-dot-message", "data-message-id"]
});
schedule();
