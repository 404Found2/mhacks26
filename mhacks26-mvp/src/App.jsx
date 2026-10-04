import { useEffect, useState } from 'react';
import NavBar from './components/NavBar';
import LoginModal from './components/LoginModal';
import DashboardPage from './pages/DashboardPage';
import MarketingStrategyPage from './pages/MarketingStrategyPage';

function App() {
  const [page, setPage] = useState('home');
  const [user, setUser] = useState(null);
  const [loginOpen, setLoginOpen] = useState(false);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionVersion, setSessionVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/session', { credentials: 'include' })
      .then((response) => response.json())
      .then((data) => {
        if (cancelled || !data.is_authenticated) return;
        setUser({ userId: data.user_id, username: data.username });
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setSessionReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const logout = async () => {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    });
    setUser(null);
    setSessionVersion((version) => version + 1);
  };

  const goToMarketingChat = () => { setPage('marketing-strategy')};

  const currentPage = (() => {
    switch (page) {
      case 'marketing-strategy':
        return <MarketingStrategyPage sessionReady={sessionReady} sessionVersion={sessionVersion} />;
      case 'home':
        return <DashboardPage sessionReady={sessionReady} sessionVersion={sessionVersion} onPageChange={goToMarketingChat}/>;
      default:
        return <DashboardPage sessionReady={sessionReady} sessionVersion={sessionVersion} onPageChange={goToMarketingChat}/>;
    }
  })();

  return (
    <div className="app-shell">
      <NavBar
        activePage={page}
        onNavigate={setPage}
        user={user}
        onLoginClick={() => setLoginOpen(true)}
        onLogout={logout}
      />
      {currentPage}
      {loginOpen && (
        <LoginModal
          onClose={() => setLoginOpen(false)}
          onAuthenticated={(account) => {
            setUser(account);
            setSessionVersion((version) => version + 1);
            setLoginOpen(false);
          }}
        />
      )}
    </div>
  );
}

export default App;