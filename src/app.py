import streamlit as st
import asyncio
import nest_asyncio
import logging
from src import initialize_app
from src.agents.planner_agent import PlannerAgent
from src.agents.estimator_agent import EstimatorAgent
from src.agents.scheduler_agent import SchedulerAgent
from src.agents.memory_agent import MemoryAgent
from datetime import datetime
import pandas as pd
import plotly.express as px
import time
import uuid
from src.utils.database import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the application first
if not initialize_app():
    logger.error("Failed to initialize application. Exiting...")
    st.error("Failed to initialize application")
    st.stop()
else:
    logger.info("Application initialized successfully")

# Initialize database
try:
    init_db()
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {str(e)}")
    st.error(f"Failed to initialize database: {str(e)}")
    st.stop()

# Patch the event loop for Streamlit
try:
    nest_asyncio.apply()
    logger.info("Successfully patched event loop with nest_asyncio")
except Exception as e:
    logger.error(f"Failed to patch event loop: {str(e)}")
    st.error(f"Failed to initialize application: {str(e)}")
    st.stop()

# Initialize agents
try:
    planner = PlannerAgent()
    estimator = EstimatorAgent()
    scheduler = SchedulerAgent()
    memory = MemoryAgent()
    logger.info("Successfully initialized all agents")
except Exception as e:
    logger.error(f"Failed to initialize agents: {str(e)}")
    st.error(f"Failed to initialize application: {str(e)}")
    st.stop()

