import HeaderBar from '../components/HeaderBar';
import StrategyChat from '../components/strategy/StrategyChat';

function MarketingStrategyPage({ sessionReady, sessionVersion }) {
  return (
    <main className="main-panel">
        <HeaderBar
          leftLabel="Marketing / Strategy builder"
          title="Develop a Marketing Strategy"
        />

        <div className="strategy-content">
            <StrategyChat sessionReady={sessionReady} sessionVersion={sessionVersion} />
        </div>
    </main>
  );
}

export default MarketingStrategyPage;
