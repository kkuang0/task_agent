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
            
            # Display Results
            st.header("Results")

            # Subtasks
            st.subheader("Subtasks")
            for task in subtasks:
                with st.expander(f"**{task.title}**"):
                    st.write(f"Description: {task.description}")
                    st.write(f"Dependencies: {', '.join(map(str, task.dependencies))}")
                    st.write(f"Priority: {task.priority}/5")

            # Estimates
            st.subheader("Time Estimates")
            estimates_df = pd.DataFrame([
                {
                    "Task ID": e.task_id,
                    "Task": next((t.title for t in subtasks if str(t.id) == str(e.task_id)), f"Task {e.task_id}"),
                    "Duration (min)": e.estimated_duration_minutes,
                    "Confidence": f"{e.confidence_score:.2f}"
                } for e in estimates
            ])
            st.dataframe(estimates_df)

            # Schedule
            st.subheader("Optimized Schedule")
            if "optimized_schedule" in scheduling_result.data:
                schedule_data = []
                for task in scheduling_result.data["optimized_schedule"]:
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
                st.dataframe(schedule_df)
                
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
                st.plotly_chart(fig)
            else:
                st.write("No schedule data available")
                
            # Feedback Section
            st.header("Task Feedback")
            feedback_expander = st.expander("Provide Feedback on Completed Tasks")
            with feedback_expander:
                # Task selection - dynamically populated from the generated subtasks
                if 'subtasks' in locals() and subtasks:
                    task_options = {f"{task.id}: {task.title}": task.id for task in subtasks}
                    selected_task = st.selectbox("Select Task", options=list(task_options.keys()))
                    selected_task_id = task_options[selected_task] if selected_task else ""
                else:
                    st.info("Complete task planning first to provide feedback.")
                    selected_task_id = st.text_input("Task ID")
                
                # Feedback inputs
                actual_duration = st.number_input("Actual Duration (minutes)", min_value=0, max_value=1440, value=60)
                
                # Find the original estimate if available
                original_estimate = 0
                if 'estimates' in locals() and estimates:
                    for estimate in estimates:
                        if str(estimate.task_id) == str(selected_task_id):
                            original_estimate = estimate.estimated_duration_minutes
                            st.info(f"Original estimate was {original_estimate} minutes")
                            break
                
                # Calculate default values
                accuracy_default = min(1.0, max(0.0, 1.0 - abs(original_estimate - actual_duration) / max(original_estimate, 1)))
                
                # Feedback metrics
                accuracy = st.slider("Accuracy Feedback (0-1)", 0.0, 1.0, accuracy_default)
                priority = st.slider("Priority Feedback (0-1)", 0.0, 1.0, 0.5)
                notes = st.text_area("Notes")
                
                if st.button("Submit Feedback"):
                    if not selected_task_id:
                        st.error("Please provide a task ID")
                    else:
                        feedback_input = {
                            "task": {"id": selected_task_id},
                            "feedback": {
                                "task_id": selected_task_id,
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
                                        with st.expander("Feedback Analysis"):
                                            if isinstance(result.data["analysis"], dict):
                                                for key, value in result.data["analysis"].items():
                                                    st.write(f"**{key.replace('_', ' ').title()}**")
                                                    st.write(value)
                                                    st.write("---")
                                            else:
                                                st.write(result.data["analysis"])
                                else:
                                    st.error(f"Error: {result.error}")
                            except Exception as e:
                                logger.error(f"Error in feedback processing: {str(e)}")
                                st.error(f"An error occurred while processing feedback: {str(e)}")

        except Exception as e:
            logger.error(f"Error in main processing: {str(e)}")
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()