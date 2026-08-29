import { useState }          from 'react';
import { AlertCircle, Zap } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth }           from '../context/AuthContext';

export default function Register() {
  const [form,    setForm]    = useState({
    full_name: '', email: '', password: '', confirm: ''
  });
  const [error,   setError]   = useState('');
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate     = useNavigate();

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (form.password !== form.confirm) {
      setError('Passwords do not match'); return;
    }
    setLoading(true);
    try {
      await register(form.full_name, form.email, form.password);
      navigate('/login');
    } catch (err) {
      setError(err.response?.data?.error || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-2 rounded-3xl overflow-hidden glass-panel shadow-2xl border border-slate-800">
        
        {/* Left Info Banner */}
        <div className="bg-gradient-to-br from-slate-900 via-indigo-950/80 to-slate-950 p-8 lg:p-12 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute -top-20 -left-20 w-64 h-64 bg-brand-500/20 rounded-full blur-3xl"></div>
          
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs font-semibold mb-6">
              <Zap size={15}/> Immediate Access
            </div>

            <h1 className="font-display font-extrabold text-3xl text-white leading-tight">
              Join Digital Tailor System
            </h1>
            <p className="text-slate-400 text-sm mt-3 leading-relaxed">
              Create an account to start generating custom clothing drafting guides and calculating fabric yardage.
            </p>
          </div>

          <div className="my-8 space-y-3">
            {[
              "Automated Aldrich 2D Bodice & Sleeve Blocks",
              "2D Fabric Nesting (90cm, 114cm, 150cm rolls)",
              "Downloadable Ready-to-Cut Technical PDF Guides",
            ].map((text, i) => (
              <div key={i} className="flex items-center gap-3 text-xs text-slate-300 font-medium">
                <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">✓</span>
                {text}
              </div>
            ))}
          </div>

          <div className="text-[11px] text-slate-500">
            NSBM Green University — BSc. (Hons) Software Engineering
          </div>
        </div>

        {/* Right Form */}
        <div className="p-8 lg:p-12 flex flex-col justify-center bg-slate-950/60">
          <div className="mb-6">
            <h2 className="font-display font-bold text-2xl text-white">Create Account</h2>
            <p className="text-slate-400 text-xs mt-1">Enter your details to register</p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-3 mb-6 text-xs flex items-center gap-2">
              <AlertCircle size={16}/> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Full Name</label>
              <input
                type="text" name="full_name"
                value={form.full_name} onChange={handleChange} required
                className="w-full glass-input rounded-xl px-4 py-2.5 text-sm focus:outline-none"
                placeholder="Dilshani Vitharana"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
              <input
                type="email" name="email"
                value={form.email} onChange={handleChange} required
                className="w-full glass-input rounded-xl px-4 py-2.5 text-sm focus:outline-none"
                placeholder="dilshani@gmail.com"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Password</label>
                <input
                  type="password" name="password"
                  value={form.password} onChange={handleChange} required
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm focus:outline-none"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Confirm</label>
                <input
                  type="password" name="confirm"
                  value={form.confirm} onChange={handleChange} required
                  className="w-full glass-input rounded-xl px-4 py-2.5 text-sm focus:outline-none"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit" disabled={loading}
              className="w-full mt-2 py-3.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-brand-600 to-indigo-500 hover:from-brand-500 hover:to-indigo-400 shadow-glow-indigo transition-all duration-200 disabled:opacity-50"
            >
              {loading ? 'Creating Account...' : 'Register Account →'}
            </button>
          </form>

          <p className="text-center text-xs text-slate-400 mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-brand-400 font-semibold hover:underline">
              Sign in
            </Link>
          </p>
        </div>

      </div>
    </div>
  );
}
