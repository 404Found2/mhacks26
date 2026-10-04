function HeaderBar({ leftLabel, title, actions }) {
  return (
    <header className="page-header">
      <div className="header-label">{leftLabel}</div>
      <div className="header-title-row">
        <h2>{title}</h2>
        <div className="header-actions wide">{actions}</div>
      </div>
    </header>
  );
}

export default HeaderBar;
