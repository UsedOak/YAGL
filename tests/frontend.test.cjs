const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

// Exercise the real state-loading and socket handlers with controlled network timing.
function browser() {
  const requests = [], sockets = [], timers = [];
  const element = {addEventListener() {}, classList: {add() {}}};
  const context = vm.createContext({
    document: {getElementById: () => element, addEventListener() {}},
    window: {addEventListener() {}},
    localStorage: {getItem() {return '';}, setItem() {}, removeItem() {}},
    location: {protocol: 'http:', host: 'localhost'},
    setTimeout(fn) {timers.push(fn); return timers.length;}, clearTimeout() {}, setInterval() {},
    fetch(url) {return new Promise((resolve, reject) => requests.push({url, resolve, reject}));},
    WebSocket: class {
      constructor() {this.handlers = {}; sockets.push(this);}
      addEventListener(name, fn) {this.handlers[name] = fn;}
    },
  });
  const source = fs.readFileSync(path.join(__dirname, '../frontend/app.js'), 'utf8');
  vm.runInContext(source, context);
  vm.runInContext('render = () => {};', context);
  const run = code => vm.runInContext(code, context);
  const respond = (index, payload) => requests[index].resolve({ok: true, json: async () => payload});
  return {requests, sockets, timers, run, respond};
}

test('an older store response cannot replace the selected store or current list', async () => {
  const b = browser();
  b.run("selectedStore = '2'");
  const latest = b.run('loadState()');
  b.respond(1, {stores: [{id: 2}], items: [{name: 'Newest'}]});
  await latest;
  b.respond(0, {stores: [], items: [{name: 'Stale'}]});
  await new Promise(setImmediate);
  assert.equal(b.run('selectedStore'), '2');
  assert.equal(b.run('currentState.items[0].name'), 'Newest');
  assert.equal(b.requests.length, 2);
});

test('overlapping refreshes for the same store keep the newest response', async () => {
  const b = browser();
  const latest = b.run('loadState()');
  b.respond(1, {stores: [], items: [{quantity: 3}]});
  await latest;
  b.respond(0, {stores: [], items: [{quantity: 1}]});
  await new Promise(setImmediate);
  assert.equal(b.run('currentState.items[0].quantity'), 3);
});

test('deleted selected stores fall back to a fresh simple-list snapshot', async () => {
  const b = browser();
  b.run("selectedStore = '2'");
  const latest = b.run('loadState()');
  b.respond(1, {stores: [], items: []});
  await new Promise(setImmediate);
  assert.equal(b.requests[2].url, '/api/state');
  b.respond(2, {stores: [], items: [{name: 'Milk'}]});
  await latest;
  assert.equal(b.run('selectedStore'), '');
  assert.equal(b.run('currentState.items[0].name'), 'Milk');
});

test('socket ready refreshes changes missed while disconnected', () => {
  const b = browser();
  b.sockets[0].handlers.message({data: JSON.stringify({type: 'ready'})});
  assert.equal(b.timers.length, 1);
  b.timers[0]();
  assert.equal(b.requests.length, 2);
});