async def process_task(project_description: str, constraints: list):
    try:
        # Step 1: Planning
        planning_input = {
            "project_description": project_description,
            "constraints": constraints
        }
        planning_result = await planner.process(planning_input)

        if not planning_result.success:
            logger.error(f"Planning failed: {planning_result.error}")
            return {"error": planning_result.error}

        subtasks = planning_result.data["subtasks"]
        logger.info(f"Successfully generated {len(subtasks)} subtasks")

        # Step 2: Estimation
        estimation_input = {
            "tasks": [s.model_dump() for s in subtasks],
            "historical_data": {}
        }
        estimation_result = await estimator.process(estimation_input)

        if not estimation_result.success:
            logger.error(f"Estimation failed: {estimation_result.error}")
            return {"error": estimation_result.error}

        estimates = estimation_result.data["estimates"]
        logger.info(f"Successfully generated {len(estimates)} estimates")

        # Step 3: Scheduling
        scheduling_input = {
            "tasks": [task.model_dump() for task in subtasks],
            "estimates": [estimate.model_dump() for estimate in estimates],
            "constraints": constraints
        }
        scheduling_result = await scheduler.process(scheduling_input)

        if not scheduling_result.success:
            logger.error(f"Scheduling failed: {scheduling_result.error}")
            return {"error": scheduling_result.error}

        logger.info("Successfully generated schedule")
        return {
            "subtasks": subtasks,
            "estimates": estimates,
            "schedule": scheduling_result.data
        }

    except Exception as e:
        logger.error(f"Unexpected error in process_task: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

def main():
    st.title("Autonomous Task Agent System")

    # Initialize session state for storing results and projects
    if 'last_result' not in st.session_state:
        st.session_state.last_result = None
    if 'show_results' not in st.session_state:
        st.session_state.show_results = False
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
    if 'current_project_id' not in st.session_state:
        st.session_state.current_project_id = None

    # Project Selection
    st.header("Project Management")
    
    # Create two columns for project selection and new project
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.session_state.projects:
            project_options = {f"{pid}: {data['description'][:50]}..." if len(data['description']) > 50 else f"{pid}: {data['description']}": pid 
                             for pid, data in st.session_state.projects.items()}
            selected_project = st.selectbox(
                "Select Existing Project",
                options=["New Project"] + list(project_options.keys())
            )
            
            if selected_project != "New Project":
                selected_project_id = project_options[selected_project]
                st.session_state.current_project_id = selected_project_id
                project_data = st.session_state.projects[selected_project_id]
                
                # Display project details
                st.write(f"**Description**: {project_data['description']}")
                st.write("**Constraints**:")
                for constraint in project_data['constraints']:
                    st.write(f"- {constraint}")
                
                # Load the project's results if available
                if 'results' in project_data:
                    st.session_state.last_result = project_data['results']
                    st.session_state.show_results = True
                    st.success("Project loaded successfully!")
    
    with col2:
        if st.button("Clear Project"):
            st.session_state.current_project_id = None
            st.session_state.last_result = None
            st.session_state.show_results = False
            st.rerun()

    # Project Input
    st.header("Project Details")
    project_description = st.text_area("Project Description")
    constraints = st.text_area("Constraints (one per line)").split("\n")

    if st.button("Process Project"):
        if not project_description:
            st.error("Please enter a project description")
            return

        # Create a placeholder for the progress bar
        progress_placeholder = st.empty()
        progress_bar = progress_placeholder.progress(0)
        
        # Create a status message placeholder
        status_message = st.empty()
        
        try:
            # Phase 1: Planning
            status_message.info("Phase 1/3: Planning tasks...")
            progress_bar.progress(10)
            
            planning_input = {
                "project_description": project_description,
                "constraints": constraints
            }
            planning_result = asyncio.get_event_loop().run_until_complete(planner.process(planning_input))
            
            if not planning_result.success:
                st.error(f"Planning failed: {planning_result.error}")
                return
                
            subtasks = planning_result.data["subtasks"]
            progress_bar.progress(30)
            status_message.success(f"Planning complete: Generated {len(subtasks)} subtasks")
            
            # Phase 2: Estimation
            status_message.info("Phase 2/3: Estimating task durations...")
            progress_bar.progress(40)
            
            estimation_input = {
                "tasks": [s.model_dump() for s in subtasks],
                "historical_data": {}
            }
            estimation_result = asyncio.get_event_loop().run_until_complete(estimator.process(estimation_input))
            
            if not estimation_result.success:
                st.error(f"Estimation failed: {estimation_result.error}")
                return
                
            estimates = estimation_result.data["estimates"]
            progress_bar.progress(60)
            status_message.success(f"Estimation complete: Generated {len(estimates)} estimates")
            
            # Phase 3: Scheduling
            status_message.info("Phase 3/3: Creating optimized schedule...")
            progress_bar.progress(70)
            
            scheduling_input = {
                "tasks": [task.model_dump() for task in subtasks],
                "estimates": [estimate.model_dump() for estimate in estimates],
                "constraints": constraints
            }
            scheduling_result = asyncio.get_event_loop().run_until_complete(scheduler.process(scheduling_input))
            
            if not scheduling_result.success:
                st.error(f"Scheduling failed: {scheduling_result.error}")
                return
                
            progress_bar.progress(90)
            status_message.success("Scheduling complete: Generated optimized schedule")
            
            # Final processing
            progress_bar.progress(100)
            status_message.success("✅ All processing complete!")
            
            # Clear the progress elements after completion
            time.sleep(1)  # Give users a moment to see the 100% completion
            progress_placeholder.empty()
            status_message.empty()
            
            # Store the results
            results = {
                "subtasks": subtasks,
                "estimates": estimates,
                "schedule": scheduling_result.data
            }
            
            # Generate a unique project ID if this is a new project
            if not st.session_state.current_project_id:
                st.session_state.current_project_id = str(uuid.uuid4())
            
            # Store the project in session state
            st.session_state.projects[st.session_state.current_project_id] = {
                "description": project_description,
                "constraints": constraints,
                "results": results,
                "created_at": datetime.now().isoformat()
            }
            
            st.session_state.last_result = results
            st.session_state.show_results = True
            
            # Force a rerun to show the results
            st.rerun()

        except Exception as e:
            logger.error(f"Error in main processing: {str(e)}")
            st.error(f"An error occurred: {str(e)}")

    # Display Results if available
    if st.session_state.show_results and st.session_state.last_result:
        st.header("Results")
        
        # Add a save button for the current project
        if st.session_state.current_project_id:
            if st.button("Save Project"):
                st.success("Project saved successfully!")
        
        subtasks = st.session_state.last_result["subtasks"]
        estimates = st.session_state.last_result["estimates"]
        schedule = st.session_state.last_result["schedule"]

        # Subtasks
        st.subheader("Subtasks")
        
        # Create a mapping of task IDs to their objects for quick lookup
        task_map = {str(task.id): task for task in subtasks}
        
        # Create a mapping of task IDs to their children
        children_map = {}
        for task in subtasks:
            for dep_id in task.dependencies:
                dep_id_str = str(dep_id)
                if dep_id_str not in children_map:
                    children_map[dep_id_str] = []
                children_map[dep_id_str].append(task)
        
        # Find root tasks (tasks with no dependencies)
        root_tasks = [task for task in subtasks if not task.dependencies]
        
        # Initialize a counter for unique task instances
        task_counter = {}
        
        def get_unique_key(task_id, parent_id, level):
            # Initialize counter for this task if not exists
            key = f"{task_id}_{parent_id}_{level}"
            if key not in task_counter:
                task_counter[key] = 0
            task_counter[key] += 1
            return f"{key}_{task_counter[key]}"
        
        def render_task_with_dependencies(task, level=0, parent_id=None):
            # Generate unique key for this task instance
            unique_key = get_unique_key(str(task.id), parent_id if parent_id else 'root', level)
            
            # Initialize task completion state if not exists
            task_key = f"task_completed_{unique_key}"
            if task_key not in st.session_state:
                st.session_state[task_key] = False
            
            # Create columns for checkbox and expander
            col1, col2 = st.columns([1, 20])
            
            with col1:
                # Checkbox for task completion with unique key
                is_completed = st.checkbox(
                    "✓",
                    value=st.session_state[task_key],
                    key=f"checkbox_{unique_key}",
                    help="Mark task as completed"
                )
                st.session_state[task_key] = is_completed
            
            with col2:
                # Add indentation based on level
                indent = "&nbsp;" * (level * 4)  # 4 spaces per level
                expander_title = f"{indent}{'└─ ' if level > 0 else ''}**{task.title}** {'✅' if is_completed else ''}"
                
                with st.expander(expander_title):
                    st.write(f"Description: {task.description}")
                    
                    # Display dependencies in a more structured way
                    if task.dependencies:
                        st.write("**Depends on:**")
                        for dep_id in task.dependencies:
                            dep_task = task_map.get(str(dep_id))
                            if dep_task:
                                dep_key = get_unique_key(str(dep_id), str(task.id), level)
                                dep_status = "✅" if st.session_state.get(f"task_completed_{dep_key}", False) else "⏳"
                                st.write(f"- {dep_task.title} {dep_status}")
                            else:
                                st.write(f"- Task {dep_id} (not found)")
                    
                    st.write(f"Priority: {task.priority}/5")
                    
                    # Find the estimate for this task
                    task_estimate = next((e for e in estimates if str(e.task_id) == str(task.id)), None)
                    if task_estimate:
                        st.write(f"Estimated Duration: {task_estimate.estimated_duration_minutes} minutes")
                        st.write(f"Confidence: {task_estimate.confidence_score:.2f}")
                    
                    # Only show feedback form if task is completed
                    if is_completed:
                        st.write("---")
                        st.subheader("Task Feedback")
                        
                        # Feedback inputs with unique keys
                        actual_duration = st.number_input(
                            "Actual Duration (minutes)", 
                            min_value=0, 
                            max_value=1440, 
                            value=task_estimate.estimated_duration_minutes if task_estimate else 60,
                            key=f"duration_{unique_key}"
                        )
                        
                        # Calculate default values
                        original_estimate = task_estimate.estimated_duration_minutes if task_estimate else 0
                        accuracy_default = min(1.0, max(0.0, 1.0 - abs(original_estimate - actual_duration) / max(original_estimate, 1)))
                        
                        # Feedback metrics with unique keys
                        accuracy = st.slider(
                            "Accuracy Feedback (0-1)", 
                            0.0, 1.0, 
                            accuracy_default,
                            key=f"accuracy_{unique_key}"
                        )
                        priority = st.slider(
                            "Priority Feedback (0-1)", 
                            0.0, 1.0, 
                            0.5,
                            key=f"priority_{unique_key}"
                        )
                        notes = st.text_area(
                            "Notes",
                            key=f"notes_{unique_key}"
                        )
                        
                        if st.button("Submit Feedback", key=f"submit_{unique_key}"):
                            # Ensure task_id is a string
                            task_id_str = str(task.id)
                            feedback_input = {
                                "task": {"id": task_id_str},
                                "feedback": {
                                    "task_id": task_id_str,
                                    "actual_duration_minutes": actual_duration,
                                    "estimated_duration_minutes": original_estimate,
                                    "accuracy_feedback": accuracy,
                                    "priority_feedback": priority,
                                    "notes": notes
                                }
                            }
                            
                            with st.spinner("Processing feedback..."):
                                try:
                                    result = asyncio.get_event_loop().run_until_complete(memory.process(feedback_input))
                                    
                                    if result.success:
                                        st.success("Feedback submitted successfully!")
                                        
                                        # Display analysis if available
                                        if "analysis" in result.data:
                                            st.subheader("Feedback Analysis")
                                            if isinstance(result.data["analysis"], dict):
                                                # Display estimation accuracy
                                                if "estimation_accuracy" in result.data["analysis"]:
                                                    accuracy = result.data["analysis"]["estimation_accuracy"]
                                                    st.write("### Estimation Accuracy")
                                                    st.write(f"**Score**: {accuracy.get('score', 'N/A')}")
                                                    st.write(f"**Analysis**: {accuracy.get('analysis', 'No analysis available')}")
                                                    st.write("**Suggestions**:")
                                                    for suggestion in accuracy.get('suggestions', []):
                                                        st.write(f"- {suggestion}")
                                                    st.write("---")
                                                
                                                # Display task patterns
                                                if "task_patterns" in result.data["analysis"]:
                                                    patterns = result.data["analysis"]["task_patterns"]
                                                    st.write("### Task Patterns")
                                                    st.write(f"**Duration Patterns**: {patterns.get('duration_patterns', 'No patterns identified')}")
                                                    st.write(f"**Priority Patterns**: {patterns.get('priority_patterns', 'No patterns identified')}")
                                                    st.write("**Common Issues**:")
                                                    for issue in patterns.get('common_issues', []):
                                                        st.write(f"- {issue}")
                                                    st.write("---")
                                                
                                                # Display recommendations
                                                if "recommendations" in result.data["analysis"]:
                                                    recs = result.data["analysis"]["recommendations"]
                                                    st.write("### Recommendations")
                                                    
                                                    st.write("**Estimation Improvements**:")
                                                    for improvement in recs.get('estimation_improvements', []):
                                                        st.write(f"- {improvement}")
                                                    
                                                    st.write("**Priority Adjustments**:")
                                                    for adjustment in recs.get('priority_adjustments', []):
                                                        st.write(f"- {adjustment}")
                                                    
                                                    st.write("**General Suggestions**:")
                                                    for suggestion in recs.get('general_suggestions', []):
                                                        st.write(f"- {suggestion}")
                                            else:
                                                st.write(result.data["analysis"])
                                    else:
                                        st.error(f"Error: {result.error}")
                                except Exception as e:
                                    logger.error(f"Error in feedback processing: {str(e)}")
                                    st.error(f"An error occurred while processing feedback: {str(e)}")
                    else:
                        st.info("Complete the task to provide feedback.")
            
            # Recursively render child tasks
            task_id_str = str(task.id)
            if task_id_str in children_map:
                for child_task in children_map[task_id_str]:
                    render_task_with_dependencies(child_task, level + 1, task_id_str)
        
        # Render all root tasks and their children
        for root_task in root_tasks:
            render_task_with_dependencies(root_task)

        # Schedule
        st.subheader("Optimized Schedule")
        if "optimized_schedule" in schedule:
            schedule_data = []
            for task in schedule["optimized_schedule"]:
                task_id = task["task_id"]
                task_title = next((t.title for t in subtasks if str(t.id) == str(task_id)), f"Task {task_id}")
                start_time = datetime.fromisoformat(task["start_time"])
                end_time = datetime.fromisoformat(task["end_time"])
                duration = (end_time - start_time).total_seconds() / 60
                
                schedule_item = {
                    "Task ID": task_id,
                    "Task": task_title,
                    "Start Time": start_time.strftime("%Y-%m-%d %H:%M"),
                    "End Time": end_time.strftime("%Y-%m-%d %H:%M"),
                    "Duration (min)": round(duration)
                }
                
                # Add deadline if available
                if "deadline" in task:
                    deadline = datetime.fromisoformat(task["deadline"])
                    schedule_item["Deadline"] = deadline.strftime("%Y-%m-%d %H:%M")
                    
                    # Add a status indicator based on deadline
                    if end_time > deadline:
                        schedule_item["Status"] = "❌ Overdue"
                    else:
                        buffer = (deadline - end_time).total_seconds() / 3600  # hours
                        if buffer < 24:
                            schedule_item["Status"] = "⚠️ Tight deadline"
                        else:
                            schedule_item["Status"] = "✅ On track"
                
                schedule_data.append(schedule_item)
            
            schedule_df = pd.DataFrame(schedule_data)
            
            # Create tabs for different views
            tab1, tab2 = st.tabs(["Calendar View", "Table View"])
            
            with tab1:
                # Calendar View
                st.subheader("Monthly Calendar")
                
                # Get the month to display (default to current month)
                today = datetime.now()
                col1, col2 = st.columns([1, 3])
                with col1:
                    selected_month = st.date_input(
                        "Select Month",
                        value=today,
                        format="YYYY-MM-DD"
                    )
                
                # Create a calendar for the selected month
                calendar_data = []
                for task in schedule["optimized_schedule"]:
                    start_time = datetime.fromisoformat(task["start_time"])
                    if start_time.year == selected_month.year and start_time.month == selected_month.month:
                        task_id = task["task_id"]
                        task_obj = next((t for t in subtasks if str(t.id) == str(task_id)), None)
                        if task_obj:
                            calendar_data.append({
                                "date": start_time.date(),
                                "task": task_obj.title,
                                "start_time": start_time.strftime("%H:%M"),
                                "end_time": datetime.fromisoformat(task["end_time"]).strftime("%H:%M"),
                                "priority": task_obj.priority
                            })
                
                # Create a calendar grid
                st.write("### Tasks for", selected_month.strftime("%B %Y"))
                
                # Group tasks by date
                tasks_by_date = {}
                for item in calendar_data:
                    date_str = item["date"].strftime("%Y-%m-%d")
                    if date_str not in tasks_by_date:
                        tasks_by_date[date_str] = []
                    tasks_by_date[date_str].append(item)
                
                # Display calendar
                for date_str, tasks in sorted(tasks_by_date.items()):
                    date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    st.write(f"#### {date.strftime('%A, %B %d')}")
                    for task in tasks:
                        with st.expander(f"{task['start_time']} - {task['end_time']}: {task['task']}"):
                            st.write(f"**Priority**: {task['priority']}/5")
                            st.write(f"**Time**: {task['start_time']} - {task['end_time']}")
            
            with tab2:
                # Table View
                st.dataframe(schedule_df)
                
                # Add Google Calendar sync button
                if st.button("Sync to Google Calendar"):
                    try:
                        from src.utils.calendar import get_calendar_service, create_calendar_event
                        
                        # Get calendar service
                        service = get_calendar_service()
                        
                        # Create events for each task
                        for task in schedule["optimized_schedule"]:
                            task_id = task["task_id"]
                            task_obj = next((t for t in subtasks if str(t.id) == str(task_id)), None)
                            if task_obj:
                                start_time = datetime.fromisoformat(task["start_time"])
                                end_time = datetime.fromisoformat(task["end_time"])
                                
                                # Create calendar event
                                event = create_calendar_event(
                                    service,
                                    task_obj,
                                    start_time,
                                    end_time
                                )
                        
                        st.success("Tasks successfully synced to Google Calendar!")
                    except Exception as e:
                        logger.error(f"Error syncing to Google Calendar: {str(e)}")
                        st.error(f"Failed to sync to Google Calendar: {str(e)}")
                        st.info("Please make sure you have set up your Google Calendar credentials in the .env file.")
        else:
            st.write("No schedule data available")

if __name__ == "__main__":
    main()