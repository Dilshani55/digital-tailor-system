// Turns API / network failures into plain-language messages. Never shows stack traces,
// file-system paths or raw exception text to the user.

const BY_CODE = {
  UNSUPPORTED_DESIGN: 'This garment design is outside what the system can draft. Please choose a supported option in the design review step.',
  DESIGN_NOT_CONFIRMED: 'Please review and confirm the garment design first.',
  CONFIRMED_DESIGN_MISMATCH: 'The design on screen differs from the one saved. Please confirm the design again.',
  FABRIC_ID_REQUIRED: 'Please choose a fabric before generating the pattern.',
  INVALID_FABRIC_ID: 'That fabric is not in the catalogue. Please choose another one.',
  DESIGN_MEASUREMENT_CONFLICT: 'Your garment length does not match the chosen garment type. Adjust the garment length or the garment type.',
  MEASUREMENTS_NOT_DRAFTABLE: 'These measurements cannot be drafted into a pattern. Please double-check them.',
  SLEEVE_TOO_WIDE_FOR_ARMHOLE: 'The sleeve is too wide for the armhole. Please check the bicep, armhole depth and bust measurements.',
  PIECE_DOES_NOT_FIT: 'A pattern piece is wider than the fabric. Choose a wider fabric or lay the fabric out open.',
  INVALID_FABRIC_WIDTH: 'Please choose a valid fabric width.',
  MODEL_UNAVAILABLE: 'The AI garment model is not available right now, so the photo cannot be analysed. You can still choose the design manually.',
  IMAGE_NOT_ANALYSABLE: 'This photo could not be analysed. Try another photo or choose the design manually.',
  PATTERN_NOT_VALID: 'This pattern failed its automatic checks, so it has no fabric estimate to compare.',
  FINAL_PATTERN_INVALID: 'The generated pattern did not pass the automatic geometry checks, so it was not created.',
};

const LEAKY = /Traceback|File "|\bat [\w.]+\(|[A-Za-z]:\|\/usr\/|\/home\/|node_modules|site-packages/;

export function friendlyError(err, fallback = 'Something went wrong. Please try again.') {
  if (!err) return fallback;
  if (err.code === 'ERR_NETWORK' || (!err.response && err.request)) {
    return 'Cannot reach the server. Check your connection and that the backend is running, then try again.';
  }
  const status = err.response?.status;
  const data = err.response?.data || {};
  if (data.error_code && BY_CODE[data.error_code]) return BY_CODE[data.error_code];
  if (typeof data.error === 'string' && data.error && !LEAKY.test(data.error)) return data.error;
  if (status === 413) return 'That file is too large. Please choose an image under 16 MB.';
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'You do not have permission to do that.';
  if (status === 404) return 'We could not find that item. It may have been removed.';
  if (status >= 500) return 'The server had a problem completing that request. Please try again in a moment.';
  return fallback;
}

export const ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const MAX_IMAGE_BYTES = 16 * 1024 * 1024;

/** Client-side image check; returns a message or ''. The server validates again. */
export function imageProblem(file) {
  if (!file) return 'Please choose a photo of the garment.';
  if (!ALLOWED_IMAGE_TYPES.includes(file.type)) return 'Please choose a JPG, PNG or WEBP photo.';
  if (file.size > MAX_IMAGE_BYTES) return 'That photo is larger than 16 MB. Please choose a smaller one.';
  if (file.size === 0) return 'That file is empty.';
  return '';
}
