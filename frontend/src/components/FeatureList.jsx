import FeatureCard from './FeatureCard';

export default function FeatureList({ features, activeId, onSelect }) {
  return (
    <div className="feature-grid">
      {features.map((f) => (
        <FeatureCard
          key={f.id}
          feature={f}
          active={f.id === activeId}
          onClick={() => onSelect(f)}
        />
      ))}
    </div>
  );
}
