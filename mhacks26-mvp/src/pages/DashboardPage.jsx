import Topbar from '../components/Topbar';
import FocusCard from '../components/dashboard/FocusCard';
import RightRail from '../components/dashboard/RightRail';

function DashboardPage({ onPageChange, sessionReady, sessionVersion }) {
  return (
    <main className="main-panel">
      <Topbar
        title={"Good Morning Jane!"}
      />

      <div className="content-grid">
        <FocusCard sessionReady={sessionReady} sessionVersion={sessionVersion} />
        <RightRail sessionReady={sessionReady} sessionVersion={sessionVersion} onPageChange={onPageChange} />
      </div>
    </main>
  );
}

export default DashboardPage;
