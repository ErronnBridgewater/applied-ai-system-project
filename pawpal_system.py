from __future__ import annotations

import importlib

"""Core data models and scheduling interfaces for PawPal+.

This module defines the domain classes used by the app:
- Owner: manages one or more pets.
- Pet: stores pet profile data and care requirements.
- Task: represents a single care activity.
- Scheduler: coordinates and optimizes task selection.
"""

from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timedelta
import re
import os
import json

try:
	load_dotenv = importlib.import_module("dotenv").load_dotenv
except Exception:
	def load_dotenv(*args, **kwargs):
		return False

try:
	genai = importlib.import_module("google.generativeai")
except Exception:
	genai = None

load_dotenv("api_key.env")
if genai is not None:
	genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class AIAgent:
	"""The 'Brain' of PawPal+ that handles the agentic reasoning loop."""

	def __init__(self):
		self.model = genai.GenerativeModel("gemini-2.5-flash") if genai is not None else None

	def _build_fallback_plan(self, tasks: list[Task]) -> list[dict[str, Any]]:
		"""Create a deterministic schedule when the Gemini client is unavailable."""
		sorted_tasks = sorted(
			tasks,
			key=lambda task: (
				task.category.lower() != "health",
				-task.priority,
				task.scheduled_start is None,
				task.scheduled_start,
				task.estimated_duration,
			),
		)
		return [
			{
				"task_id": task.task_id,
				"reason": "Deterministic fallback based on health, priority, and time fit.",
			}
			for task in sorted_tasks
		]

	def generate_smart_plan(self, owner: Owner, pets: list[Pet], tasks: list[Task]) -> str:
		"""Step 1: The Planning Phase."""
		if self.model is None:
			return json.dumps(self._build_fallback_plan(tasks))

		pet_context = [f"{p.name} ({p.species}, {p.health_status})" for p in pets]
		task_context = [f"{t.task_id}: {t.category}, {t.estimated_duration}m, Priority {t.priority}" for t in tasks]

		prompt = f"""
		You are a pet care expert. Create a logical schedule for {owner.name} (Energy Level: {owner.energy_level}/3).
		Pets: {pet_context}
		Requested Tasks: {task_context}

		Rules:
		1. High priority tasks and health tasks must come first.
		2. If owner energy is low (1), suggest shorter durations.
		3. Output ONLY valid JSON in this shape: [{{"task_id": "...", "reason": "..."}}].
		4. Do not wrap the JSON in markdown fences or add any explanatory text.
		"""
		try:
			response = self.model.generate_content(prompt)
			response_text = getattr(response, "text", "")
			if response_text:
				return response_text
		except Exception:
			pass

		return json.dumps(self._build_fallback_plan(tasks))

@dataclass
class Owner:
	"""Represents a pet owner and high-level scheduling constraints."""

	name: str
	available_hours: list[Any] = field(default_factory=list)
	energy_level: int = 0
	owned_pets: list[Pet] = field(default_factory=list)

	def add_pet(self, pet_details: Pet) -> None:
		"""Attach a Pet to this owner and establish the relationship."""
		if pet_details not in self.owned_pets:
			self.owned_pets.append(pet_details)
		pet_details.owner = self

	def update_availability(self, times: Any) -> None:
		"""Update the owner's available time blocks used by scheduling logic."""
		if times is None:
			self.available_hours = []
		elif isinstance(times, list):
			self.available_hours = times
		else:
			self.available_hours = [times]

	def get_preferences(self) -> str:
		"""Return a human-readable summary of owner preferences."""
		pet_names = ", ".join(p.name for p in self.owned_pets) if self.owned_pets else "no pets"
		availability = ", ".join(str(hour) for hour in self.available_hours) if self.available_hours else "unspecified"
		return (
			f"Owner {self.name}: energy level {self.energy_level}/3, "
			f"available hours [{availability}], pets: {pet_names}."
		)


