// Minimal "unsaved changes" guard shared by the wizard and the app navigation.
// The wizard marks work as unsaved while a pattern is being prepared; leaving via the sidebar/header
// or closing the tab then asks for confirmation.
let unsaved = false;

export const UNSAVED_MESSAGE = 'You have an unfinished pattern. Leave this page?';

export function setUnsaved(value) {
  unsaved = Boolean(value);
}

export function hasUnsaved() {
  return unsaved;
}

/** Returns true when navigation may continue. */
export function confirmLeave() {
  if (!unsaved) return true;
  const ok = window.confirm(UNSAVED_MESSAGE);
  if (ok) unsaved = false;
  return ok;
}

export function beforeUnloadHandler(event) {
  if (!unsaved) return undefined;
  event.preventDefault();
  event.returnValue = UNSAVED_MESSAGE;       // required by some browsers to show the prompt
  return UNSAVED_MESSAGE;
}
