// Research integrity: a calculated result is shown only when the backend produced it.
// Otherwise show an honest label — never a plausible-looking substitute number.

export const NOT_CALCULATED = 'Not calculated';
export const CALCULATION_FAILED = 'Calculation failed';

export const hasValue = (value) =>
  !(value === null || value === undefined || value === '' || Number.isNaN(Number(value)));

/** Format a backend result, or return the honest placeholder when it is absent. */
export function formatResult(value, suffix = '', failed = false) {
  if (!hasValue(value)) return failed ? CALCULATION_FAILED : NOT_CALCULATED;
  return `${value}${suffix}`;
}
