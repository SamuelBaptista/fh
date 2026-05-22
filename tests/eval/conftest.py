import json
from pathlib import Path
import pytest

FIXTURES_PATH = Path(__file__).parent.parent.parent / "assets" / "fixtures" / "test-cases.json"


@pytest.fixture
def test_cases():
    with open(FIXTURES_PATH) as f:
        data = json.load(f)
    return data


@pytest.fixture
def base_load_data(test_cases):
    return test_cases["base_load"]