@dataclass
class Pet:
	"""Represents a pet profile, including health and care requirements."""

	name: str
	species: str
	age: int
	health_status: str
	owner: Owner | None = None
	requirements: dict[str, Any] = field(default_factory=dict)

	def get_needs(self) -> dict[str, Any]:
		"""Return normalized care needs that can be consumed by a scheduler."""
		return {
			"species": self.species.lower(),
			"age": self.age,
			"health_status": self.health_status,
			"requirements": dict(self.requirements),
			"owner": self.owner.name if self.owner else None,
		}

	def update_health_record(self, note: str) -> None:
		"""Record a new health-related note for the pet."""
		health_notes = self.requirements.setdefault("health_notes", [])
		health_notes.append({"note": note, "recorded_at": datetime.now().isoformat()})
		self.health_status = note


@dataclass
class Task:
	"""A single pet-care activity with time and completion metadata."""

	task_id: str
	category: str
	priority: int
	estimated_duration: int
	pet: Pet | None = None
	owner: Owner | None = None
	is_completed: bool = False
	completed_date: datetime | None = None
	skip_count: int = 0
	scheduled_start: datetime | None = None
	scheduled_end: datetime | None = None
	dependency: Task | None = None

	def mark_complete(self) -> Task | None:
		"""Mark the task complete and optionally generate its next recurrence.

		Returns:
			A new Task instance when this task is recurring (daily/weekly),
			otherwise None.
		"""
		if self.is_completed:
			return None

		self.is_completed = True
		self.completed_date = datetime.now()

		return self._build_next_occurrence()

	def _build_next_occurrence(self) -> Task | None:
		"""Create the next recurring task instance for daily/weekly categories."""
		recurrence_days = {"daily": 1, "weekly": 7}
		days = recurrence_days.get(self.category.lower())
		if days is None:
			return None

		delta = timedelta(days=days)
		next_start = self.scheduled_start + delta if self.scheduled_start else None
		next_end = self.scheduled_end + delta if self.scheduled_end else None

		return Task(
			task_id=f"{self.task_id}-next",
			category=self.category,
			priority=self.priority,
			estimated_duration=self.estimated_duration,
			pet=self.pet,
			owner=self.owner,
			skip_count=0,
			scheduled_start=next_start,
			scheduled_end=next_end,
			dependency=self.dependency,
		)

	def get_priority_score(self) -> int:
		"""Calculate a scheduling score based on urgency and history."""
		score = self.priority * 10
		score += max(0, 5 - self.skip_count) * 2
		if self.category.lower() == "health":
			score += 10
		if self.is_completed:
			score -= 25
		return score


@dataclass
class ScheduleResult:
	"""Container for scheduler outputs, conflicts, and status messaging."""

	success: bool
	scheduled_tasks: list[Task] = field(default_factory=list)
	conflicts: list[str] = field(default_factory=list)
	message: str = ""


