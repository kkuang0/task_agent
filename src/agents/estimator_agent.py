from typing import Any, Dict, List
from .base_agent import BaseAgent, AgentResponse
from pydantic import BaseModel
import json
from src.utils.json_helpers import extract_json_block

class TaskEstimate(BaseModel):
    task_id: str
    estimated_duration_minutes: int
    confidence_score: float
    historical_data_used: bool

class EstimatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Estimator Agent",
            description="You are a task duration estimation agent that predicts how long tasks will take based on their description and historical data. "
        )
    
    def _format_prompt(self, input_data: Dict[str, Any]) -> str:
        tasks = input_data.get("tasks", [])
        historical_data = input_data.get("historical_data", {})
        
        # Create a more structured representation of tasks with clear IDs
        task_descriptions = []
        for task in tasks:
            task_id = task.get('id') or task.get('ID') or task.get('task_id')
            title = task.get('title') or task.get('Title')
            description = task.get('description') or task.get('Description')
            task_descriptions.append(f"- Task ID: {task_id}, Title: {title}, Description: {description}")
        
        prompt = f"""
        Tasks to Estimate:
        {chr(10).join(task_descriptions)}
        
        Historical Data (if available):
        {json.dumps(historical_data, indent=2)}
        
        For each task, estimate:
        1. Duration in minutes
        2. Confidence score (0-1)
        3. Whether historical data was used
        
        IMPORTANT: Use the numeric Task ID value (not the title) as the task_id in your response.
        
        For each task, return a JSON object with the following fields:
        - "task_id": the numeric ID of the task (e.g., "1", "2", "3")
        - "estimated_duration_minutes": integer — your estimate of how long the task will take in minutes
        - "confidence_score": float between 0 and 1 — your confidence level in the estimate
        - "historical_data_used": boolean — true if the estimate used historical data, otherwise false

        ### Output Format (JSON Array):
        [
        {{
            "task_id": "1",
            "estimated_duration_minutes": 120,
            "confidence_score": 0.8,
            "historical_data_used": false
        }},
        ...
        ]

        Do not include markdown or extra commentary. Return only a valid JSON array
        """
        return prompt.strip()
    
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        try:
            if not isinstance(input_data, dict):
                raise TypeError(f"Expected input_data to be a dict, got {type(input_data)}: {repr(input_data)}")

            prompt = self._format_prompt(input_data)
            raw_response = await self._call_llm(prompt)

            try:
                response_json = extract_json_block(raw_response)
                parsed_data = json.loads(response_json)
            except Exception as e:
                return AgentResponse(success=False, error=f"Failed to extract or parse JSON: {str(e)}")

            # Handle both list and dict formats from LLM
            if isinstance(parsed_data, dict):
                estimates_data = parsed_data.get("Tasks", parsed_data)
            elif isinstance(parsed_data, list):
                estimates_data = parsed_data
            else:
                return AgentResponse(success=False, error=f"Unexpected LLM format: {type(parsed_data)}")

            if not isinstance(estimates_data, list):
                estimates_data = [estimates_data]

            estimates = []
            for estimate in estimates_data:
                if isinstance(estimate, str):
                    try:
                        estimate = json.loads(estimate)
                    except json.JSONDecodeError:
                        print(f"Skipping unparsable string: {estimate}")
                        continue

                if not isinstance(estimate, dict):
                    print(f"Skipping non-dict estimate: {estimate}")
                    continue

                required_fields = ['task_id', 'estimated_duration_minutes', 'confidence_score', 'historical_data_used']
                if not all(k in estimate for k in required_fields):
                    print(f"Skipping incomplete estimate: {estimate}")
                    continue

                try:
                    estimates.append(TaskEstimate(**estimate))
                except Exception as e:
                    print(f"Validation error for TaskEstimate: {estimate} — {str(e)}")

            return AgentResponse(success=True, data={"estimates": estimates})

        except Exception as e:
            return AgentResponse(success=False, error=f"Unexpected error: {str(e)}")
