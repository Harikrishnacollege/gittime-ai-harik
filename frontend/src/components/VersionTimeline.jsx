export default function VersionTimeline({ feature, versions, loading }) {
  if (loading) {
    return (
      <div className="timeline-panel">
        <h3>{feature.name}</h3>
        <p className="subtitle">Building version timeline…</p>
        <div className="timeline-loading">
          <div className="spinner" />
          <p>Analyzing commit history with AI…</p>
        </div>
      </div>
    );
  }

  if (!versions || versions.length === 0) {
    return (
      <div className="timeline-panel">
        <h3>{feature.name}</h3>
        <p className="subtitle">No version history could be determined for this feature.</p>
      </div>
    );
  }

  return (
    <div className="timeline-panel">
      <h3>{feature.name}</h3>
      <p className="subtitle">
        {versions.length} version{versions.length > 1 ? 's' : ''} tracked
      </p>

      <div className="version-timeline">
        {versions.map((v, i) => (
          <div className="version-node" key={i}>
            <div className="dot" />
            <div className="meta">
              <span className="tag">{v.version}</span>
              <span className="date">{v.date}</span>
            </div>
            <p className="desc">{v.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
