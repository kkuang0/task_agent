from typing import Any, Dict, List, Optional
from .base_agent import BaseAgent, AgentResponse
from pydantic import BaseModel
from ortools.sat.python import cp_model
import json
from datetime import datetime, timedelta
from src.utils.json_helpers import extract_json_block
import traceback
from src.agents.time_constraint_parser import TimeConstraintParser

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
        
        # Print extracted time constraints for debugging
        print(f"Task deadlines: {task_deadlines}")
        print(f"Global constraints: {global_constraints}")
        
        # Debug: print all task IDs and estimate task_ids
        print(f"Task IDs: {[task.get('id') for task in tasks]}")
        print(f"Estimate task_ids: {[est.get('task_id') for est in estimates]}")
        
        # Create a larger scheduling window to ensure feasibility
        # Allow tasks to be scheduled within a 180-day window (6 months)
        max_time = 180 * 24 * 60  

        # Determine the project deadline if specified
        project_end_time = max_time
        if global_constraints['project_deadline']:
            project_end_minutes = int((global_constraints['project_deadline'] - datetime.now()).total_seconds() / 60)
            project_end_time = min(max_time, max(0, project_end_minutes))
            print(f"Project deadline in minutes: {project_end_time}")

        task_vars = {}
        task_end_vars = {}
        task_durations = {}
        
        # Step 1: Create variables for each task (start and end times)
        for task in tasks:
            task_id = str(task.get('id'))
            # Try different ways to match estimates to tasks
            matching_estimate = next((e for e in estimates if str(e.get('task_id')) == task_id), None)
            
            # If no match found, try with ID field names used in other places
            if matching_estimate is None:
                # Try with ID capitalized (as in Subtask model)
                alt_id = str(task.get('ID', task.get('id')))
                matching_estimate = next((e for e in estimates if str(e.get('task_id')) == alt_id), None)
                
                if matching_estimate is None:
                    # As a fallback, use a default duration
                    print(f"WARNING: No estimate found for task_id: {task_id}, using default")
                    duration = 60  # Default 1 hour
                else:
                    duration = int(matching_estimate['estimated_duration_minutes'])
            else:
                duration = int(matching_estimate['estimated_duration_minutes'])
            
            # Store the duration for later use
            task_durations[task_id] = duration
            
            # Create variables for start and end times
            task_vars[task_id] = model.NewIntVar(0, max_time, f'start_task_{task_id}')
            task_end_vars[task_id] = model.NewIntVar(0, max_time, f'end_task_{task_id}')
            
            # Add constraint: end time = start time + duration
            model.Add(task_end_vars[task_id] == task_vars[task_id] + duration)
            
            # Add deadline constraints if specified
            if task_id in task_deadlines:
                deadline_minutes = int((task_deadlines[task_id] - datetime.now()).total_seconds() / 60)
                if deadline_minutes > 0:
                    print(f"Adding deadline constraint for task {task_id}: {deadline_minutes} minutes")
                    model.Add(task_end_vars[task_id] <= deadline_minutes)

        # Step 2: Add dependency constraints
        for task in tasks:
            task_id = str(task.get('id'))
            dependencies = task.get('dependencies', [])
            
            # Convert dependencies to strings if they aren't already
            dependencies = [str(dep) for dep in dependencies]
            
            for dep_id in dependencies:
                if dep_id in task_vars:
                    # Ensure task starts after dependency ends
                    model.Add(task_vars[task_id] >= task_end_vars[dep_id])
        
        # Step 3: Add constraints for work hours if specified
        if global_constraints['work_hours']:
            work_start = global_constraints['work_hours']['start']
            work_end = global_constraints['work_hours']['end']
            work_hours_per_day = work_end - work_start
            
            # Disable this for now as it's complex to implement properly
            # TODO: Implement work hours constraints
        
        # Step 4: Add project deadline constraint if specified
        if global_constraints['project_deadline']:
            for task_id in task_end_vars:
                model.Add(task_end_vars[task_id] <= project_end_time)
        
        # Step 5: Add objective to minimize makespan (completion time of the last task)
        makespan = model.NewIntVar(0, max_time, 'makespan')
        for task_id in task_end_vars:
            model.Add(makespan >= task_end_vars[task_id])
        
        model.Minimize(makespan)

        # Create the solver and solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 20.0  # Set a time limit to avoid hanging
        status = solver.Solve(model)

        # Debug solver status
        print(f"Solver status: {status}")
        print(f"  OPTIMAL={cp_model.OPTIMAL}, FEASIBLE={cp_model.FEASIBLE}, INFEASIBLE={cp_model.INFEASIBLE}")
        
        # Return a schedule even if we only have a partial solution
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            scheduled_tasks = []
            for task in tasks:
                task_id = str(task.get('id'))
                start_time = datetime.now() + timedelta(minutes=solver.Value(task_vars[task_id]))
                end_time = start_time + timedelta(minutes=task_durations[task_id])
                
                # Get the deadline if it exists (but don't set if None)
                deadline = task_deadlines.get(task_id)
                
                # Create task object with deadline only if one exists
                task_params = {
                    "task_id": task_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "assigned_to": "default"
                }
                
                # Only add deadline if it exists
                if deadline is not None:
                    task_params["deadline"] = deadline
                    
                scheduled_tasks.append(ScheduledTask(**task_params))
            return scheduled_tasks
        else:
            # If no feasible solution found, create a simple sequential schedule as fallback
            print("No feasible schedule found. Creating sequential schedule as fallback.")
            current_time = datetime.now()
            scheduled_tasks = []

            # Sort tasks by dependencies to ensure we schedule parents first
            # This is a simple topological sort
            task_ids_to_schedule = set(task.get('id') for task in tasks)
            scheduled_task_ids = set()

            while task_ids_to_schedule:
                # Find tasks with no unscheduled dependencies
                for task in tasks:
                    task_id = str(task.get('id'))
                    if task_id not in task_ids_to_schedule:
                        continue
                        
                    dependencies = set(str(dep) for dep in task.get('dependencies', []))
                    unscheduled_dependencies = dependencies - scheduled_task_ids
                    
                    if not unscheduled_dependencies:
                        # Schedule this task
                        duration = task_durations.get(task_id, 60)  # Default to 60 if not found
                        end_time = current_time + timedelta(minutes=duration)
                        
                        # Create task object with required fields
                        task_params = {
                            "task_id": task_id,
                            "start_time": current_time,
                            "end_time": end_time,
                            "assigned_to": "default"
                        }
                        
                        # Only add deadline if it exists
                        deadline = task_deadlines.get(task_id)
                        if deadline is not None:
                            task_params["deadline"] = deadline
                            
                        scheduled_tasks.append(ScheduledTask(**task_params))
                        
                        # Update tracking variables
                        scheduled_task_ids.add(task_id)
                        task_ids_to_schedule.remove(task_id)
                        current_time = end_time
                        break
                else:
                    # If we've gone through all tasks with no progress, there must be a circular dependency
                    # Pick the first unscheduled task and force it
                    print("WARNING: Potential circular dependency detected!")
                    task_id = next(iter(task_ids_to_schedule))
                    duration = task_durations.get(task_id, 60)
                    end_time = current_time + timedelta(minutes=duration)
                    
                    # Create task object with required fields
                    task_params = {
                        "task_id": task_id,
                        "start_time": current_time,
                        "end_time": end_time,
                        "assigned_to": "default"
                    }
                    
                    # Only add deadline if it exists
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