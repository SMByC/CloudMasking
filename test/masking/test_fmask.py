import sys


def test_only_fmask_default(init_qgis):

    from cloud_masking import CloudMasking

    from qgis.core import QgsApplication

    QGISAPP = QgsApplication(sys.argv, False)
    QGISAPP.initQgis()

    iface = init_qgis
    dockwidget = CloudMasking(iface)

    print dockwidget
    pass
