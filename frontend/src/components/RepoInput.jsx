import { useState } from 'react';
import { Search } from 'lucide-react';

export default function RepoInput({ onAnalyze, loading }) {
  const [url, setUrl] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (url.trim()) onAnalyze(url.trim());
  };

  return (
    <form className="repo-input-wrapper" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="Enter a public repo URL  (e.g. facebook/react)"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={loading}
      />
      <button type="submit" disabled={loading || !url.trim()}>
        <Search size={16} style={{ marginRight: 6, verticalAlign: -2 }} />
        Analyze
      </button>
    </form>
  );
}