@dataclass
class Scheduler:
	"""Scheduling engine that organizes tasks across an owner's pets."""

	owner: Owner
	daily_queue: list[Task] = field(default_factory=list)
	total_time_budget: int = 0
	generated_plan: dict[str, Any] = field(default_factory=dict)

	def complete_task(self, task: Task) -> Task | None:
		"""Complete a task and enqueue the next occurrence when recurring."""
		next_task = task.mark_complete()
		if next_task is not None:
			self.daily_queue.append(next_task)
		return next_task

	def _get_effective_time_budget(self) -> int | None:
		"""Resolve a usable budget in minutes from explicit or owner settings."""
		if self.total_time_budget > 0:
			return self.total_time_budget

		numeric_hours = [value for value in self.owner.available_hours if isinstance(value, (int, float))]
		if not numeric_hours:
			return None

		total = sum(numeric_hours)
		if total <= 24:
			return int(total * 60)
		return int(total)

	def _parse_plan_response(self, plan_response: Any) -> list[dict[str, Any]]:
		"""Normalize an AI response into a list of plan items.

		The model may return plain JSON, JSON wrapped in markdown fences, or a
		Response object with a .text payload. This helper strips the common
		wrappers and converts the payload into the structure optimize_schedule()
		expects.
		"""
		response_text = getattr(plan_response, "text", plan_response)
		if not isinstance(response_text, str):
			raise ValueError("AI plan response was not a text payload")

		cleaned = response_text.strip()
		if not cleaned:
			raise ValueError("AI plan response was empty")

		if cleaned.startswith("```"):
			cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
			cleaned = re.sub(r"\s*```$", "", cleaned)

		try:
			parsed = json.loads(cleaned)
		except json.JSONDecodeError:
			start = cleaned.find("[")
			end = cleaned.rfind("]")
			if start != -1 and end != -1 and end > start:
				parsed = json.loads(cleaned[start : end + 1])
			else:
				raise

		if isinstance(parsed, dict):
			parsed = parsed.get("tasks", parsed.get("plan", []))

		if not isinstance(parsed, list):
			raise ValueError("AI plan response must be a JSON list")

		normalized_plan: list[dict[str, Any]] = []
		for item in parsed:
			if isinstance(item, str):
				normalized_plan.append({"task_id": item, "reason": "AI selected this task."})
			elif isinstance(item, dict):
				task_id = item.get("task_id") or item.get("id")
				if task_id:
					normalized_plan.append(
						{
							"task_id": task_id,
							"reason": item.get("reason", "AI selected this task."),
						}
					)

		if not normalized_plan:
			raise ValueError("AI plan response did not contain any task IDs")

		return normalized_plan

	def optimize_schedule(self, pet_list: list[Pet]) -> ScheduleResult:
		"""
        Agentic Workflow Implementation:
        1. Plan: Ask AI for an optimal sequence based on pet/owner context.
        2. Verify: Check if the AI's plan fits the owner's time budget.
        3. Refine: If over budget, drop the lowest priority items.
        """
		agent = AIAgent()
		try:
			plan_response = agent.generate_smart_plan(self.owner, pet_list, self.daily_queue)
			plan_data = self._parse_plan_response(plan_response)
			self.generated_plan = plan_data

			scheduled_tasks = []
			for item in plan_data:
				task_id = item.get("task_id")
				reason = item.get("reason", "No reason provided")
				task = next((t for t in self.daily_queue if t.task_id == task_id), None)
				if task:
					scheduled_tasks.append(task)

			total_time = sum(t.estimated_duration for t in scheduled_tasks)
			budget = self._get_effective_time_budget()
			if budget is not None and total_time > budget:
				message = f"Plan exceeds time budget by {total_time - budget} minutes. Refining..."
				return ScheduleResult(success=False, scheduled_tasks=scheduled_tasks, message=message)

			return ScheduleResult(success=True, scheduled_tasks=scheduled_tasks)
		except Exception as e:
			return ScheduleResult(success=False, message=f"Error during scheduling: {str(e)}")
		

	def explain_logic(self) -> str:
		"""Explain the rules or heuristics used to generate the current plan."""
		if not self.daily_queue:
			return "No tasks are queued yet."

		total_duration = sum(task.estimated_duration for task in self.daily_queue)
		high_priority = sorted(self.daily_queue, key=lambda task: (-task.priority, task.scheduled_start is None, task.scheduled_start))
		top_task = high_priority[0]
		budget = self._get_effective_time_budget()
		budget_text = f" within a {budget}-minute budget" if budget is not None else ""
		return (
			f"Tasks are ranked by priority, health needs, and time fit{budget_text}. "
			f"The current queue contains {len(self.daily_queue)} task(s) totaling {total_duration} minutes, "
			f"with {top_task.task_id} as the highest-priority item."
		)

	def export_to_streamlit(self) -> dict[str, Any]:
		"""Return the generated plan in a UI-friendly dictionary structure."""
		return {
			"owner": self.owner.name,
			"total_time_budget": self._get_effective_time_budget(),
			"task_count": len(self.daily_queue),
			"generated_plan": self.generated_plan,
			"conflicts": self.detect_time_conflicts_lightweight(),
			"tasks": [
				{
					"task_id": task.task_id,
					"category": task.category,
					"priority": task.priority,
					"estimated_duration": task.estimated_duration,
					"completed": task.is_completed,
				}
				for task in self.sort_by_time()
			],
		}

	def detect_time_conflicts(self) -> list[str]:
		"""Detect overlapping task windows in the current daily queue.

		The algorithm builds effective time windows for schedulable tasks,
		then compares each pair of windows to find interval overlaps.

		Returns:
			A list of human-readable conflict messages. Each message identifies
			the two task IDs involved and labels the overlap as either
			"same pet" or "different pets".
		"""
		conflicts: list[str] = []
		tasks_with_windows = []

		for task in self.daily_queue:
			window = self._get_task_window(task)
			if window is not None:
				tasks_with_windows.append((task, window[0], window[1]))

		for i, (left_task, left_start, left_end) in enumerate(tasks_with_windows):
			for right_task, right_start, right_end in tasks_with_windows[i + 1:]:
				if left_start < right_end and right_start < left_end:
					left_pet = left_task.pet.name if left_task.pet else "Unknown"
					right_pet = right_task.pet.name if right_task.pet else "Unknown"
					relation = "same pet" if left_pet == right_pet else "different pets"
					conflicts.append(
						f"Time conflict ({relation}): "
						f"{left_task.task_id} ({left_pet}) overlaps with "
						f"{right_task.task_id} ({right_pet})"
					)

		return conflicts

	def detect_time_conflicts_lightweight(self) -> list[str]:
		"""Run conflict detection defensively for UI-safe behavior.

		This wrapper calls detect_time_conflicts() and suppresses unexpected
		exceptions so app flows can continue without crashing.

		Returns:
			The same conflict message list returned by detect_time_conflicts()
			when successful. If an exception occurs, returns a single warning
			message instructing the user to verify task times.
		"""
		try:
			return self.detect_time_conflicts()
		except Exception:
			return [
				"Warning: Conflict detection could not be completed. "
				"Please verify scheduled task times."
			]

	def _get_task_window(self, task: Task) -> tuple[datetime, datetime] | None:
		"""Build a normalized half-open time window for one task.

		Args:
			task: The task to normalize into a [start, end) interval.

		Returns:
			A tuple of (start, end) datetimes when the task has a valid window.
			If scheduled_start is missing or end is not after start, returns None.
			When scheduled_end is missing, end is inferred from estimated_duration.
		"""
		if task.scheduled_start is None:
			return None

		end_time = task.scheduled_end
		if end_time is None:
			end_time = task.scheduled_start + timedelta(minutes=task.estimated_duration)

		if end_time <= task.scheduled_start:
			return None

		return task.scheduled_start, end_time

	def filter_tasks(
		self,
		is_completed: bool | None = None,
		pet_name: str | None = None,
	) -> list[Task]:
		"""Return tasks from the daily queue matching the given filters.

		Args:
			is_completed: If provided, keep only tasks whose completion status
				matches this value.
			pet_name: If provided, keep only tasks assigned to the pet with
				this name (case-insensitive).

		Returns:
			A list of Task objects that satisfy all supplied filters.
		"""
		results = self.daily_queue

		if is_completed is not None:
			results = [t for t in results if t.is_completed == is_completed]

		if pet_name is not None:
			results = [
				t for t in results
				if t.pet is not None and t.pet.name.lower() == pet_name.lower()
			]

		return results

	def sort_by_time(self) -> list[Task]:
		"""Return tasks from the daily queue sorted by scheduled_start.

		Tasks with no scheduled_start are placed at the end.
		"""
		return sorted(
			self.daily_queue,
			key=lambda t: (t.scheduled_start is None, t.scheduled_start),
		)
	
