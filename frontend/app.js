/* YAGL alpha: one shared list, browser-local store selection. No frameworks or trackers. */
'use strict';
const $ = (id) => document.getElementById(id);
const escapeHTML = (x) => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const selectedStoreKey = 'yagl.selectedStore.v1';
let selectedStore = localStorage.getItem(selectedStoreKey) || '';
let currentState = null;
let page = 'shopping';
let activeTab = 'stores';
let socket = null;
let retryTimer = null;
let refreshTimer = null;
let importPayload = null;
let toastTimer = null;

function showToast(message, error = false) {
  const el = $('notification'); el.textContent = message;
  el.className = 'toast' + (error ? ' error' : '');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.add('hidden'), 4200);
}
async function api(path, method = 'GET', payload = undefined) {
  const options = {method, headers: payload === undefined ? {} : {'Content-Type': 'application/json'}};
  if (payload !== undefined) options.body = JSON.stringify(payload);
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const err = new Error(data.detail || `Request failed (${response.status})`); err.data = data; err.status = response.status; throw err; }
  return data;
}
async function mutate(path, method, payload) {
  try { const result = await api(path, method, payload); await loadState(); return result; }
  catch (err) { showToast(err.message, true); throw err; }
}
function scheduleRefresh() { clearTimeout(refreshTimer); refreshTimer = setTimeout(() => loadState(), 120); }
async function loadState() {
  try {
    const response = await api('/api/state' + (selectedStore ? '?store_id=' + encodeURIComponent(selectedStore) : ''));
    if (selectedStore && !response.stores.some(s => String(s.id) === String(selectedStore))) {
      selectedStore = ''; localStorage.removeItem(selectedStoreKey);
      currentState = await api('/api/state');
    } else currentState = response;
    render();
  } catch (e) { showToast('Could not load the list: ' + e.message, true); }
}
function connectLive() {
  clearTimeout(retryTimer);
  if (socket && socket.readyState === WebSocket.OPEN) socket.close();
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  socket = new WebSocket(protocol + '//' + location.host + '/api/live');
  socket.addEventListener('open', () => setOnline(true));
  socket.addEventListener('message', event => { try {if (JSON.parse(event.data).type === 'changed') scheduleRefresh();} catch {} });
  socket.addEventListener('close', () => {setOnline(false); retryTimer = setTimeout(connectLive, 3500);});
  socket.addEventListener('error', () => socket.close());
}
function setOnline(online) {
  $('connection').className = 'connection ' + (online ? 'online' : 'offline');
  $('connectionText').textContent = online ? 'Live sync on' : 'Reconnecting';
}
function render() {
  if (!currentState) return;
  const select = $('storePicker');
  const opts = '<option value="">Simple list · No store</option>' + currentState.stores.map(s => `<option value="${s.id}">${escapeHTML(s.name)}${s.location ? ' · ' + escapeHTML(s.location) : ''}</option>`).join('');
  if (select.innerHTML !== opts) select.innerHTML = opts;
  select.value = selectedStore;
  if (page === 'shopping') renderShopping(); else renderSettings();
}
function renderShopping() {
  const items = currentState.items;
  const checked = items.filter(x => x.checked).length;
  $('listSummary').textContent = `${items.length} item${items.length === 1 ? '' : 's'} on the list · ${checked} picked up`;
  $('footerCount').textContent = `${items.length - checked} remaining`;
  $('doneBtn').disabled = checked === 0;
  $('progress').setAttribute('aria-valuenow', String(items.length ? Math.round(checked / items.length * 100) : 0));
  $('progressBar').style.width = `${items.length ? checked / items.length * 100 : 0}%`;
  if (!items.length) {
    $('shoppingItems').innerHTML = `<div class="empty-state"><div class="empty-graphic">🛒</div><strong>Nothing on the list. Yet.</strong><p>Add your first item above. No setup required.</p></div>`;
  } else {
    const groups = new Map();
    for (const item of items) {
      const key = selectedStore && item.aisle_id ? String(item.aisle_id) : 'unmapped';
      if (!groups.has(key)) groups.set(key, {heading: selectedStore ? (item.aisle_code ? `${item.aisle_code}${item.aisle_description ? ' · ' + item.aisle_description : ''}` : 'Unmapped items') : 'Your items', items: []});
      groups.get(key).items.push(item);
    }
    $('shoppingItems').innerHTML = [...groups.values()].map(group => `
      <div class="group-title"><span class="group-location">${escapeHTML(group.heading)}</span></div>
      ${group.items.map(item => `<div class="shopping-row ${item.checked ? 'is-checked' : ''}" data-item="${item.id}">
        <label class="custom-check" aria-label="${escapeHTML('Mark ' + item.name + ' picked up')}"><input type="checkbox" data-check="${item.id}" ${item.checked ? 'checked' : ''}></label>
        <div class="item-name">${escapeHTML(item.name)}${item.category_name && selectedStore ? `<div class="item-sub">${escapeHTML(item.category_name)}</div>` : ''}</div>
        <div class="quantity-controls">${item.quantity > 1 ? `<button class="icon-btn" type="button" data-decrement="${item.id}" aria-label="Reduce quantity of ${escapeHTML(item.name)}">−</button><span class="quantity-number">${item.quantity}</span>` : ''}
          <button class="icon-btn" type="button" data-increment="${item.id}" aria-label="Increase quantity of ${escapeHTML(item.name)}">+</button></div>
        <button class="item-edit" type="button" data-edit-item="${item.id}" aria-label="Edit ${escapeHTML(item.name)}" title="Edit item and remember its category or location">⋯</button>
      </div>`).join('')}`).join('');
  }
  if (!selectedStore) {
    $('routeSummary').innerHTML = '<div class="info-box">Select a store to organize items by aisle, or keep using this as a simple list.</div><p class="muted">You can configure stores, aisles, and category locations anytime in Settings.</p>';
  } else {
    const layout = currentState.layout;
    const mapped = items.filter(x => x.aisle_id);
    const steps = new Map();
    for (const item of mapped) {
      if (!steps.has(item.aisle_id)) steps.set(item.aisle_id, {code: item.aisle_code, description: item.aisle_description, count: 0});
      if (!item.checked) steps.get(item.aisle_id).count++;
    }
    $('routeSummary').innerHTML = `<div class="label-chip">${escapeHTML(layout?.store.name || 'Store')}</div>` +
      (steps.size ? [...steps.values()].map((step, i) => `<div class="route-step"><span class="route-step-count">${i+1}</span><span class="route-step-info">${escapeHTML(step.code)}<small>${escapeHTML(step.description || 'Mapped aisle')}</small></span><span class="route-step-total">${step.count} left</span></div>`).join('') : '<p class="muted">Map a category or product to an aisle to see a shopping route here.</p>') +
      (items.length - mapped.length ? `<p class="muted">${items.length - mapped.length} item(s) have no aisle assigned at this store.</p>` : '');
  }
}
function selectStore(value) {selectedStore = value; if (value) localStorage.setItem(selectedStoreKey, value); else localStorage.removeItem(selectedStoreKey); loadState();}
function openSettings(tab) {page = 'settings'; activeTab = tab || 'stores'; $('shoppingPage').classList.add('hidden'); $('settingsPage').classList.remove('hidden'); renderSettings(); window.scrollTo(0, 0);}
function closeSettings() {page = 'shopping'; $('settingsPage').classList.add('hidden'); $('shoppingPage').classList.remove('hidden'); renderShopping(); window.scrollTo(0, 0);}
function selectedLayout() {return currentState?.layout;}
function storeHint() {return selectedStore ? '' : `<div class="empty-compact">Create or choose a store in the shopping view to configure its layout.</div>`;}
function aisleOptions(value, includeUnmapped = true) {
  const aisles = selectedLayout()?.aisles || [];
  return (includeUnmapped ? '<option value="">Not assigned</option>' : '') + aisles.map(a => `<option value="${a.id}" ${String(value ?? '') === String(a.id) ? 'selected' : ''}>${escapeHTML(a.code)}${a.description ? ' · ' + escapeHTML(a.description) : ''}</option>`).join('');
}
function renderSettings() {
  if (!currentState) return;
  document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === activeTab));
  let html = '';
  switch (activeTab) {
    case 'stores': html = renderStoresSettings(); break;
    case 'aisles': html = renderAislesSettings(); break;
    case 'categories': html = renderCategoriesSettings(); break;
    case 'transfer': html = renderTransferSettings(); break;
  }
  $('settingsContent').innerHTML = html;
}
function renderStoresSettings() {
  return `<h2 class="settings-title">Store profiles</h2><p class="settings-description">Walmart, Trader Joe's, Ace Hardware — any store works. Your selected store only affects the view on this browser.</p>
  <form class="settings-form" id="storeForm"><div class="field"><label for="storeName">STORE NAME</label><input id="storeName" maxlength="120" required placeholder="e.g. Walmart Supercenter"></div>
  <div class="field-row"><div class="field"><label for="storeLocation">LOCATION (OPTIONAL)</label><input id="storeLocation" maxlength="240" placeholder="e.g. Inverness, FL"></div>
  <div class="field"><label for="storeCode">STORE NUMBER (OPTIONAL)</label><input id="storeCode" maxlength="60" placeholder="e.g. #1234"></div></div><div class="form-actions"><button class="btn btn-primary">+ Add store</button></div></form>
  <h3>Configured stores · ${currentState.stores.length}</h3>${currentState.stores.length ? currentState.stores.map(s => `<div class="settings-item"><div class="settings-item-main"><div class="settings-item-title">${escapeHTML(s.name)}${String(s.id) === String(selectedStore) ? ' <span class="label-chip">Current view</span>' : ''}</div><div class="settings-item-meta">${escapeHTML([s.location, s.store_code].filter(Boolean).join(' · ') || 'No location set')}</div></div><button type="button" class="btn btn-outline btn-small" data-choose-store="${s.id}">Use</button><button type="button" class="btn btn-outline btn-small" data-edit-store="${s.id}">Edit</button><button type="button" class="btn btn-danger btn-small" data-delete-store="${s.id}">Delete</button></div>`).join('') : '<div class="empty-compact">No stores configured. The shopping list still works just fine.</div>'}
  <div class="info-box" style="margin-top:22px">Switching stores never creates a new list. Every device continues to work from the same shared shopping list.</div>`;
}
function renderAislesSettings() {
  if (!selectedStore) return `<h2 class="settings-title">Walking order</h2><p class="settings-description">Map your store from the beginning of your trip to checkout.</p>${storeHint()}`;
  const aisles = selectedLayout()?.aisles || [];
  return `<h2 class="settings-title">Walking order</h2><p class="settings-description">Aisles are sorted in the exact sequence below — not alphabetically. Put dry goods first and frozen goods last if that's how you prefer to shop.</p>
  <div class="info-box">Editing <strong>${escapeHTML(selectedLayout().store.name)}</strong>. Use ↑ and ↓ to arrange your walking route. Other devices can select different stores.</div>
  <form id="aisleForm" class="settings-form"><div class="field-row"><div class="field"><label for="aisleCode">AISLE / ZONE</label><input id="aisleCode" maxlength="50" required placeholder="A7 or Dairy"></div><div class="field"><label for="aisleDescription">DESCRIPTION (OPTIONAL)</label><input id="aisleDescription" maxlength="120" placeholder="Canned goods"></div></div><div class="form-actions"><button class="btn btn-primary">+ Add location</button></div></form>
  <h3>Beginning of trip → Checkout</h3>${aisles.length ? aisles.map((a, index) => `<div class="settings-item"><div class="move-buttons"><button type="button" class="icon-btn" data-move="${a.id}" data-direction="-1" ${index === 0 ? 'disabled' : ''} aria-label="Move ${escapeHTML(a.code)} earlier">↑</button><button type="button" class="icon-btn" data-move="${a.id}" data-direction="1" ${index === aisles.length - 1 ? 'disabled' : ''} aria-label="Move ${escapeHTML(a.code)} later">↓</button></div><div class="settings-item-main"><div class="settings-item-title"><span class="label-chip">${index+1}</span> ${escapeHTML(a.code)}</div><div class="settings-item-meta">${escapeHTML(a.description || 'No description')}</div></div><button type="button" class="btn btn-outline btn-small" data-edit-aisle="${a.id}">Edit</button><button type="button" class="btn btn-danger btn-small" data-delete-aisle="${a.id}">×</button></div>`).join('') : '<div class="empty-compact">No aisles yet. Add your first location above.</div>'}`;
}
function renderCategoriesSettings() {
  const mapping = Object.fromEntries((selectedLayout()?.category_locations || []).map(m => [m.category_id, m.aisle_id]));
  return `<h2 class="settings-title">Categories & memory</h2><p class="settings-description">YAGL remembers product categories and their aisle at each store. Words and phrases below help new items inherit a category automatically.</p>
  <form id="categoryForm" class="settings-form"><div class="field"><label for="categoryName">NEW CATEGORY</label><input id="categoryName" maxlength="120" required placeholder="e.g. Pasta & Sauces"></div><div class="field"><label for="categoryKeywords">MATCHING WORDS (OPTIONAL, COMMA-SEPARATED)</label><input id="categoryKeywords" placeholder="pasta, spaghetti, penne"></div><div class="form-actions"><button class="btn btn-primary">+ Add category</button></div></form>
  <h3>Known categories · ${currentState.categories.length}</h3>${!selectedStore ? '<div class="info-box">Select a store from the shopping view to assign aisle locations. Categories themselves are shared between all stores.</div>' : ''}
  ${currentState.categories.map(c => `<div class="settings-item"><div class="settings-item-main"><div class="settings-item-title">${escapeHTML(c.name)}</div><div class="settings-item-meta">${escapeHTML(c.keywords.join(', ') || 'No matching words configured')}</div></div>${selectedStore ? `<select class="text-input" aria-label="Aisle for ${escapeHTML(c.name)}" data-map-category="${c.id}">${aisleOptions(mapping[c.id])}</select>` : ''}<button type="button" class="btn btn-outline btn-small" data-edit-category="${c.id}">Edit</button></div>`).join('')}`;
}
function renderTransferSettings() {
  if (!selectedStore) return `<h2 class="settings-title">Import & export</h2><p class="settings-description">Share complete aisle layouts as portable JSON files.</p>${storeHint()}`;
  return `<h2 class="settings-title">Import & export</h2><p class="settings-description">Store profiles travel between YAGL installations. Imports and exports use the same versioned JSON format and include aisle order, category mappings, product exceptions, and remembered product categories. Your shopping list is never included.</p>
  <div class="warning-box"><strong>⚠ Back up your existing layout first.</strong><br>Before importing, export your current configuration. An import may change aisle assignments, category locations, and walking order. Keep the backup so you can restore it if you're not happy with the result.</div>
  <h3>1. Export current store</h3><div class="setting-buttons"><a class="btn btn-primary" style="text-decoration:none" href="/api/stores/${selectedStore}/export" download>↓ Download JSON backup</a></div>
  <h3>2. Import a layout</h3><div class="field"><label for="importFile">YAGL STORE CONFIGURATION (.JSON)</label><input id="importFile" class="text-input" type="file" accept=".json,application/json"></div>
  <div id="importPreview">${importPayload ? '<p class="muted">An import file has been selected. Preview it again to review what will change.</p>' : ''}</div>
  <div class="setting-buttons"><button type="button" class="btn btn-outline" id="previewImportBtn">Preview import</button></div>
  <div class="info-box" style="margin-top:20px">Merge adds missing mappings without overwriting existing aisle order. Replace replaces this store's aisle layout and mappings but leaves the shared shopping list untouched. Neither changes other store profiles.</div>`;
}
async function addItem(event) {
  event.preventDefault(); const input = $('newItem'); const name = input.value.trim(); if (!name) return;
  try {
    await mutate('/api/items', 'POST', {name}); input.value = ''; input.focus();
  } catch (error) {
    if (error.status === 409 && error.data?.existing_id) {
      if (confirm(`"${name}" is already on your list. Increase its quantity by one?`)) {
        const existing = currentState?.items.find(x => x.id === error.data.existing_id);
        try { await mutate(`/api/items/${error.data.existing_id}`, 'PATCH', {quantity: (existing?.quantity || error.data.quantity) + 1, checked: false}); input.value = ''; } catch {}
      }
    }
  }
}
function editItem(id) {
  const item = currentState.items.find(i => i.id === id); if (!item) return;
  const productOverride = selectedLayout()?.product_locations.find(p => p.product_name.toLowerCase() === item.name.toLowerCase());
  $('itemDialogContents').innerHTML = `<h2>Edit item</h2><p>Remember its category for future lists. Locations are saved for the selected store only.</p>
  <input type="hidden" id="editId" value="${id}"><div class="field"><label for="editName">ITEM</label><input id="editName" maxlength="120" required value="${escapeHTML(item.name)}"></div>
  <div class="field"><label for="editCategory">CATEGORY (SHARED BETWEEN STORES)</label><select id="editCategory"><option value="">Not assigned</option>${currentState.categories.map(c => `<option value="${c.id}" ${c.id === item.category_id ? 'selected' : ''}>${escapeHTML(c.name)}</option>`).join('')}</select></div>
  ${selectedStore ? `<div class="field"><label for="editAisle">THIS STORE'S AISLE / ZONE</label><select id="editAisle">${aisleOptions(item.aisle_id)}</select></div><label class="checkbox-explain"><input type="checkbox" id="saveToCategory"> Save aisle for the entire selected category (instead of only this product)</label><p>Category mapping changes every item inheriting that category at this store. A product-only assignment takes priority over its category.</p>` : '<div class="info-box">Choose a store to teach YAGL where this item is located.</div>'}
  <div class="form-actions"><button type="button" class="btn btn-danger" id="deleteItemBtn">Remove item</button><button type="button" class="btn btn-outline" id="cancelEditBtn">Cancel</button><button type="submit" class="btn btn-primary">Save</button></div>`;
  $('itemDialog').showModal();
}
async function saveEditedItem(event) {
  event.preventDefault();
  const id = Number($('editId').value), item = currentState.items.find(i => i.id === id);
  const name = $('editName').value.trim(), categoryId = $('editCategory').value ? Number($('editCategory').value) : null;
  if (!name) return;
  try {
    await mutate(`/api/items/${id}`, 'PATCH', {name, category_id: categoryId});
    if (selectedStore) {
      const aisle = $('editAisle').value ? Number($('editAisle').value) : null;
      if ($('saveToCategory').checked && categoryId) {
        await mutate(`/api/stores/${selectedStore}/categories/${categoryId}`, 'PUT', {aisle_id: aisle});
        // Explicitly clear any product override so the new category mapping is inherited.
        await mutate(`/api/stores/${selectedStore}/products`, 'PUT', {product_name: name, aisle_id: null});
      } else {
        const priorOverride = selectedLayout()?.product_locations.find(p => p.product_name.toLowerCase() === item.name.toLowerCase());
        const priorMapped = item.aisle_id || null;
        if (aisle !== priorMapped || priorOverride) {
          await mutate(`/api/stores/${selectedStore}/products`, 'PUT', {product_name: name, aisle_id: aisle});
        }
      }
    }
    $('itemDialog').close(); showToast('Item saved. YAGL will remember its category and location.');
  } catch { /* mutate already reports error */ }
}
async function submitStore(event) {
  event.preventDefault();
  try { const result = await mutate('/api/stores', 'POST', {name:$('storeName').value, location:$('storeLocation').value, store_code:$('storeCode').value}); selectedStore = String(result.id); localStorage.setItem(selectedStoreKey, selectedStore); await loadState(); showToast('Store added. Map its aisles whenever you like.'); } catch {}
}
async function submitAisle(event) {
  event.preventDefault(); if (!selectedStore) return;
  try {await mutate(`/api/stores/${selectedStore}/aisles`, 'POST', {code:$('aisleCode').value, description:$('aisleDescription').value}); showToast('Location added to the end of your route.');} catch {}
}
async function submitCategory(event) {
  event.preventDefault();
  try {await mutate('/api/categories', 'POST', {name:$('categoryName').value, keywords:$('categoryKeywords').value}); showToast('Category saved.');} catch {}
}
async function moveAisle(id, direction) {
  const aisles = selectedLayout()?.aisles || [], list = aisles.map(a=>a.id), i=list.indexOf(id), j=i+direction;
  if (i<0 || j<0 || j>=list.length) return;
  [list[i],list[j]]=[list[j],list[i]];
  try {await mutate(`/api/stores/${selectedStore}/aisles/order`, 'PUT', {ids:list});} catch {}
}
async function previewImport() {
  const file = $('importFile').files[0];
  if (!file) {showToast('Choose a JSON file first.', true);return;}
  if (file.size > 1024*512) {showToast('Layout file exceeds the 512 KB limit.', true);return;}
  try {
    importPayload = JSON.parse(await file.text());
    const result = await api(`/api/stores/${selectedStore}/import/preview`, 'POST', {payload:importPayload});
    $('importPreview').innerHTML = `<div class="info-box"><b>Ready to import: ${escapeHTML(result.from_store)}</b><p>${result.aisles} aisles · ${result.category_locations} category locations · ${result.product_locations} product exceptions · ${result.product_categories} remembered product categories</p><p>Target: ${escapeHTML(selectedLayout().store.name)}</p></div>
    <div class="field"><label for="importMode">IMPORT BEHAVIOR</label><select id="importMode"><option value="merge">Merge · Keep my existing mappings</option><option value="replace">Replace · Replace this store's layout</option></select></div>
    <button type="button" class="btn btn-primary" id="applyImportBtn">Apply import to this store</button>`;
  } catch (err) {importPayload=null; $('importPreview').innerHTML=''; showToast('Import preview failed: ' + err.message, true);}
}
async function applyImport() {
  if (!importPayload) return;
  const mode = $('importMode').value;
  if (!confirm(`Import this layout using ${mode.toUpperCase()} mode? Have you downloaded a backup of your current configuration?`)) return;
  try {await mutate(`/api/stores/${selectedStore}/import`, 'POST', {mode, payload:importPayload}); importPayload=null; showToast('Store layout imported successfully.');} catch {}
}
$('addForm').addEventListener('submit', addItem);
$('storePicker').addEventListener('change', e => selectStore(e.target.value));
$('settingsBtn').addEventListener('click', () => page==='shopping' ? openSettings() : closeSettings());
$('backBtn').addEventListener('click', closeSettings);
$('homeLink').addEventListener('click', e => {e.preventDefault();closeSettings();});
$('doneBtn').addEventListener('click', async () => {
  const checked = currentState.items.filter(i=>i.checked).length;
  if (!checked) return;
  try {const result=await mutate('/api/items/clear-completed', 'POST'); showToast(`${result.removed} checked item${result.removed===1?'':'s'} cleared. Unchecked items remain.`);} catch {}
});
$('itemEditForm').addEventListener('submit', saveEditedItem);
$('itemDialog').addEventListener('click', e => {if (e.target === $('itemDialog')) $('itemDialog').close();});
document.addEventListener('change', async e => {
  const el = e.target;
  if (el.matches('[data-check]')) {try {await mutate(`/api/items/${Number(el.dataset.check)}`, 'PATCH', {checked:el.checked});}catch {await loadState();}}
  if (el.matches('[data-map-category]')) {try {await mutate(`/api/stores/${selectedStore}/categories/${Number(el.dataset.mapCategory)}`, 'PUT', {aisle_id:el.value ? Number(el.value) : null});}catch {}}
});
document.addEventListener('submit', async e => {
  if (e.target.id === 'storeForm') submitStore(e);
  if (e.target.id === 'aisleForm') submitAisle(e);
  if (e.target.id === 'categoryForm') submitCategory(e);
});
document.addEventListener('click', async e => {
  const target = e.target.closest('button'); if (!target) return;
  if (target.dataset.tab) {activeTab=target.dataset.tab;renderSettings();return;}
  if (target.dataset.increment) {const id=Number(target.dataset.increment),item=currentState.items.find(i=>i.id===id);if(item) {try {await mutate(`/api/items/${id}`, 'PATCH', {quantity:Math.min(item.quantity+1,9999)});}catch {}}}
  if (target.dataset.decrement) {const id=Number(target.dataset.decrement),item=currentState.items.find(i=>i.id===id);if(item&&item.quantity>1) {try {await mutate(`/api/items/${id}`, 'PATCH', {quantity:item.quantity-1});}catch {}}}
  if (target.dataset.editItem) editItem(Number(target.dataset.editItem));
  if (target.dataset.chooseStore) {selectStore(target.dataset.chooseStore);showToast('Store selected for this browser.');}
  if (target.dataset.move) moveAisle(Number(target.dataset.move),Number(target.dataset.direction));
  if (target.dataset.editStore) {
    const s=currentState.stores.find(x=>x.id===Number(target.dataset.editStore));if (!s) return;
    const name=prompt('Store name',s.name);if(name===null)return;
    const location=prompt('Location (optional)',s.location);if(location===null)return;
    const store_code=prompt('Store number (optional)',s.store_code);if(store_code===null)return;
    try {await mutate(`/api/stores/${s.id}`, 'PATCH', {name,location,store_code});}catch {}
  }
  if (target.dataset.deleteStore) {
    const id=Number(target.dataset.deleteStore);
    if(confirm('Permanently delete this store and all of its aisle mappings? Your shared shopping list will remain untouched.')) {try {await mutate(`/api/stores/${id}`, 'DELETE');}catch {}}
  }
  if (target.dataset.editAisle) {
    const a=selectedLayout()?.aisles.find(x=>x.id===Number(target.dataset.editAisle));if(!a)return;
    const code=prompt('Aisle / zone',a.code);if(code===null)return;
    const description=prompt('Description (optional)',a.description);if(description===null)return;
    try {await mutate(`/api/stores/${selectedStore}/aisles/${a.id}`, 'PATCH', {code,description});}catch {}
  }
  if (target.dataset.deleteAisle) {
    const id=Number(target.dataset.deleteAisle);if(confirm('Delete this aisle? Its category and product mappings at this store will be cleared.')) {try {await mutate(`/api/stores/${selectedStore}/aisles/${id}`, 'DELETE');}catch {}}
  }
  if (target.dataset.editCategory) {
    const c=currentState.categories.find(x=>x.id===Number(target.dataset.editCategory));if(!c)return;
    const name=prompt('Category name',c.name);if(name===null)return;
    const keywords=prompt('Matching words, separated by commas',c.keywords.join(', '));if(keywords===null)return;
    try {await mutate(`/api/categories/${c.id}`, 'PATCH', {name,keywords});}catch {}
  }
  if (target.id === 'cancelEditBtn') $('itemDialog').close();
  if (target.id === 'deleteItemBtn') {const id=Number($('editId').value);if(confirm('Remove this item from the shopping list?')) {try {await mutate(`/api/items/${id}`, 'DELETE');$('itemDialog').close();}catch {}}}
  if (target.id === 'previewImportBtn') previewImport();
  if (target.id === 'applyImportBtn') applyImport();
});
window.addEventListener('focus', scheduleRefresh);
document.addEventListener('visibilitychange', () => {if (!document.hidden) scheduleRefresh();});
// Fallback for devices with interrupted WebSocket connections.
setInterval(() => {if (!document.hidden) scheduleRefresh();}, 30000);
loadState(); connectLive();
