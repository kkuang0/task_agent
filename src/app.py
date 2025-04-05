import streamlit as st
import asyncio
import nest_asyncio
import logging
import hashlib
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
from src.utils.logging import logger

# Define the notes interface
def run_notes_interface():
    st.subheader("Create a New Note")
    
    # Using unique keys by adding a unique identifier
    note_title = st.text_input("Title", key="notes_title_input")
    note_content = st.text_area("Content", height=200, key="notes_content_input")
    note_tags = st.text_input("Tags (comma-separated)", key="notes_tags_input")
    
    # Initialize projects if not exists
    if 'projects' not in st.session_state:
        st.session_state.projects = {}
        
    # Initialize notes if not exists
    if 'notes' not in st.session_state:
        st.session_state.notes = {}
        
    project_options = ["None"] + list(st.session_state.projects.keys())
    assigned_project = st.selectbox("Assign to Project", options=project_options, key="notes_project_select")

    if st.button("Save Note", key="notes_save_button"):
        if note_title and note_content:
            note_data = {
                "task_id": None if assigned_project == "None" else assigned_project,
                "title": note_title,
                "content": note_content,
                "tags": [t.strip() for t in note_tags.split(",") if t.strip()]
            }
            # Store note in session state
            note_id = str(uuid.uuid4())
            st.session_state.notes[note_id] = note_data
            st.success("Note added successfully")

            # Reset form
            st.experimental_rerun()
        else:
            st.error("Title and content are required.")

    # Note Listing
    st.subheader("View Notes")
    filter_option = st.selectbox("Filter Notes", options=["All", "Project-specific", "Unassigned"], key="notes_filter_select")

    # Filter notes based on selection
    filtered_notes = {}
    for note_id, note in st.session_state.notes.items():
        if filter_option == "All":
            filtered_notes[note_id] = note
        elif filter_option == "Project-specific" and note["task_id"] is not None:
            filtered_notes[note_id] = note
        elif filter_option == "Unassigned" and note["task_id"] is None:
            filtered_notes[note_id] = note

    # Display filtered notes
    for note_id, note in filtered_notes.items():
        with st.expander(f"{note['title']} (Task ID: {note['task_id']})", key=f"note_expander_{note_id}"):
            st.markdown(note['content'])
            st.write("Tags:", ", ".join(note['tags']) if note['tags'] else "None")

