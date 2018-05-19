import os
import sys
import pytest


@pytest.fixture(scope="session", autouse=True)
def python_path_project():
    # add project dir to pythonpath
    project_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if project_dir not in sys.path:
        sys.path.append(project_dir)
