import { useState }       from 'react';
import { Bot, AlertCircle, Recycle, Ruler, ScanLine } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth }        from '../context/AuthContext';

export default function Login() {
  const [form,    setForm]    = useState({ email: '', password: '' });
  const [error,   setError]   = useState('');
  const [loading, setLoading] = useState(false);
  const { login }  = useAuth();
  const navigate   = useNavigate();

  const handleChange = (e) =>
    setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(form.email, form.password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4 sm:p-6 lg:p-8">
      <div className="w-full max-w-4xl grid grid-cols-1 lg:grid-cols-2 rounded-3xl overflow-hidden glass-panel shadow-2xl border border-slate-800">
        
        {/* Left Banner: Research & System Branding */}
        <div className="bg-gradient-to-br from-slate-900 via-indigo-950/80 to-slate-950 p-8 lg:p-12 flex flex-col justify-between relative overflow-hidden">
          {/* Subtle Ambient Mesh Blur */}
          <div className="absolute -top-20 -left-20 w-64 h-64 bg-brand-500/20 rounded-full blur-3xl"></div>
          <div className="absolute -bottom-20 -right-20 w-64 h-64 bg-emerald-500/10 rounded-full blur-3xl"></div>

          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs font-semibold mb-6">
              <ScanLine size={15}/> Research Project — NSBM Green University
            </div>

            <h1 className="font-display font-extrabold text-3xl sm:text-4xl text-white leading-tight tracking-tight">
              AI Digital Tailor System
            </h1>
            <p className="text-slate-400 text-sm mt-3 leading-relaxed">
              Automated 2D pattern drafting and fabric waste minimization platform powered by Computer Vision & Aldrich Geometry.
            </p>
          </div>

          <div className="my-8 space-y-4">
            {[
              { icon: Bot, title: 'YOLOv8 Vision AI', desc: 'Detects necklines, sleeves & garment structure' },
              { icon: Ruler, title: 'Aldrich Metric Engine', desc: 'Generates custom technical cutting blocks' },
              { icon: Recycle, title: '2D Fabric Nesting', desc: 'Minimizes textile waste & calculates yardage' },
            ].map((feat, i) => {
              const Icon = feat.icon;
              return (
              <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-slate-900/40 border border-slate-800/60">
                <span className="p-2 rounded-lg bg-slate-800/80"><Icon size={18}/></span>
                <div>
                  <h4 className="text-xs font-bold text-slate-200">{feat.title}</h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">{feat.desc}</p>
                </div>
              </div>
            )})}
          </div>

          <div className="text-[11px] text-slate-500 pt-4 border-t border-slate-800/60">
            Student: <strong className="text-slate-300">D N M Vitharana (28404)</strong>  
            <br />Supervisor: Mr. Anton Jayakody
          </div>
        </div>

        {/* Right Form: Login Controls */}
        <div className="p-8 lg:p-12 flex flex-col justify-center bg-slate-950/60">
          <div className="mb-6">
            <h2 className="font-display font-bold text-2xl text-white">Welcome Back</h2>
            <p className="text-slate-400 text-xs mt-1">Sign in to access your pattern drafting workspace</p>
          </div>

          {error && (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl p-3 mb-6 text-xs flex items-center gap-2">
              <AlertCircle size={16}/> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                name="email"
                value={form.email}
                onChange={handleChange}
                required
                className="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none transition-all"
                placeholder="dilshani@gmail.com"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Password
              </label>
              <input
                type="password"
                name="password"
                value={form.password}
                onChange={handleChange}
                required
                className="w-full glass-input rounded-xl px-4 py-3 text-sm focus:outline-none transition-all"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 rounded-xl font-semibold text-sm text-white bg-gradient-to-r from-brand-600 to-indigo-500 hover:from-brand-500 hover:to-indigo-400 shadow-glow-indigo transition-all duration-200 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  Authenticating...
                </>
              ) : (
                'Sign In to Dashboard →'
              )}
            </button>
          </form>

          <p className="text-center text-xs text-slate-400 mt-8">
            Don't have an account?{' '}
            <Link to="/register" className="text-brand-400 font-semibold hover:underline">
              Create student / tailor account
            </Link>
          </p>
        </div>

      </div>
    </div>
  );
}