# Define the projects interface
def run_projects_interface():
    st.header("Project Management")
    
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
    st.subheader("Project Selection")
    
    # Create two columns for project selection and new project
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.session_state.projects:
            project_options = {f"{pid}: {data['description'][:50]}..." if len(data['description']) > 50 else f"{pid}: {data['description']}": pid 
                             for pid, data in st.session_state.projects.items()}
            selected_project = st.selectbox(
                "Select Existing Project",
                options=["New Project"] + list(project_options.keys()),
                key="project_select"
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
        if st.button("Clear Project", key="clear_project_button"):
            st.session_state.current_project_id = None
            st.session_state.last_result = None
            st.session_state.show_results = False
            st.rerun()

    # Project Input
    st.header("Project Details")
    project_description = st.text_area("Project Description", key="project_description_input")
    constraints = st.text_area("Constraints (one per line)", key="project_constraints_input").split("\n")

    if st.button("Process Project", key="process_project_button"):
        if not project_description:
            st.error("Please enter a project description")
            return

        # Create a placeholder for the progress bar
        progress_placeholder = st.empty()
        progress_bar = progress_placeholder.progress(0)
        
        # Create a status message placeholder
        status_message = st.empty()
        
        try:
            # Initialize agents
            planner = PlannerAgent()
            estimator = EstimatorAgent()
            scheduler = SchedulerAgent()
            
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
            if st.button("Save Project", key="save_project_button"):
                st.success("Project saved successfully!")
        
        subtasks = st.session_state.last_result["subtasks"]
        estimates = st.session_state.last_result["estimates"]
        schedule = st.session_state.last_result["schedule"]

        # Subtasks
        st.subheader("Subtasks")
        for idx, task in enumerate(subtasks):
            # Initialize task completion state if not exists
            task_key = f"task_completed_{task.id}_{idx}"
            if task_key not in st.session_state:
                st.session_state[task_key] = False
            
            # Create columns for checkbox and expander
            col1, col2 = st.columns([1, 20])
            
            with col1:
                # Checkbox for task completion
                is_completed = st.checkbox(
                    "✓",
                    value=st.session_state[task_key],
                    key=f"checkbox_{task.id}_{idx}",
                    help="Mark task as completed"
                )
                st.session_state[task_key] = is_completed
            
            with col2:
                # Task expander with completion status
                expander_title = f"**{task.title}** {'✅' if is_completed else ''}"
                with st.expander(expander_title, key=f"task_expander_{task.id}_{idx}"):
                    st.write(f"Description: {task.description}")
                    st.write(f"Dependencies: {', '.join(map(str, task.dependencies))}")
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
                        
                        # Feedback inputs
                        actual_duration = st.number_input(
                            "Actual Duration (minutes)", 
                            min_value=0, 
                            max_value=1440, 
                            value=task_estimate.estimated_duration_minutes if task_estimate else 60,
                            key=f"duration_input_{task.id}_{idx}"
                        )
                        
                        # Calculate default values
                        original_estimate = task_estimate.estimated_duration_minutes if task_estimate else 0
                        accuracy_default = min(1.0, max(0.0, 1.0 - abs(original_estimate - actual_duration) / max(original_estimate, 1)))
                        
                        # Feedback metrics
                        accuracy = st.slider(
                            "Accuracy Feedback (0-1)", 
                            0.0, 1.0, 
                            accuracy_default,
                            key=f"accuracy_slider_{task.id}_{idx}"
                        )
                        priority = st.slider(
                            "Priority Feedback (0-1)", 
                            0.0, 1.0, 
                            0.5,
                            key=f"priority_slider_{task.id}_{idx}"
                        )
                        notes = st.text_area(
                            "Notes",
                            key=f"notes_input_{task.id}_{idx}"
                        )
                        
                        if st.button("Submit Feedback", key=f"submit_feedback_{task.id}_{idx}"):
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
                                    memory = MemoryAgent()
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
            st.dataframe(schedule_df, key="schedule_dataframe")
            
            # Generate a Gantt chart visualization
            fig = px.timeline(
                schedule_data, 
                x_start="Start Time", 
                x_end="End Time", 
                y="Task",
                color="Status" if any("Status" in item for item in schedule_data) else "Task",
                title="Task Schedule Gantt Chart"
            )
            
            # Add deadline markers if available
            if any("Deadline" in item for item in schedule_data):
                for task in schedule_data:
                    if "Deadline" in task:
                        fig.add_vline(
                            x=task["Deadline"], 
                            line_dash="dash", 
                            line_color="red",
                            annotation_text=f"Deadline: {task['Task']}"
                        )
            
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, key="gantt_chart")
        else:
            st.write("No schedule data available")

# Main application entry point
def main():
    # Set page configuration
    st.set_page_config(page_title="Autonomous Task Agent System", layout="wide")

    # Main title
    st.title("📝 NoteDesk: Your Smart Productivity Workspace")

    # Sidebar for mode selection
    app_mode = st.sidebar.radio("Select Mode", ["🗒️ Notes", "📁 Projects"], key="mode_select")

    # Ensure projects are initialized in session state
    if 'projects' not in st.session_state:
        st.session_state.projects = {}

    # Ensure notes are initialized in session state
    if 'notes' not in st.session_state:
        st.session_state.notes = {}

    # Run the appropriate interface based on selection
    if app_mode == "🗒️ Notes":
        run_notes_interface()
    elif app_mode == "📁 Projects":
        run_projects_interface()


if __name__ == "__main__":
    # Initialize the application
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
        # Initialize agents globally to check they work
        PlannerAgent()
        EstimatorAgent()
        SchedulerAgent()
        MemoryAgent()
        logger.info("Successfully initialized all agents")
    except Exception as e:
        logger.error(f"Failed to initialize agents: {str(e)}")
        st.error(f"Failed to initialize application: {str(e)}")
        st.stop()

    # Run the application
    main()