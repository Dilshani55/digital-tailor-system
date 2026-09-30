// Simple line-art of the three supported garments (an icon, not a picture of the customer's garment).
const PATHS = {
  blouse: 'M38 18 C42 26 58 26 62 18 L72 22 C82 22 89 30 87 41 L75 43 L73 50 C71 60 75 74 77 86 L23 86 C25 74 29 60 27 50 L25 43 L13 41 C11 30 18 22 28 22 Z',
  't-shirt': 'M36 16 L28 19 L11 32 L20 45 L28 40 L28 86 L72 86 L72 40 L80 45 L89 32 L72 19 L64 16 C61 24 39 24 36 16 Z',
  'crop-top': 'M34 12 L39 12 L41 30 C46 35 54 35 59 30 L61 12 L66 12 L68 34 C72 42 74 50 74 60 L26 60 C26 50 28 42 32 34 Z',
};
const DETAILS = {
  blouse: 'M28 22 C27 30 26 37 25 43 M72 22 C73 30 74 37 75 43',
  't-shirt': 'M28 40 L28 26 M72 40 L72 26',
  'crop-top': '',
};

export default function GarmentIllustration({ type, className = 'garment', label }) {
  const key = PATHS[type] ? type : 'blouse';
  return (
    <svg viewBox="0 0 100 100" className={className} role="img" aria-label={label || `${key.replace('-', ' ')} illustration`}>
      <path d={PATHS[key]} fill="#f7f4ec" stroke="#56625b" strokeWidth="1.6" strokeLinejoin="round" />
      {DETAILS[key] && <path d={DETAILS[key]} fill="none" stroke="#9aa39d" strokeWidth="1.1" strokeDasharray="2 2" />}
    </svg>
  );
}
