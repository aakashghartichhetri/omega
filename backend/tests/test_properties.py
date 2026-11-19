"""Property-based tests for the independent verifier."""
import pytest
from app.verification import InvalidSchedule, verify_schedule

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, strategies as st


@given(st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=40),
       st.integers(min_value=1, max_value=10), st.integers(min_value=0, max_value=2**32 - 1))
def test_property_every_valid_schedule_respects_load_bounds(durations, machines, seed):
    import random
    assignments = [random.Random(seed + i).randrange(machines) for i in range(len(durations))]
    makespan = verify_schedule(durations, assignments, machines)
    assert max(durations) <= makespan <= sum(durations)
    assert makespan >= (sum(durations) + machines - 1) // machines


@given(st.lists(st.integers(min_value=1, max_value=100), min_size=1, max_size=30))
def test_property_extra_job_is_always_rejected(durations):
    with pytest.raises(InvalidSchedule):
        verify_schedule(durations, [0] * (len(durations) + 1), 2)
