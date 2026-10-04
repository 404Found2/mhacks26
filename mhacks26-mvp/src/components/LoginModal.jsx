import { useEffect, useState } from 'react';

function LoginModal({ onClose, onAuthenticated }) {
  const [mode, setMode] = useState('login');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setSubmitting(true);

    const isLogin = mode === 'login';
    try {
      const response = await fetch(isLogin ? '/api/auth/login' : '/api/auth/register', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(
          isLogin
            ? { email, password }
            : { username, email, password }
        ),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || 'Could not sign in');
      }
      onAuthenticated({
        userId: data.user_id,
        username: data.username,
      });
    } catch (err) {
      setError(err.message || 'Could not reach the server');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-overlay" onClick={onClose}>
      <div
        className="login-box"
        role="dialog"
        aria-modal="true"
        aria-labelledby="login-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="login-close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h2 id="login-title" className="login-title">
          {mode === 'login' ? 'Log in' : 'Create account'}
        </h2>
        <p className="login-subtitle">
          {mode === 'login'
            ? 'Sign in to keep this session on your account.'
            : 'Create an account and keep the work from this visit.'}
        </p>

        <form className="login-form" onSubmit={submit}>
          {error && <div className="error-message">{error}</div>}

          {mode === 'register' && (
            <label className="form-group">
              <span className="form-label">Name</span>
              <input
                className="form-input"
                type="text"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
              />
            </label>
          )}

          <label className="form-group">
            <span className="form-label">Email</span>
            <input
              className="form-input"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label className="form-group">
            <span className="form-label">Password</span>
            <input
              className="form-input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              required
            />
          </label>

          <button type="submit" className="login-button primary-button" disabled={submitting}>
            {submitting ? 'Please wait…' : mode === 'login' ? 'Log in' : 'Create account'}
          </button>
        </form>

        <p className="login-switch">
          {mode === 'login' ? 'New here?' : 'Already have an account?'}{' '}
          <button
            type="button"
            onClick={() => {
              setMode(mode === 'login' ? 'register' : 'login');
              setError('');
            }}
          >
            {mode === 'login' ? 'Create an account' : 'Log in'}
          </button>
        </p>
      </div>
    </div>
  );
}

export default LoginModal;
