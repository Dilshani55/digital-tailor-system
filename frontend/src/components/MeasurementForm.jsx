import React from 'react';

export default function MeasurementForm() {
  return (
    <form style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxWidth: '400px', margin: '0 auto' }}>
      <label>Bust (cm): <input type="number" name="bust" placeholder="e.g. 88" /></label>
      <label>Waist (cm): <input type="number" name="waist" placeholder="e.g. 70" /></label>
      <label>Hip (cm): <input type="number" name="hip" placeholder="e.g. 96" /></label>
      <label>Height (cm): <input type="number" name="height" placeholder="e.g. 165" /></label>
    </form>
  );
}
