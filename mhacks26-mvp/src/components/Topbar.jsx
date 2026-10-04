function Topbar({ title, actions }) {
  return (
    <header className="topbar">
      <h1>{title}</h1>
      <div className="header-actions">{actions}</div>
    </header>
  );
}

export default Topbar;
