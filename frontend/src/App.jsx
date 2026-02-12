import { useState } from 'react';
import { GitBranch } from 'lucide-react';
import RepoInput from './components/RepoInput';
import FeatureList from './components/FeatureList';
import VersionTimeline from './components/VersionTimeline';
import CommitEvolution from './components/CommitEvolution';
import { analyzeRepo, getFeatureTimeline, getFeatureEvolution } from './api';

export default function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);          // { repo, features }
  const [activeFeature, setActiveFeature] = useState(null);
  const [activeTab, setActiveTab] = useState('timeline');   // 'timeline' | 'evolution'
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [evolutionLoading, setEvolutionLoading] = useState(false);
  const [versions, setVersions] = useState({});            // { featureId: [...] }
  const [evolutions, setEvolutions] = useState({});        // { featureId: [...] }

  const handleAnalyze = async (url) => {
    setLoading(true);
    setError('');
    setAnalysis(null);
    setActiveFeature(null);
    setVersions({});
    setEvolutions({});

    try {
      const data = await analyzeRepo(url);
      setAnalysis(data);
    } catch (err) {
      setError(err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const fetchTimeline = async (feature) => {
    if (versions[feature.id]) return;
    setTimelineLoading(true);
    try {
      const data = await getFeatureTimeline(analysis.repo, feature);
      setVersions((prev) => ({ ...prev, [feature.id]: data.versions }));
    } catch {
      setVersions((prev) => ({ ...prev, [feature.id]: [] }));
    } finally {
      setTimelineLoading(false);
    }
  };

  const fetchEvolution = async (feature) => {
    if (evolutions[feature.id]) return;
    setEvolutionLoading(true);
    try {
      const data = await getFeatureEvolution(analysis.repo, feature);
      setEvolutions((prev) => ({ ...prev, [feature.id]: data.evolution }));
    } catch {
      setEvolutions((prev) => ({ ...prev, [feature.id]: [] }));
    } finally {
      setEvolutionLoading(false);
    }
  };

  const handleSelectFeature = async (feature) => {
    setActiveFeature(feature);
    if (activeTab === 'timeline') {
      fetchTimeline(feature);
    } else {
      fetchEvolution(feature);
    }
  };

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    if (activeFeature) {
      if (tab === 'timeline') fetchTimeline(activeFeature);
      else fetchEvolution(activeFeature);
    }
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <h1>
          <GitBranch size={32} style={{ verticalAlign: -4, marginRight: 8 }} />
          GitTime AI
        </h1>
        <p>AI-powered feature discovery &amp; version timeline for any public repo</p>
      </header>

      {/* Repo Input */}
      <RepoInput onAnalyze={handleAnalyze} loading={loading} />

      {/* Error */}
      {error && <div className="error">{error}</div>}

      {/* Loading */}
      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p>Cloning repo context &amp; identifying features…</p>
        </div>
      )}

      {/* Results */}
      {analysis && (
        <>
          <div className="repo-banner">
            <h2>
              Features of <span>{analysis.repo}</span>
            </h2>
          </div>

          <FeatureList
            features={analysis.features}
            activeId={activeFeature?.id}
            onSelect={handleSelectFeature}
          />

          {activeFeature && (
            <>
              {/* Tab switcher */}
              <div className="detail-tabs">
                <button
                  className={`tab-btn${activeTab === 'timeline' ? ' active' : ''}`}
                  onClick={() => handleTabSwitch('timeline')}
                >
                  📊 Version Timeline
                </button>
                <button
                  className={`tab-btn${activeTab === 'evolution' ? ' active' : ''}`}
                  onClick={() => handleTabSwitch('evolution')}
                >
                  🧬 Commit Evolution
                </button>
              </div>

              {activeTab === 'timeline' && (
                <VersionTimeline
                  feature={activeFeature}
                  versions={versions[activeFeature.id]}
                  loading={timelineLoading && !versions[activeFeature.id]}
                />
              )}

              {activeTab === 'evolution' && (
                <CommitEvolution
                  feature={activeFeature}
                  evolution={evolutions[activeFeature.id]}
                  loading={evolutionLoading && !evolutions[activeFeature.id]}
                />
              )}
            </>
          )}
        </>
      )}

      {/* Empty state */}
      {!analysis && !loading && !error && (
        <div className="empty-state">
          <div className="icon-large">🔍</div>
          <h2>Discover Features in Any Repo</h2>
          <p>
            Paste a GitHub repo URL above and the AI agent will break it down
            into its major features with a version timeline for each.
          </p>
        </div>
      )}
    </div>
  );
}
