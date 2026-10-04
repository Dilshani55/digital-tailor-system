// Separate drafts per account/workflow, including the original photo File.
// The active draft marker survives refresh, but is cleared when leaving /upload.
const DATABASE = 'tailorai-wizard';
const STORE = 'drafts';
const VERSION = 1;
const ACTIVE = 'tailorai-active-pattern-draft';

export function createWizardDraftId() {
  return globalThis.crypto?.randomUUID?.() || `draft-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function activeWizardDraft(owner) {
  try {
    const active = JSON.parse(sessionStorage.getItem(ACTIVE) || 'null');
    return active?.owner === owner ? active.id : null;
  } catch { return null; }
}

export function activateWizardDraft(owner, id) {
  try { sessionStorage.setItem(ACTIVE, JSON.stringify({ owner, id })); } catch { /* Explicit resume still works. */ }
}

export function clearActiveWizardDraft() {
  try { sessionStorage.removeItem(ACTIVE); } catch { /* Storage may be disabled. */ }
}

export function wizardOwner() {
  try {
    const user = JSON.parse(localStorage.getItem('user') || 'null');
    return user?.id || user?.email || 'guest';
  } catch {
    return 'guest';
  }
}

// Serialize reads/writes/resets so an older pending save cannot overwrite newer
// answers, resurrect a cleared draft, or race a read during navigation.
let pending = Promise.resolve();
function transaction(owner, mode, operation) {
  const result = pending.catch(() => {}).then(() => runTransaction(owner, mode, operation));
  pending = result;
  return result;
}

async function runTransaction(owner, mode, operation) {
  const db = await new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE, VERSION);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error('Draft storage is unavailable.'));
  });
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const request = operation(tx.objectStore(STORE), owner);
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error('Draft storage was interrupted.'));
    });
  } finally {
    db.close();
  }
}

const draftKey = (owner, id) => !id || id === 'legacy' ? owner : [owner, id];
const validRecord = (record) => record?.version === VERSION && record.values && typeof record.values === 'object'
  && Number.isInteger(record.values.step) && record.values.step >= 1 && record.values.step <= 8;

export async function readWizardDraft(owner, id) {
  const record = await transaction(owner, 'readonly', (store) => store.get(draftKey(owner, id)));
  return validRecord(record) ? record.values : null;
}

export async function listWizardDrafts(owner) {
  const records = await transaction(owner, 'readonly', (store) => store.getAll(IDBKeyRange.bound([owner, ''], [owner, '\uffff'])));
  // Older installations used the account ID as the key. Keep that draft available.
  const legacy = await transaction(owner, 'readonly', (store, key) => store.get(key));
  if (validRecord(legacy)) records.push({ ...legacy, id: 'legacy' });
  return records.filter(validRecord).map((record) => ({ id: record.id, savedAt: record.savedAt || null,
    clientName: record.values.meas?.client_name || 'Unnamed customer', projectName: record.values.projectName || '',
    step: record.values.step })).sort((a, b) => (b.savedAt || '').localeCompare(a.savedAt || ''));
}

export function saveWizardDraft(owner, values, id) {
  return transaction(owner, 'readwrite', (store) => store.put({ version: VERSION, id: id || 'legacy',
    savedAt: new Date().toISOString(), values }, draftKey(owner, id)));
}

export function clearWizardDraft(owner, id) {
  return transaction(owner, 'readwrite', (store) => store.delete(draftKey(owner, id)));
}
