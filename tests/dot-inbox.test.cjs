const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {test} = require("node:test");
const vm = require("node:vm");

test("Dot forwards each new incoming ID once, retrying a failed delivery", async () => {
  const rows = [];
  const calls = [];
  const timers = [];
  const opened = Date.now();
  const location = {pathname: "/dots/test"};
  let mutated;
  const extension = path.join(__dirname, "../bridge/dot-extension/inbox.js");
  vm.runInNewContext(fs.readFileSync(extension, "utf8"), {
    Date: class extends Date { static now() { return opened; } },
    location,
    document: {querySelectorAll(selector) {
      assert.equal(selector, 'article[data-dot-message="true"][data-message-id]');
      return rows.filter(row => row.incoming);
    }},
    MutationObserver: class {
      constructor(callback) { mutated = callback; }
      observe() {}
    },
    setTimeout(callback) { timers.push(callback); },
    chrome: {runtime: {async sendMessage(items) {
      calls.push(JSON.parse(JSON.stringify(items)));
      return {ok: calls.length > 1};
    }}},
  });
  function message(id, at, incoming) {
    return {incoming, dataset: {messageId: id}, querySelector(selector) {
      assert.equal(selector, "time[datetime]");
      return {dateTime: new Date(at).toISOString()};
    }};
  }
  rows.push(message("history", opened-1, true), message("own", opened, false));
  await timers.shift()();
  assert.equal(calls.length, 0);
  rows.push(message("arrival", opened, true));
  mutated();
  await timers.shift()();
  await timers.shift()();
  await timers.shift()();
  assert.deepEqual(calls, Array(2).fill([{id: "arrival", at: opened}]));
  location.pathname = "/c/ordinary-chat";
  rows.push(message("other", opened, true));
  mutated();
  await timers.shift()();
  assert.equal(calls.length, 2);
});
