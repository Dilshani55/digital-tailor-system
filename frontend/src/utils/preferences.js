// Per-device workspace preferences (stored in this browser only, never sent to the server).
// Only settings the app really uses are kept here: the wizard reads them as its starting values.

export const FABRIC_WIDTHS = [90, 114, 150];
export const DEFAULT_PREFERENCES = { unit: 'cm', fabricWidth: 114 };
const KEY = 'tailorai.preferences';

const valid = (p) => ({
  unit: p?.unit === 'in' ? 'in' : 'cm',
  fabricWidth: FABRIC_WIDTHS.includes(Number(p?.fabricWidth)) ? Number(p.fabricWidth) : DEFAULT_PREFERENCES.fabricWidth,
});

export function getPreferences() {
  try {
    return valid(JSON.parse(window.localStorage.getItem(KEY) || 'null') || DEFAULT_PREFERENCES);
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

/** Returns true when the preferences were stored. */
export function savePreferences(prefs) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(valid(prefs)));
    return true;
  } catch {
    return false;
  }
}
