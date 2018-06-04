import os
import sys
import pytest


@pytest.fixture(scope="session", autouse=True)
def set_project_in_pythonpath():
    # add project dir to pythonpath
    project_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if project_dir not in sys.path:
        sys.path.append(project_dir)


@pytest.fixture(scope="session", autouse=True)
def set_qgis_in_pythonpath():
    qgis_dir = "/usr/share/qgis/python"
    if qgis_dir not in sys.path:
        sys.path.append(qgis_dir)


@pytest.fixture()
def init_qgis():
    import qgis
    from qgis_interface import QgisInterface
    iface = QgisInterface(None)
    return iface
