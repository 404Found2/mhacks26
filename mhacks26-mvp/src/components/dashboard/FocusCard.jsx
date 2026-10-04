import { useEffect, useState } from 'react';

const priorities = {
  'Review audience research synthesis': 'High',
  'Approve fall launch messaging': 'Low',
  'Benchmark premium candle pricing': 'Medium',
  'Publish updated product margins': 'Medium',
};

function toTask(todo) {
  return {
    id: todo.id,
    title: todo.name,
    description: todo.des,
    priority: priorities[todo.name] || 'Medium',
    done: todo.status === 'complete',
  };
}

function FocusCard({ sessionReady, sessionVersion }) {
  const [dashboardTasks, setDashboardTasks] = useState([]);
  const [showCompleted, setShowCompleted] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [clearing, setClearing] = useState(false);
  const completedCount = dashboardTasks.filter((task) => task.done).length;
  const visibleTasks = showCompleted
    ? dashboardTasks
    : dashboardTasks.filter((task) => !task.done);

  useEffect(() => {
    if (!sessionReady) return undefined;
    let cancelled = false;

    fetch('/api/todos', { credentials: 'include' })
      .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
      .then(({ ok, data }) => {
        if (cancelled) return;
        if (!ok) throw new Error(data.error || 'Could not load tasks');
        setDashboardTasks(data.map(toTask));
        setLoadError('');
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error.message || 'Could not load tasks');
      });

    return () => {
      cancelled = true;
    };
  }, [sessionReady, sessionVersion]);

  const handleCheck = async (taskId) => {
    const task = dashboardTasks.find((item) => item.id === taskId);
    if (!task) return;

    const nextDone = !task.done;
    setDashboardTasks((current) =>
      current.map((item) =>
        item.id === taskId ? { ...item, done: nextDone } : item
      )
    );

    try {
      const response = await fetch(`/api/todos/${taskId}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextDone ? 'complete' : 'pending' }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not update task');
    } catch {
      setDashboardTasks((current) =>
        current.map((item) =>
          item.id === taskId ? { ...item, done: task.done } : item
        )
      );
    }
  };

  const clearTasks = async () => {
    if (!dashboardTasks.length || clearing) return;
    const previous = dashboardTasks;
    setClearing(true);
    setDashboardTasks([]);
    try {
      const response = await fetch('/api/todos', {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not clear tasks');
      setDashboardTasks([]);
      setLoadError('');
    } catch (error) {
      setDashboardTasks(previous);
      setLoadError(error.message || 'Could not clear tasks');
    } finally {
      setClearing(false);
    }
  };

  return (
    <section className="focus-card">
      <div className="card-header">
        <div>
          <h2>Today's focus</h2>
          <p>One prioritized list for you and every active AI agent.</p>
        </div>
        <div className="card-actions">
          <button
            type="button"
            className="completed-toggle"
            disabled={!dashboardTasks.length || clearing}
            onClick={clearTasks}
          >
            Clear all
          </button>
          <button
            type="button"
            className="completed-toggle"
            aria-pressed={showCompleted}
            onClick={() => setShowCompleted((current) => !current)}
          >
            {showCompleted ? 'Hide completed' : `Show completed (${completedCount})`}
          </button>
        </div>
      </div>

      <div className="progress-box">
        <div className="progress-number">{completedCount} of {dashboardTasks.length}</div>
        <div className="progress-track">
          <div
            className="progress-fill"
            style={{ width: dashboardTasks.length ? `${(completedCount * 100) / dashboardTasks.length}%` : '0%' }}
          />
        </div>
        <div className="progress-label">tasks moving forward</div>
      </div>

      <div className="task-list">
        {loadError && <p className="task-description">{loadError}</p>}
        {!loadError && dashboardTasks.length === 0 && (
          <p className="task-description">No tasks yet.</p>
        )}
        {visibleTasks.map((task) => (
          <div key={task.id} id={task.id} className="task-item">
            <button
              type="button"
              onClick={() => handleCheck(task.id)}
              className={`checkbox ${task.done ? 'checked' : ''}`}
              aria-pressed={task.done}
              aria-label={task.done ? `Mark ${task.title} incomplete` : `Mark ${task.title} complete`}
            >
              {task.done ? '✓' : ''}
            </button>
            <div className="task-copy">
              <div className="task-title-row">
                <span className={`task-title ${task.done ? 'done' : ''}`}>{task.title}</span>
                <span className={`priority-tag ${(task.done ? 'Complete' : task.priority).toLowerCase()}`}>
                  {task.done ? 'Complete' : task.priority}
                </span>
              </div>

              {task.description && <div className="task-description">{task.description}</div>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default FocusCard;
