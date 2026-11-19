import pytest
from app.verification import InvalidSchedule, verify_schedule


def test_small_schedule_score_is_calculated_independently():
    assert verify_schedule([9, 8, 7, 6], [0, 1, 1, 0], 2) == 15


@pytest.mark.parametrize("assignments", [[0, 1, 0], [0, 2], [-1, 0], [True, 0], [0, "1"]])
def test_verifier_rejects_missing_extra_or_invalid_machines(assignments):
    with pytest.raises(InvalidSchedule):
        verify_schedule([4, 5], assignments, 2)


def test_wrong_durations_are_rejected():
    with pytest.raises(InvalidSchedule):
        verify_schedule([0, 5], [0, 1], 2)




def test_many_seeded_schedules_respect_bounds_without_optional_dependencies():
    import random

    randomizer = random.Random(5001)
    for _ in range(200):
        machine_count = randomizer.randint(1, 10)
        durations = [randomizer.randint(1, 150) for _ in range(randomizer.randint(1, 40))]
        assignments = [randomizer.randrange(machine_count) for _ in durations]
        score = verify_schedule(durations, assignments, machine_count)
        assert max(durations) <= score <= sum(durations)
        assert score >= (sum(durations) + machine_count - 1) // machine_count
