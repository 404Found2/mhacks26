const navigation = [
  { id: 'home', label: 'Home', icon: 'home' },
  { id: 'marketing-strategy', label: 'Marketing Strategy', icon: 'marketing'},
];

function initials(name) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function NavBar({ activePage, onNavigate, user, onLoginClick, onLogout }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="brand">
          <div className="brand-mark">
            <span className="brand-spark" />
          </div>
          <div className="brand-copy">
            <div className="brand-name">Northstar</div>
            <div className="brand-sub">AI STRATEGY STUDIO</div>
          </div>
        </div>

        <nav className="side-nav" aria-label="Sidebar navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${activePage === item.id ? 'active' : ''}`}
              onClick={() => onNavigate(item.id)}
            >
              <span className={`nav-icon ${item.icon}`} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="profile-card">
        {user ? (
          <>
            <div className="avatar-circle">{initials(user.username)}</div>
            <div className="profile-copy">
              <div className="profile-name">{user.username}</div>
              <button type="button" className="profile-logout" onClick={onLogout}>
                Log out
              </button>
            </div>
          </>
        ) : (
          <button type="button" className="nav-login" onClick={onLoginClick}>
            Log in
          </button>
        )}
      </div>
    </aside>
  );
}

export default NavBar;