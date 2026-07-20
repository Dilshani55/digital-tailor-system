import React from 'react';

export default function ImageUploader() {
  return (
    <div style={{ border: '2px dashed #ccc', padding: '2rem', textAlign: 'center' }}>
      <p>Upload Front-View Design Photo (Blouse / T-Shirt / Crop Top)</p>
      <input type="file" accept="image/*" />
    </div>
  );
}
