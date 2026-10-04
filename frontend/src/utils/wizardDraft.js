// One resumable draft per account. IndexedDB keeps the original photo as a File,
// along with inputs/results; blob preview URLs and in-flight requests are not saved.
const DATABASE = 'tailorai-wizard';
const STORE = 'drafts';
const VERSION = 1;

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

export async function readWizardDraft(owner) {
  const record = await transaction(owner, 'readonly', (store, key) => store.get(key));
  if (record?.version !== VERSION || !record.values || typeof record.values !== 'object'
      || !Number.isInteger(record.values.step) || record.values.step < 1 || record.values.step > 8) return null;
  return record.values;
}

export function saveWizardDraft(owner, values) {
  return transaction(owner, 'readwrite', (store, key) => store.put({ version: VERSION, values }, key));
}

export function clearWizardDraft(owner) {
  return transaction(owner, 'readwrite', (store, key) => store.delete(key));
}
