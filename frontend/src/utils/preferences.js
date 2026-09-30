// Per-device workspace preferences (stored in this browser only, never sent to the server).
// Only settings the app really uses are kept here: the wizard reads them as its starting values.

// Standard bolt widths 36", 45", 60" (exact: 1 in = 2.54 cm) — must match the backend STANDARD_FABRIC_WIDTHS.
export const FABRIC_WIDTH_OPTIONS = [
  { inches: 36, cm: 91.44 },
  { inches: 45, cm: 114.3 },
  { inches: 60, cm: 152.4 },
];
export const FABRIC_WIDTHS = FABRIC_WIDTH_OPTIONS.map((w) => w.cm);
export const widthLabel = (cm) => {
  const w = FABRIC_WIDTH_OPTIONS.find((o) => o.cm === Number(cm));
  return w ? `${w.inches}" (${w.cm} cm)` : `${cm} cm`;
};
export const DEFAULT_PREFERENCES = { unit: 'cm', fabricWidth: 114.3 };
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
