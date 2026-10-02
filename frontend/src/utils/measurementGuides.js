// How to take each measurement, in plain words. The text lives in backend/config/measurement_requirements.json
// (one source for the app, the PDF and the documentation).
import { MEASUREMENT_FIELDS } from './measurementSchema';

export const GUIDES = Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, f.guide]));
export const MISTAKES = Object.fromEntries(MEASUREMENT_FIELDS.map((f) => [f.key, f.mistake]));
