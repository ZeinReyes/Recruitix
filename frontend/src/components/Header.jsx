function Header() {
  return (
    <header className="header">
      <div>
        <h1>Recruitix</h1>
        <p>Philippine Job Market Analytics</p>
      </div>

      <nav>
        <a href="/">Dashboard</a>
        <a href="/jobs">Jobs</a>
      </nav>
    </header>
  );
}

export default Header;