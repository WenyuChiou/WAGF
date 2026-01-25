"""Education domain environment observer."""
from typing import Any, Dict, List
from ..environment import EnvironmentObserver


class EducationEnvironmentObserver(EnvironmentObserver):
    """
    Environment observer for educational psychology domain.

    Agents can sense:
    - School/institutional environment
    - Academic calendar events
    - Educational opportunities
    """

    @property
    def domain(self) -> str:
        return "education"

    def sense_state(
        self,
        agent: Any,
        environment: Any
    ) -> Dict[str, Any]:
        """Sense education-relevant environment state."""
        sensed = {}

        # Academic term/semester
        if hasattr(environment, "current_semester"):
            sensed["current_semester"] = environment.current_semester
        if hasattr(environment, "academic_year"):
            sensed["academic_year"] = environment.academic_year

        # School quality metrics
        if hasattr(environment, "get_school_rating"):
            school = getattr(agent, "school_name", None)
            if school:
                sensed["school_rating"] = environment.get_school_rating(school)

        # Class size / student-teacher ratio
        if hasattr(environment, "student_teacher_ratio"):
            sensed["student_teacher_ratio"] = environment.student_teacher_ratio

        # Available programs/courses
        if hasattr(environment, "available_programs"):
            sensed["available_programs"] = environment.available_programs

        # Scholarship availability
        if hasattr(environment, "scholarship_available"):
            sensed["scholarship_available"] = environment.scholarship_available

        # Job market for graduates
        if hasattr(environment, "graduate_employment_rate"):
            sensed["graduate_employment_rate"] = environment.graduate_employment_rate

        return sensed

    def detect_events(
        self,
        agent: Any,
        environment: Any
    ) -> List[Dict[str, Any]]:
        """Detect education-related events."""
        events = []

        # Enrollment deadline
        if hasattr(environment, "enrollment_deadline_approaching"):
            if environment.enrollment_deadline_approaching:
                events.append({
                    "event_type": "enrollment_deadline",
                    "description": "Enrollment deadline approaching",
                    "severity": "moderate",
                })

        # Exam period
        if hasattr(environment, "exam_period") and environment.exam_period:
            events.append({
                "event_type": "exam_period",
                "description": "Examination period is active",
                "severity": "moderate",
            })

        # Graduation ceremony
        if hasattr(environment, "graduation_ceremony") and environment.graduation_ceremony:
            events.append({
                "event_type": "graduation",
                "description": "Graduation ceremony scheduled",
                "severity": "low",
            })

        # School closure
        if hasattr(environment, "school_closed") and environment.school_closed:
            events.append({
                "event_type": "school_closure",
                "description": "School temporarily closed",
                "severity": "high",
            })

        # New program available
        if hasattr(environment, "new_program_announced") and environment.new_program_announced:
            events.append({
                "event_type": "new_program",
                "description": "New educational program available",
                "severity": "low",
            })

        return events

    def get_observation_accuracy(
        self,
        agent: Any,
        variable: str
    ) -> float:
        """
        Get accuracy based on educational engagement.

        More engaged students/parents have better information.
        """
        base_accuracy = 0.75

        # Better accuracy if enrolled
        if getattr(agent, "enrolled_in_school", False):
            base_accuracy += 0.15

        # Better accuracy if parent is involved
        if getattr(agent, "parent_involvement", 0) > 0.5:
            base_accuracy += 0.1

        return min(base_accuracy, 1.0)
