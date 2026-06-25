import { useState } from 'react';
import { Bot, Mail, Lock, User, Eye, EyeOff, Sparkles, Loader } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './AuthPage.css';

export default function AuthPage() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState('login'); // 'login' | 'register'
  const [form, setForm] = useState({ email: '', password: '', fullName: '' });
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (tab === 'login') {
        await login(form.email, form.password);
      } else {
        await register(form.email, form.password, form.fullName);
      }
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const update = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }));

  return (
    <div className="auth-root">
      {/* Ambient background orbs */}
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />

      <div className="auth-card">
        {/* Logo */}
        <div className="auth-logo">
          <div className="logo-icon">
            <Bot size={28} />
          </div>
          <span className="logo-text">RAG<span className="logo-accent">Chat</span></span>
        </div>

        <div className="auth-headline">
          <h1>{tab === 'login' ? 'Welcome back' : 'Get started'}</h1>
          <p>{tab === 'login'
            ? 'Sign in to your AI knowledge base'
            : 'Create your account and start querying'}</p>
        </div>

        {/* Tab switcher */}
        <div className="auth-tabs">
          <button
            className={`auth-tab ${tab === 'login' ? 'active' : ''}`}
            onClick={() => { setTab('login'); setError(''); }}
          >Login</button>
          <button
            className={`auth-tab ${tab === 'register' ? 'active' : ''}`}
            onClick={() => { setTab('register'); setError(''); }}
          >Register</button>
          <div className={`auth-tab-indicator ${tab === 'register' ? 'right' : ''}`} />
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          {tab === 'register' && (
            <div className="input-group">
              <User size={16} className="input-icon" />
              <input
                type="text"
                placeholder="Full name"
                value={form.fullName}
                onChange={update('fullName')}
                autoComplete="name"
              />
            </div>
          )}

          <div className="input-group">
            <Mail size={16} className="input-icon" />
            <input
              type="email"
              placeholder="Email address"
              value={form.email}
              onChange={update('email')}
              required
              autoComplete="email"
            />
          </div>

          <div className="input-group">
            <Lock size={16} className="input-icon" />
            <input
              type={showPwd ? 'text' : 'password'}
              placeholder="Password"
              value={form.password}
              onChange={update('password')}
              required
              autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
            />
            <button
              type="button"
              className="pwd-toggle"
              onClick={() => setShowPwd(!showPwd)}
              tabIndex={-1}
            >
              {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
            </button>
          </div>

          {error && <p className="auth-error">{error}</p>}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading
              ? <><Loader size={16} className="spin" /> {tab === 'login' ? 'Signing in…' : 'Creating account…'}</>
              : <><Sparkles size={16} /> {tab === 'login' ? 'Sign In' : 'Create Account'}</>
            }
          </button>
        </form>

        <p className="auth-footer">
          {tab === 'login'
            ? <>Don't have an account? <button onClick={() => setTab('register')}>Register</button></>
            : <>Already have an account? <button onClick={() => setTab('login')}>Sign in</button></>
          }
        </p>
      </div>
    </div>
  );
}
