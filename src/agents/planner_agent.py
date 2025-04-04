from typing import Any, Dict, List, Union
from .base_agent import BaseAgent, AgentResponse
from pydantic import BaseModel, ConfigDict, Field
import json
import asyncio
from src.utils.json_helpers import extract_json_block, robust_json_load

class Subtask(BaseModel):
    id: Union[str, int] = Field(..., alias="ID")
    title: str = Field(..., alias="Title")
    description: str = Field(..., alias="Description")
    dependencies: List[Union[str, int]] = Field(..., alias="Dependencies")
    priority: int = Field(..., alias="Priority")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="allow"
    )

class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Planner Agent",
            description="You are a task planning agent that breaks down high-level projects into structured subtasks with dependencies."
        )
    
    def _format_prompt(self, input_data: Dict[str, Any]) -> str:
        project_description = input_data.get("project_description", "")
        constraints = input_data.get("constraints", [])
        
        prompt = f"""
        Project Description: {project_description}
        
        Constraints:
        {chr(10).join(f"- {constraint}" for constraint in constraints)}
        
        Please break down this project into subtasks with the following structure:
        - Each subtask should have a unique ID
        - Include a clear title and description
        - Specify dependencies (IDs of tasks that must be completed first)
        - Assign a priority level (1-5, where 5 is highest)
        
        Return the response in JSON format.
        """
        return prompt
    
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        try:
            prompt = self._format_prompt(input_data)
            raw_response = await self._call_llm(prompt)

            print("[PLANNER_AGENT] Raw response:", repr(raw_response))

            # Step 1: Extract the JSON block
            try:
                json_str = extract_json_block(raw_response)
                print("[DEBUG] Type after extract:", type(json_str))
                
            except Exception as e:
                return AgentResponse(success=False, error=f"Failed to extract JSON: {e}")


            # Step 2: Parse the JSON, possibly double-decode if needed
            try:
                print("[DEBUG] JSON string before loading:", repr(json_str))
                parsed = robust_json_load(json_str)
                print("[DEBUG] Type after first json.loads:", type(parsed))


                # If still a string, decode it again
                if isinstance(parsed, str):
                    print("[PLANNER_AGENT] Double-encoded JSON detected. Parsing again...")
                    parsed = json.loads(parsed)
            except Exception as e:
                return AgentResponse(success=False, error=f"Failed to parse JSON: {e}")

            # Step 3: Get the task list (either directly or from a wrapper key)
            if isinstance(parsed, list):
                subtasks_data = parsed
            elif isinstance(parsed, dict):
                subtasks_data = parsed.get("tasks", [])
            else:
                return AgentResponse(success=False, error="Unexpected JSON structure")

            # Step 4: Validate and collect
            subtasks = []
            for task in subtasks_data:
                try:
                    subtasks.append(Subtask.model_validate(task))
                except Exception as e:
                    print(f"Skipping task due to validation error: {task} — {str(e)}")

            return AgentResponse(success=True, data={"subtasks": subtasks})

        except Exception as e:
            return AgentResponse(success=False, error=str(e))
