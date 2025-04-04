from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent, AgentResponse
from pydantic import BaseModel
from ortools.sat.python import cp_model
import json
from datetime import datetime, timedelta
from src.utils.json_helpers import extract_json_block
import traceback
from src.agents.time_constraint_parser import TimeConstraintParser
from src.utils.calendar import get_calendar_service, get_calendar_events
from src.utils.logging import logger

class ScheduledTask(BaseModel):
    task_id: str
    start_time: datetime
    end_time: datetime
    assigned_to: str
    deadline: Optional[datetime] = None

class SchedulerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Scheduler Agent",
            description="You are a task scheduling agent that optimizes task assignments based on dependencies, durations, and constraints."
        )
        self.model = cp_model.CpModel()
        self.time_parser = TimeConstraintParser()
    
    def _get_unavailable_times(self, start_time: datetime, end_time: datetime) -> List[Dict[str, datetime]]:
        """Get list of unavailable time slots from Google Calendar"""
        try:
            service = get_calendar_service()
            events = get_calendar_events(service, start_time.isoformat(), end_time.isoformat())
            
            unavailable_times = []
            for event in events:
                event_start = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                unavailable_times.append({
                    'start': event_start,
                    'end': event_end
                })
            return unavailable_times
        except Exception as e:
            logger.error(f"Error fetching calendar events: {str(e)}")
            # Return empty list if calendar service is not available
            return []

    def _format_prompt(self, input_data: Dict[str, Any]) -> str:
        tasks = input_data.get("tasks", [])
        estimates = input_data.get("estimates", [])
        constraints = input_data.get("constraints", [])
        
        prompt = f"""
        Tasks to Schedule:
        {chr(10).join(f"- {task['title']} (ID: {task['id']})" for task in tasks)}
        
        Task Estimates:
        {chr(10).join(f"- {estimate['task_id']}: {estimate['estimated_duration_minutes']} minutes" for estimate in estimates)}
        
        Constraints:
        {chr(10).join(f"- {constraint}" for constraint in constraints)}
        
        Please provide a schedule that:
        1. Respects task dependencies
        2. Optimizes for priority and deadlines
        3. Considers resource availability
        4. Minimizes context switching
        
        Return the response in JSON format.
        """
        return prompt
    
    def _create_schedule(self, tasks: List[Dict], estimates: List[Dict], constraints: List[str]) -> List[ScheduledTask]:
        model = cp_model.CpModel()

        # Normalize task IDs - convert to string
        for task in tasks:
            if 'id' in task:
                task['id'] = str(task['id'])
            elif 'ID' in task:
                task['id'] = str(task['ID'])
        
        for estimate in estimates:
            if 'task_id' in estimate:
                estimate['task_id'] = str(estimate['task_id'])
        
        # Parse time constraints from tasks and global constraints
        task_deadlines = self.time_parser.extract_task_constraints(tasks)
        global_constraints = self.time_parser.extract_global_constraints(constraints)
        
        # Get unavailable times from Google Calendar
        start_time = datetime.now()
        end_time = start_time + timedelta(days=180)  # 6 months window
        unavailable_times = self._get_unavailable_times(start_time, end_time)
        
        # Create a larger scheduling window to ensure feasibility
        max_time = 180 * 24 * 60  # 180 days in minutes

        # Determine the project deadline if specified
        project_end_time = max_time
        if global_constraints['project_deadline']:
            project_end_minutes = int((global_constraints['project_deadline'] - datetime.now()).total_seconds() / 60)
            project_end_time = min(max_time, max(0, project_end_minutes))

        task_vars = {}
        task_end_vars = {}
        task_durations = {}
        
        # Step 1: Create variables for each task (start and end times)
        for task in tasks:
            task_id = str(task.get('id'))
            matching_estimate = next((e for e in estimates if str(e.get('task_id')) == task_id), None)
            
            if matching_estimate is None:
                alt_id = str(task.get('ID', task.get('id')))
                matching_estimate = next((e for e in estimates if str(e.get('task_id')) == alt_id), None)
                
                if matching_estimate is None:
                    duration = 60  # Default 1 hour
                else:
                    duration = int(matching_estimate['estimated_duration_minutes'])
            else:
                duration = int(matching_estimate['estimated_duration_minutes'])
            
            task_durations[task_id] = duration
            task_vars[task_id] = model.NewIntVar(0, max_time, f'start_task_{task_id}')
            task_end_vars[task_id] = model.NewIntVar(0, max_time, f'end_task_{task_id}')
            
            # Add constraint: end time = start time + duration
            model.Add(task_end_vars[task_id] == task_vars[task_id] + duration)
            
            # Add deadline constraints if specified
            if task_id in task_deadlines:
                deadline_minutes = int((task_deadlines[task_id] - datetime.now()).total_seconds() / 60)
                if deadline_minutes > 0:
                    deadline_var = model.NewIntVar(0, max_time, f'deadline_{task_id}')
                    model.Add(deadline_var == int(deadline_minutes))
                    model.Add(task_end_vars[task_id] <= deadline_var)

        # Step 2: Add dependency constraints
        for task in tasks:
            task_id = str(task.get('id', ''))
            dependencies = [str(dep) for dep in task.get('dependencies', [])]
            
            for dep_id in dependencies:
                if dep_id in task_vars:
                    model.Add(task_vars[task_id] >= task_end_vars[dep_id])
        
        # Step 3: Add constraints for unavailable times
        for unavailable in unavailable_times:
            unavailable_start = int((unavailable['start'] - datetime.now()).total_seconds() / 60)
            unavailable_end = int((unavailable['end'] - datetime.now()).total_seconds() / 60)
            
            for task_id in task_vars:
                # Add constraint that task must either end before unavailable time starts
                # or start after unavailable time ends
                before_unavailable = model.NewBoolVar(f'before_unavailable_{task_id}_{unavailable_start}')
                model.Add(task_end_vars[task_id] <= unavailable_start).OnlyEnforceIf(before_unavailable)
                model.Add(task_vars[task_id] >= unavailable_end).OnlyEnforceIf(before_unavailable.Not())
        
        # Step 4: Add project deadline constraint if specified
        if global_constraints['project_deadline']:
            project_deadline_minutes = int((global_constraints['project_deadline'] - datetime.now()).total_seconds() / 60)
            if project_deadline_minutes > 0:
                project_deadline_var = model.NewIntVar(0, max_time, 'project_deadline')
                model.Add(project_deadline_var == int(project_deadline_minutes))
                for task_id in task_end_vars:
                    model.Add(task_end_vars[task_id] <= project_deadline_var)
        
        # Step 5: Add objective to minimize makespan
        makespan = model.NewIntVar(0, max_time, 'makespan')
        for task_id in task_end_vars:
            model.Add(makespan >= task_end_vars[task_id])
        
        model.Minimize(makespan)

        # Create the solver and solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 20.0
        status = solver.Solve(model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            scheduled_tasks = []
            for task in tasks:
                task_id = str(task.get('id'))
                start_time = datetime.now() + timedelta(minutes=solver.Value(task_vars[task_id]))
                end_time = start_time + timedelta(minutes=task_durations[task_id])
                
                deadline = task_deadlines.get(task_id)
                
                task_params = {
                    "task_id": task_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "assigned_to": "default"
                }
                
                if deadline is not None:
                    task_params["deadline"] = deadline
                    
                scheduled_tasks.append(ScheduledTask(**task_params))
            return scheduled_tasks
        else:
            # Fallback to sequential scheduling if no feasible solution found
            print("No feasible schedule found. Creating sequential schedule as fallback.")
            current_time = datetime.now()
            scheduled_tasks = []
            task_ids_to_schedule = set(task.get('id') for task in tasks)
            scheduled_task_ids = set()

            while task_ids_to_schedule:
                for task in tasks:
                    task_id = str(task.get('id'))
                    if task_id not in task_ids_to_schedule:
                        continue
                        
                    dependencies = set(str(dep) for dep in task.get('dependencies', []))
                    unscheduled_dependencies = dependencies - scheduled_task_ids
                    
                    if not unscheduled_dependencies:
                        duration = task_durations.get(task_id, 60)
                        
                        # Check if current time is in an unavailable slot
                        for unavailable in unavailable_times:
                            if unavailable['start'] <= current_time < unavailable['end']:
                                current_time = unavailable['end']
                                break
                        
                        end_time = current_time + timedelta(minutes=duration)
                        
                        task_params = {
                            "task_id": task_id,
                            "start_time": current_time,
                            "end_time": end_time,
                            "assigned_to": "default"
                        }
                        
                        deadline = task_deadlines.get(task_id)
                        if deadline is not None:
                            task_params["deadline"] = deadline
                            
                        scheduled_tasks.append(ScheduledTask(**task_params))
                        
                        scheduled_task_ids.add(task_id)
                        task_ids_to_schedule.remove(task_id)
                        current_time = end_time
                        break
                else:
                    # Handle potential circular dependencies
                    print("WARNING: Potential circular dependency detected!")
                    task_id = next(iter(task_ids_to_schedule))
                    duration = task_durations.get(task_id, 60)
                    
                    # Check if current time is in an unavailable slot
                    for unavailable in unavailable_times:
                        if unavailable['start'] <= current_time < unavailable['end']:
                            current_time = unavailable['end']
                            break
                    
                    end_time = current_time + timedelta(minutes=duration)
                    
                    task_params = {
                        "task_id": task_id,
                        "start_time": current_time,
                        "end_time": end_time,
                        "assigned_to": "default"
                    }
                    
                    deadline = task_deadlines.get(task_id)
                    if deadline is not None:
                        task_params["deadline"] = deadline
                        
                    scheduled_tasks.append(ScheduledTask(**task_params))
                    
                    scheduled_task_ids.add(task_id)
                    task_ids_to_schedule.remove(task_id)
                    current_time = end_time
                    
            return scheduled_tasks
            
    async def process(self, input_data: Dict[str, Any]) -> AgentResponse:
        try:
            prompt = self._format_prompt(input_data)
            raw_response = await self._call_llm(prompt)

            try:
                json_str = extract_json_block(raw_response)
                llm_schedule = json.loads(json_str)
            except Exception as e:
                return AgentResponse(success=False, error=f"Failed to parse LLM schedule: {e}")

            tasks = input_data.get("tasks", [])
            estimates = input_data.get("estimates", [])
            constraints = input_data.get("constraints", [])

            # Normalize IDs
            for task in tasks:
                task['id'] = str(task.get('id') or task.get('ID'))
            for estimate in estimates:
                estimate['task_id'] = str(estimate.get('task_id'))
                        
            try:
                scheduled_tasks = self._create_schedule(tasks, estimates, constraints)
                
                # Convert ScheduledTask objects to dictionaries for JSON serialization
                scheduled_tasks_dicts = []
                for task in scheduled_tasks:
                    task_dict = {
                        "task_id": task.task_id,
                        "start_time": task.start_time.isoformat(),
                        "end_time": task.end_time.isoformat(),
                        "assigned_to": task.assigned_to
                    }
                    
                    # Add deadline if it exists
                    if task.deadline:
                        task_dict["deadline"] = task.deadline.isoformat()
                    
                    scheduled_tasks_dicts.append(task_dict)
                
                return AgentResponse(
                    success=True,
                    data={
                        "llm_suggestions": llm_schedule,
                        "optimized_schedule": scheduled_tasks_dicts
                    }
                )

            except Exception as e:
                tb = traceback.format_exc()
                return AgentResponse(success=False, error=f"Scheduling exception: {str(e)}\nTraceback:\n{tb}")

        except Exception as e:
            tb = traceback.format_exc()
            return AgentResponse(success=False, error=f"Unexpected error: {str(e)}\nTraceback:\n{tb}")