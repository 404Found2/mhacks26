import { useEffect, useState } from 'react';

function RightRail({ onPageChange, sessionReady, sessionVersion }) {
  const [persona, setPersona] = useState(null);
  const [strategy, setStrategy] = useState('');
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!sessionReady) return undefined;
    let cancelled = false;

    Promise.all([
      fetch('/api/personas', { credentials: 'include' }).then((response) => response.json()),
      fetch('/api/strategy', { credentials: 'include' }).then((response) => response.json()),
    ])
      .then(([personas, strategies]) => {
        if (cancelled) return;
        setPersona(Array.isArray(personas) && personas.length ? personas[0] : null);
        const statement = Array.isArray(strategies) && strategies.length ? strategies[0].statement : '';
        setStrategy(statement || '');
        setLoaded(true);
      })
      .catch(() => {
        if (!cancelled) setLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionReady, sessionVersion]);

  return (
    <aside className="right-stack">
      <div className="mini-card">
        <div className="mini-header">
          <h3>Marketing strategy</h3>
        </div>

        <p className="strategy-copy">
          {strategy
            || (loaded
              ? (persona
                ? 'Your mission statement will show up here once Theo finishes it.'
                : 'Your mission statement will show up here after you keep a customer profile.')
              : 'Loading your strategy...')}
        </p>

        <button onClick={onPageChange} className="inline-link">
          Open strategy →
        </button>
      </div>

      <div className="mini-card">
        <div className="mini-header">
          <h3>Target Customer</h3>
        </div>

        <div className="target-label">Qualities Of Your Ideal Customer</div>

        {persona ? (
          <p className="target-copy">
            <strong>Demographic:</strong> {persona.demographics} <br />
            <strong>Challenges:</strong> {persona.pains} <br />
            <strong>Behaviors & Habits:</strong> {persona.habits} <br />
          </p>
        ) : (
          <p className="target-copy">
            {loaded
              ? 'No customer profile yet. Build one with Theo, then choose Keep this profile.'
              : 'Loading your customer profile...'}
          </p>
        )}
      </div>
    </aside>
  );
}

export default RightRail;
