# GitTime AI

An AI-powered agent that analyzes public GitHub repositories, identifies all major features, and shows a linear version timeline for each feature.

## Architecture

```
├── backend/          # FastAPI server
│   ├── main.py       # API endpoints
│   ├── github_client.py  # GitHub API integration
│   ├── ai_analyzer.py    # OpenAI-powered feature analysis
│   └── models.py         # Pydantic data models
├── frontend/         # React + Vite app
│   └── src/
│       ├── App.jsx
│       ├── components/
│       │   ├── RepoInput.jsx
│       │   ├── FeatureList.jsx
│       │   ├── FeatureCard.jsx
│       │   └── VersionTimeline.jsx
│       └── api.js
```

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Add your API keys
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment Variables

| Variable         | Description                                                    |
| ---------------- | -------------------------------------------------------------- |
| `OPENAI_API_KEY` | Your OpenAI API key                                            |
| `GITHUB_TOKEN`   | (Optional) GitHub personal access token for higher rate limits |

## How It Works

1. Enter a public GitHub repository URL
2. The agent fetches the repo structure, README, commits, and tags via the GitHub API
3. OpenAI analyzes the codebase to identify major features
4. Features are displayed as interactive cards
5. Click a feature to see its version timeline — a linear graph showing how the feature evolved across commits/releases
