import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Lock, Mail } from 'lucide-react';

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    // Simulate a small delay for effect
    await new Promise(resolve => setTimeout(resolve, 800));

    const result = login(email, password);

    if (result.success) {
      navigate('/chat');
    } else {
      setError(result.error);
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center p-4 relative overflow-hidden bg-[#fdf8f6]">
      {/* Ambient Background */}
      <div className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] bg-copper-200/20 rounded-full blur-[120px]" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[60%] h-[60%] bg-blue-100/30 rounded-full blur-[120px]" />

      <div className="glass-card w-full max-w-[400px] p-8 rounded-3xl shadow-2xl relative z-10 animate-fade-in-up">
        {/* Logo Section */}
        <div className="text-center mb-10">
          <div className="w-20 h-20 mx-auto mb-6 bg-white rounded-2xl shadow-glass flex items-center justify-center p-4">
            <img
              src="/Logo_Naranja_Codelco.jpg"
              alt="Codelco Logo"
              className="w-full h-full object-contain"
            />
          </div>
          <h1 className="text-3xl font-display font-bold text-slate-900 tracking-tight">
            MineDash <span className="text-transparent bg-clip-text bg-gradient-to-r from-copper-500 to-copper-700">AI</span>
          </h1>
          <p className="text-slate-500 text-sm font-medium mt-2 tracking-wide uppercase">
            División Salvador • Codelco
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider ml-1">
              Credenciales Corporativas
            </label>
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Mail className="h-5 w-5 text-slate-400 group-focus-within:text-copper-500 transition-colors" />
              </div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="block w-full pl-10 pr-3 py-3 bg-white/50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-copper-500/20 focus:border-copper-500 transition-all font-medium"
                placeholder="usuario@codelco.cl"
                required
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="relative group">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Lock className="h-5 w-5 text-slate-400 group-focus-within:text-copper-500 transition-colors" />
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="block w-full pl-10 pr-3 py-3 bg-white/50 border border-slate-200 rounded-xl text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-copper-500/20 focus:border-copper-500 transition-all font-medium"
                placeholder="••••••••"
                required
              />
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl flex items-center gap-2 animate-shake">
              <div className="w-1.5 h-1.5 rounded-full bg-red-500" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full group relative flex justify-center py-3.5 px-4 border border-transparent text-sm font-bold rounded-xl text-white bg-gradient-to-r from-copper-600 to-copper-500 hover:from-copper-500 hover:to-copper-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-copper-500 shadow-lg shadow-copper-500/30 transition-all duration-300 transform hover:-translate-y-0.5 disabled:opacity-70 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <span className="flex items-center gap-2">
                Iniciar Sesión
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </span>
            )}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-8 text-center space-y-4">
          <p className="text-xs text-slate-400 font-medium">
            Sistema experto de análisis operacional v2.0
          </p>
          <div className="flex justify-center gap-4 opacity-50 grayscale hover:grayscale-0 transition-all duration-500">
            {/* Placeholders for partner logos if needed, or just keep it clean */}
          </div>
        </div>
      </div>

      <div className="absolute bottom-6 text-center w-full text-[10px] text-slate-400 font-medium tracking-widest uppercase opacity-60">
        Powered by GPT-5.1 • Advanced Mining Intelligence
      </div>
    </div>
  );
};

export default Login;
