import { Layers } from 'lucide-react';

export default function FeatureCard({ feature, active, onClick }) {
  return (
    <div
      className={`feature-card${active ? ' active' : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <h3>
        <Layers size={18} className="icon" />
        {feature.name}
      </h3>
      <p>{feature.description}</p>
      {feature.files.length > 0 && (
        <div className="files">
          {feature.files.slice(0, 5).map((f) => (
            <span key={f}>{f.split('/').pop()}</span>
          ))}
          {feature.files.length > 5 && (
            <span>+{feature.files.length - 5} more</span>
          )}
        </div>
      )}
    </div>
  );
}
