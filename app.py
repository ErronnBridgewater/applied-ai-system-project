import streamlit as st
from datetime import datetime, timedelta
from pawpal_system import Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

st.subheader("Owner And Pet")
owner_name = st.text_input("Owner name", value="Jordan")
pet_name = st.text_input("Pet name", value="Mochi")
species = st.selectbox("Species", ["dog", "cat", "other"])

st.markdown("### Tasks")
st.caption("Add tasks below. The schedule view uses Scheduler methods to sort, filter, and detect conflicts.")

if "tasks" not in st.session_state:
    st.session_state.tasks = []

if "show_schedule" not in st.session_state:
    st.session_state.show_schedule = False

col1, col2, col3, col4 = st.columns(4)
with col1:
    task_id = st.text_input("Task ID", value="morning-walk")
with col2:
    category = st.selectbox("Category", ["daily", "feeding", "exercise", "health", "grooming", "weekly"])
with col3:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with col4:
    priority = st.slider("Priority", min_value=1, max_value=3, value=2)

date_col, time_col = st.columns(2)
with date_col:
    task_date = st.date_input("Scheduled date")
with time_col:
    task_time = st.time_input("Scheduled time")

start_dt = datetime.combine(task_date, task_time)
end_dt = start_dt.replace(second=0, microsecond=0)
end_dt = end_dt + timedelta(minutes=int(duration))

owner = Owner(name=owner_name, available_hours=[4.0], energy_level=2)
pet = Pet(name=pet_name, species=species, age=0, health_status="healthy", owner=owner)

if st.button("Add Task"):
    new_task = Task(
        task_id=task_id.strip() or f"task-{len(st.session_state.tasks) + 1}",
        category=category,
        priority=int(priority),
        estimated_duration=int(duration),
        pet=pet,
        owner=owner,
        scheduled_start=start_dt,
        scheduled_end=end_dt,
    )
    st.session_state.tasks.append(new_task)
    st.success("Task added to the schedule queue.")

if st.session_state.tasks:
    st.write("Current task queue:")

    scheduler = Scheduler(owner=owner, daily_queue=st.session_state.tasks)
    task_rows = []
    for t in scheduler.sort_by_time():
        task_rows.append(
            {
                "Task ID": t.task_id,
                "Category": t.category,
                "Priority": t.priority,
                "Pet": t.pet.name if t.pet else "Unknown",
                "Start": t.scheduled_start.strftime("%Y-%m-%d %H:%M") if t.scheduled_start else "Not set",
                "End": t.scheduled_end.strftime("%Y-%m-%d %H:%M") if t.scheduled_end else "Calculated from duration",
                "Completed": t.is_completed,
            }
        )
    st.table(task_rows)

    open_task_ids = [t.task_id for t in scheduler.filter_tasks(is_completed=False)]
    selected_to_complete = st.multiselect(
        "Mark tasks complete",
        options=open_task_ids,
        help="Completing a daily or weekly task auto-creates the next occurrence.",
    )

    if st.button("Complete Selected Tasks"):
        next_created = 0
        completed_count = 0
        for t in scheduler.daily_queue[:]:
            if t.task_id in selected_to_complete and not t.is_completed:
                new_task = scheduler.complete_task(t)
                completed_count += 1
                if new_task is not None:
                    next_created += 1

        st.session_state.tasks = scheduler.daily_queue
        st.success(f"Marked {completed_count} task(s) complete.")
        if next_created:
            st.info(f"Created {next_created} recurring follow-up task(s).")

    conflicts = scheduler.detect_time_conflicts_lightweight()
    time_conflicts = [c for c in conflicts if "Time conflict" in c]
    if time_conflicts:
        for msg in time_conflicts:
            st.warning(msg)
    else:
        st.success("No time conflicts detected in the current queue.")
else:
    st.info("No tasks yet. Add one above.")

st.divider()

st.subheader("Build Schedule")
st.caption("Generate a polished sorted/filtered schedule view from the Scheduler.")

if st.button("Generate Schedule"):
    st.session_state.show_schedule = True

if st.session_state.show_schedule and st.session_state.tasks:
    scheduler = Scheduler(owner=owner, daily_queue=st.session_state.tasks)

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        completion_filter = st.selectbox("Completion filter", ["all", "open", "completed"])
    with filter_col2:
        pet_filter = st.text_input("Filter by pet name", value=pet_name)

    completed_filter_value = None
    if completion_filter == "open":
        completed_filter_value = False
    elif completion_filter == "completed":
        completed_filter_value = True

    filtered_tasks = scheduler.filter_tasks(
        is_completed=completed_filter_value,
        pet_name=pet_filter.strip() if pet_filter.strip() else None,
    )

    filtered_rows = []
    for t in sorted(filtered_tasks, key=lambda task: (task.scheduled_start is None, task.scheduled_start)):
        filtered_rows.append(
            {
                "Task ID": t.task_id,
                "Category": t.category,
                "Priority": t.priority,
                "Pet": t.pet.name if t.pet else "Unknown",
                "Start": t.scheduled_start.strftime("%Y-%m-%d %H:%M") if t.scheduled_start else "Not set",
                "Completed": t.is_completed,
            }
        )

    st.table(filtered_rows)

    st.success(f"Displaying {len(filtered_rows)} filtered task(s) from {len(scheduler.daily_queue)} total.")

st.subheader("🤖 AI Smart Planner")
st.caption("Let the Agentic Workflow design your day based on your energy and pet needs.")

if st.button("Run AI Optimization"):
    # Initialize logic
    owner = Owner(name=owner_name, available_hours=[4.0], energy_level=priority) # Using priority slider as energy proxy
    pet = Pet(name=pet_name, species=species, age=0, health_status="Healthy", owner=owner)
    
    scheduler = Scheduler(owner=owner, daily_queue=st.session_state.tasks)
    
    with st.spinner("Agent is planning and verifying your schedule..."):
        result = scheduler.optimize_schedule(pet_list=[pet])
    
    if result.success:
        st.success(result.message)
        for t in result.scheduled_tasks:
            st.write(f"✅ **{t.task_id}** ({t.estimated_duration} mins)")
        
        if result.conflicts:
            with st.expander("Warnings / Budget Constraints"):
                for c in result.conflicts:
                    st.warning(c)
    else:
        st.error(result.message)


elif st.session_state.show_schedule:
    st.warning("Add at least one task to generate the schedule table.")
