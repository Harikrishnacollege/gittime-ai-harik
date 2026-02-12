import { useState } from 'react';
import { ChevronDown, ChevronRight, GitCommit, FileCode, Plus, Minus } from 'lucide-react';

const STATUS_COLOR = {
  added: '#3fb950',
  modified: '#d29922',
  removed: '#f85149',
  renamed: '#bc8cff',
};

const STATUS_LABEL = {
  added: 'A',
  modified: 'M',
  removed: 'D',
  renamed: 'R',
};

function FileStat({ file }) {
  return (
    <div className="evo-file-row">
      <span
        className="evo-file-badge"
        style={{ background: STATUS_COLOR[file.status] || '#8b949e' }}
      >
        {STATUS_LABEL[file.status] || file.status?.[0]?.toUpperCase()}
      </span>
      <span className="evo-file-name">{file.filename}</span>
      <span className="evo-file-stats">
        {file.additions > 0 && (
          <span className="evo-stat evo-stat-add">
            <Plus size={10} />
            {file.additions}
          </span>
        )}
        {file.deletions > 0 && (
          <span className="evo-stat evo-stat-del">
            <Minus size={10} />
            {file.deletions}
          </span>
        )}
        {file.additions === 0 && file.deletions === 0 && (
          <span className="evo-stat evo-stat-none">0</span>
        )}
      </span>
    </div>
  );
}

function CommitRow({ commit }) {
  const [open, setOpen] = useState(false);
  const totalAdds = commit.total_additions || 0;
  const totalDels = commit.total_deletions || 0;

  return (
    <div className={`evo-commit${open ? ' evo-commit--open' : ''}`}>
      {/* ── Collapsed row ── */}
      <div className="evo-commit-row" onClick={() => setOpen(!open)}>
        <span className="evo-expand-icon">
          {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <GitCommit size={14} className="evo-commit-icon" />
        <span className="evo-sha">{commit.sha}</span>
        <span className="evo-commit-msg">{commit.message}</span>
        <span className="evo-row-stats">
          {totalAdds > 0 && <span className="evo-stat evo-stat-add">+{totalAdds}</span>}
          {totalDels > 0 && <span className="evo-stat evo-stat-del">-{totalDels}</span>}
        </span>
        <span className="evo-date">{commit.date}</span>
      </div>

      {/* ── Expanded detail ── */}
      {open && (
        <div className="evo-detail">
          {/* AI explanation */}
          <div className="evo-explanation">
            <div className="evo-explanation-label">How this evolved the feature</div>
            <p>{commit.evolution_summary}</p>
          </div>

          {/* Commit meta */}
          <div className="evo-meta-line">
            <span>Author: <strong>{commit.author}</strong></span>
            <span>{commit.date}</span>
          </div>

          {/* Files changed */}
          {commit.files_changed && commit.files_changed.length > 0 && (
            <div className="evo-file-list">
              <div className="evo-file-list-header">
                <FileCode size={14} />
                <span>
                  {commit.files_changed.length} file{commit.files_changed.length > 1 ? 's' : ''} changed
                </span>
                <span className="evo-file-list-totals">
                  <span className="evo-stat evo-stat-add">+{totalAdds}</span>
                  <span className="evo-stat evo-stat-del">-{totalDels}</span>
                </span>
              </div>
              {commit.files_changed.map((f, i) => (
                <FileStat key={i} file={f} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CommitEvolution({ feature, evolution, loading }) {
  if (loading) {
    return (
      <div className="timeline-panel">
        <h3>🧬 Evolution: {feature.name}</h3>
        <p className="subtitle">Analyzing how this feature evolved…</p>
        <div className="timeline-loading">
          <div className="spinner" />
          <p>Tracing commits &amp; explaining changes with AI…</p>
        </div>
      </div>
    );
  }

  if (!evolution || evolution.length === 0) {
    return (
      <div className="timeline-panel">
        <h3>🧬 Evolution: {feature.name}</h3>
        <p className="subtitle">No commit-level evolution could be determined.</p>
      </div>
    );
  }

  const totalCommits = evolution.length;
  const totalAdds = evolution.reduce((s, c) => s + (c.total_additions || 0), 0);
  const totalDels = evolution.reduce((s, c) => s + (c.total_deletions || 0), 0);

  return (
    <div className="timeline-panel evo-panel">
      <h3>🧬 Evolution: {feature.name}</h3>
      <p className="subtitle">
        {totalCommits} commit{totalCommits > 1 ? 's' : ''} ·{' '}
        <span className="evo-stat evo-stat-add">+{totalAdds}</span>{' '}
        <span className="evo-stat evo-stat-del">-{totalDels}</span>{' '}
        lines · oldest → newest
      </p>

      <div className="evo-list">
        {evolution.map((c, i) => (
          <CommitRow key={c.sha + i} commit={c} />
        ))}
      </div>
    </div>
  );
}
