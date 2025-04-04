# Autonomous Task Agent System

An intelligent task management system that uses multiple AI agents to plan, estimate, schedule, and learn from task execution.

## System Architecture

The system consists of four main agents:

1. **Planner Agent**: Breaks down high-level projects into structured subtasks using Mistral AI
2. **Estimator Agent**: Predicts task durations using LLM and historical data
3. **Scheduler Agent**: Optimizes task scheduling using constraint programming
4. **Memory Agent**: Tracks and learns from task execution patterns

## Features

- **Interactive Task Planning**: Break down projects into manageable subtasks
- **Smart Time Estimation**: AI-powered duration predictions with confidence scores
- **Optimized Scheduling**: Constraint-based scheduling with dependency management
- **Visual Analytics**: Interactive charts and graphs for task analysis
- **Learning System**: Continuous improvement through feedback and historical data
- **Real-time Updates**: Live progress tracking and schedule adjustments

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables in `.env`:
   ```
   MISTRAL_API_KEY=your_api_key
   GOOGLE_CALENDAR_CREDENTIALS=path_to_credentials.json
   ```

## Usage

Run the Streamlit interface:
```bash
streamlit run src/app.py
```

## Components

- **Agents**: Located in `src/agents/`
  - Base Agent: Common functionality and LLM integration
  - Planner Agent: Task decomposition and structuring
  - Estimator Agent: Duration prediction and confidence scoring
  - Scheduler Agent: Constraint-based scheduling
  - Memory Agent: Learning and pattern recognition

- **Data Management**:
  - SQLite/PostgreSQL for task storage
  - ChromaDB for semantic memory
  - Pandas for data analysis and manipulation

- **Visualization**:
  - Plotly for interactive charts and graphs
  - Streamlit for web interface and data display

- **Scheduling**: Google OR-Tools for constraint optimization

## Dependencies

- **AI & ML**:
  - Mistral AI for language model capabilities
  - LangGraph for agent coordination
  - Scikit-learn for machine learning components

- **Data & Storage**:
  - ChromaDB for vector storage
  - SQLAlchemy for database operations
  - Pandas for data manipulation
  - NumPy for numerical operations

- **Scheduling & Optimization**:
  - Google OR-Tools for constraint programming
  - Dateparser for flexible date handling

- **Web Interface**:
  - Streamlit for web application
  - Plotly for interactive visualizations

## Development

The project uses modern Python development practices and async/await patterns for efficient processing. Key features include:

- Asynchronous processing with nest_asyncio
- Pydantic for data validation and settings management
- Comprehensive logging and error handling
- Modular agent architecture for easy extension

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request 