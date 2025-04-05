from typing import Any, Dict, List
from .base_agent import BaseAgent, AgentResponse
from pydantic import BaseModel
import chromadb
from chromadb.config import Settings
import json
from datetime import datetime
from src.utils.json_helpers import extract_json_block

class TaskFeedback(BaseModel):
    task_id: str
    actual_duration_minutes: int
    estimated_duration_minutes: int
    accuracy_feedback: float  # 0-1 scale
    priority_feedback: float  # 0-1 scale
    notes: str
    created_at: datetime = None

class MemoryAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Memory Agent",
            description="You are a memory agent that tracks and learns from task execution patterns and user feedback."
        )
        self.client = chromadb.EphemeralClient()
        self.collection = self.client.get_or_create_collection("task_memory")
    
    def _format_prompt(self, input_data: Dict[str, Any]) -> str:
        task = input_data.get("task", {})
        feedback = input_data.get("feedback", {})
        
        prompt = f"""
        Task Information:
        - ID: {task.get('id', '')}
        - Title: {task.get('title', '')}
        - Description: {task.get('description', '')}
        
        Feedback:
        - Actual Duration: {feedback.get('actual_duration_minutes', 0)} minutes
        - Estimated Duration: {feedback.get('estimated_duration_minutes', 0)} minutes
        - Accuracy Feedback: {feedback.get('accuracy_feedback', 0)}
        - Priority Feedback: {feedback.get('priority_feedback', 0)}
        - Notes: {feedback.get('notes', '')}
        
        Please analyze this feedback and provide a JSON response with the following structure:
        {{
            "estimation_accuracy": {{
                "score": <float between 0 and 1>,
                "analysis": "<detailed analysis of estimation accuracy>",
                "suggestions": ["<suggestion 1>", "<suggestion 2>", ...]
            }},
            "task_patterns": {{
                "duration_patterns": "<analysis of duration patterns>",
                "priority_patterns": "<analysis of priority patterns>",
                "common_issues": ["<issue 1>", "<issue 2>", ...]
            }},
            "recommendations": {{
                "estimation_improvements": ["<improvement 1>", "<improvement 2>", ...],
                "priority_adjustments": ["<adjustment 1>", "<adjustment 2>", ...],
                "general_suggestions": ["<suggestion 1>", "<suggestion 2>", ...]
            }}
        }}
        
        Provide detailed, actionable insights in each section.
        """
        return prompt
    
    def _store_feedback(self, feedback: TaskFeedback):
        # Store feedback in ChromaDB
        feedback_data = {
            "task_id": feedback.task_id,
            "actual_duration_minutes": feedback.actual_duration_minutes,
            "accuracy_feedback": feedback.accuracy_feedback,
            "priority_feedback": feedback.priority_feedback,
            "notes": feedback.notes,
            "created_at": feedback.created_at.isoformat() if feedback.created_at else None
        }
        
        self.collection.add(
            documents=[json.dumps(feedback_data)],
            metadatas=[{
                "task_id": feedback.task_id,
                "timestamp": feedback.created_at.isoformat() if feedback.created_at else datetime.now().isoformat(),
                "accuracy": feedback.accuracy_feedback,
                "priority": feedback.priority_feedback
            }],
            ids=[f"feedback_{feedback.task_id}_{datetime.now().isoformat()}"]
        )
    
    def _get_similar_tasks(self, task_description: str, limit: int = 5) -> List[Dict]:
        # Query similar tasks from ChromaDB
        results = self.collection.query(
            query_texts=[task_description],
            n_results=limit
        )
        
        similar_tasks = []
        for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
            similar_tasks.append({
                **json.loads(doc),
                **metadata
            })
        return similar_tasks
    
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        try:
            # Store the feedback
            feedback = TaskFeedback(**input_data.get("feedback", {}))
            self._store_feedback(feedback)

            # Get similar tasks for analysis
            task_description = input_data.get("task", {}).get("description", "")
            similar_tasks = self._get_similar_tasks(task_description)

            # Get LLM analysis
            prompt = self._format_prompt(input_data)
            raw_response = await self._call_llm(prompt)

            try:
                # First try to extract JSON block
                analysis_json = extract_json_block(raw_response)
                if not analysis_json:
                    # If no JSON block found, try to parse the entire response
                    analysis_json = raw_response.strip()
                
                # Try to parse the JSON
                analysis_data = json.loads(analysis_json)
                
                # Validate the structure
                if not isinstance(analysis_data, dict):
                    raise ValueError("Analysis data must be a dictionary")
                
                required_sections = ["estimation_accuracy", "task_patterns", "recommendations"]
                for section in required_sections:
                    if section not in analysis_data:
                        raise ValueError(f"Missing required section: {section}")
                
            except Exception as e:
                # If JSON parsing fails, return a structured error response
                return AgentResponse(
                    success=True,
                    data={
                        "analysis": {
                            "error": f"Failed to parse LLM analysis: {str(e)}",
                            "raw_response": raw_response
                        },
                        "similar_tasks": similar_tasks
                    }
                )

            return AgentResponse(
                success=True,
                data={
                    "analysis": analysis_data,
                    "similar_tasks": similar_tasks
                }
            )

        except Exception as e:
            return AgentResponse(success=False, error=str(e))