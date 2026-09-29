import { Scissors } from 'lucide-react';

export default function LoadingSpinner({ message = "Processing AI calculations..." }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      <div className="relative flex items-center justify-center">
        {/* Outer Pulsing Glow */}
        <div className="w-16 h-16 rounded-full bg-brand-500/20 animate-ping absolute"></div>
        
        {/* Rotating Gradient Spinner */}
        <div className="w-14 h-14 rounded-full border-4 border-slate-200 border-t-brand-500 border-r-emerald-400 animate-spin"></div>
        
        {/* Center Icon */}
        <div className="absolute text-brand-400"><Scissors size={20} /></div>
      </div>
      <p role="status" className="mt-6 text-sm font-semibold tracking-wide" style={{ color: 'var(--text-primary)' }}>
        {message}
      </p>
      <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
        TailorAI
      </p>
    </div>
  );
}
