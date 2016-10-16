# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMaskingDockWidget
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                             -------------------
        copyright            : (C) 2016 by Xavier Corredor Llano, SMBYC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import sys

from PyQt4 import QtGui, uic, QtCore
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QApplication
from qgis.utils import iface

plugin_folder = os.path.dirname(os.path.dirname(__file__))
if plugin_folder not in sys.path:
    sys.path.append(plugin_folder)

from core import cloud_masking_utils

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'cloud_masking_dockwidget_base.ui'))


class CloudMaskingDockWidget(QtGui.QDockWidget, FORM_CLASS):

    # Fmask parameters by default
    cirrus_prob_ratio = 0.04
    cloud_buffer = 5
    shadow_buffer = 10
    # Blue band by default
    bb_threshold = 10

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(CloudMaskingDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.canvas = iface.mapCanvas()
        self.setupUi(self)
        self.setup_gui()
        # Setup default MTL file
        self.mtl_path = os.getcwd()  # path to MTL file
        self.mtl_file = None  # dict with all parameters of MTL file
        self.isExtentAreaSelected = False

    def closeEvent(self, event):
        self.widget_ExtentSelector.stop()
        self.closingPlugin.emit()
        event.accept()

    def setup_gui(self):
        # find MTL file #########
        self.button_FindMTL.clicked.connect(self.fileDialog_findMTL)
        # load MTL: this is called from cloud_masking
        # MTL info
        self.kled_LoadedMTL.off()
        self.label_LoadedMTL_1.setText('No MTL file loaded yet.')
        self.label_LoadedMTL_2.setText('')

        # FMask filters #########
        # start hidden
        self.widget_FMask.setHidden(True)
        # Synchronize the slider with the spin box
        # cirrus_prob_ratio
        self.horizontalSlider_CPR.valueChanged.connect(self.update_cirrus_prob_ratio_slider)
        self.doubleSpinBox_CPR.valueChanged.connect(self.update_cirrus_prob_ratio_box)
        self.update_cirrus_prob_ratio_box(self.cirrus_prob_ratio)  # initial value
        # cloud_buffer
        self.horizontalSlider_CB.sliderMoved.connect(self.doubleSpinBox_CB.setValue)
        self.doubleSpinBox_CB.valueChanged.connect(self.horizontalSlider_CB.setValue)
        self.doubleSpinBox_CB.setValue(self.cloud_buffer)  # initial value
        # shadow_buffer
        self.horizontalSlider_SB.sliderMoved.connect(self.doubleSpinBox_SB.setValue)
        self.doubleSpinBox_SB.valueChanged.connect(self.horizontalSlider_SB.setValue)
        self.doubleSpinBox_SB.setValue(self.shadow_buffer)  # initial value

        # Blue band threshold #########
        # start hidden
        self.widget_BlueBand.setHidden(True)
        # Synchronize the slider with the spin box
        self.horizontalSlider_BB.sliderMoved.connect(self.doubleSpinBox_BB.setValue)
        self.doubleSpinBox_BB.valueChanged.connect(self.horizontalSlider_BB.setValue)
        self.doubleSpinBox_BB.setValue(self.bb_threshold)  # initial value

        # Quality control flags #########
        # start hidden
        self.widget_QCflags.setHidden(True)

        # Generate the cloud mask #########
        # selected area start hidden
        self.widget_ExtentSelector.setHidden(True)

        # Extent selector widget #########
        # set the extent selector
        self.widget_ExtentSelector.setCanvas(self.canvas)
        # connections
        self.widget_ExtentSelector.newExtentDefined.connect(self.extentChanged)
        self.widget_ExtentSelector.selectionStarted.connect(self.checkRun)
        self.checkBox_ExtentSelector.toggled.connect(self.switchClippingMode)

        # Save and apply #########
        # start hidden
        self.widget_SaveApply_01.setHidden(True)
        self.widget_SaveApply_02.setHidden(True)

    ### Cirrus prob ratio - for connect Qslider(int) with QdoubleSpinBox(float)
    @QtCore.pyqtSlot(int)
    def update_cirrus_prob_ratio_slider(self, value):
        self.doubleSpinBox_CPR.setValue(value/1000.0)
    @QtCore.pyqtSlot(float)
    def update_cirrus_prob_ratio_box(self, value):
        self.horizontalSlider_CPR.setValue(value*1000)

    ### Extent selector widget
    def switchClippingMode(self):
        if self.checkBox_ExtentSelector.isChecked():
            self.widget_ExtentSelector.start()
        else:
            self.widget_ExtentSelector.stop()
        self.checkRun()
    def checkRun(self):
        if self.checkBox_ExtentSelector.isChecked():
            self.isExtentAreaSelected = self.widget_ExtentSelector.isCoordsValid()
        else:
            self.isExtentAreaSelected = False
    def extentChanged(self):
        self.activateWindow()
        self.raise_()
        self.checkRun()

    @QtCore.pyqtSlot()
    def fileDialog_findMTL(self):
        """Open QFileDialog to find a MTL file
        """
        self.mtl_path = str(QtGui.QFileDialog.
                            getOpenFileName(self, self.tr('Select the MTL file'),
                                            self.mtl_path if os.path.isdir(self.mtl_path)
                                            else os.path.dirname(self.mtl_path),
                                            self.tr("MTL file (*MTL.txt);;All files (*.*)")))
        if self.mtl_path != '':
            self.lineEdit_PathMTL.setText(self.mtl_path)

    @QtCore.pyqtSlot()
    def load_MTL(self):
        """Load MTL file currently specified in QLineEdit"""

        # TODO: first prompt to user if delete the current
        # process and load a new MTL file

        self.mtl_path = str(self.lineEdit_PathMTL.text())

        if not os.path.isfile(self.mtl_path):
            self.label_LoadedMTL_1.setText('Error:')
            self.label_LoadedMTL_2.setText('File not exist')
            return

        # load the MTL file
        try:
            self.mtl_file = cloud_masking_utils.mtl2dict(self.mtl_path)
            # get the landsat version
            self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])
        except:
            self.label_LoadedMTL_1.setText('Error:')
            self.label_LoadedMTL_2.setText('Cannot parse MTL file')
            return

        #### If we load it okay
        # MTL info
        self.kled_LoadedMTL.on()
        self.label_LoadedMTL_1.setText(self.mtl_file['LANDSAT_SCENE_ID'])
        self.label_LoadedMTL_2.setText('Landsat {}'.format(self.landsat_version))
        # Load stack and clear all #########
        self.button_ClearAll.setEnabled(True)
        self.groupBox_LoadStacks.setEnabled(True)
        # active filters box
        self.groupBox_Filters.setEnabled(True)
        #self.groupBox_Filters.setChecked(True)
        # active generate cloud mask box
        self.groupBox_GenerateMask.setEnabled(True)

    def unload_MTL(self):
        """Disconnect, unload and remove temporal files of old MTL
        and old process
        """

        # MTL info
        self.kled_LoadedMTL.off()
        # deactivate filters box
        self.groupBox_Filters.setEnabled(False)
        self.groupBox_Filters.setChecked(False)
        # deactivate save and apply box
        self.groupBox_SaveApply.setEnabled(False)
        self.groupBox_SaveApply.setChecked(False)

        # Load stack and clear all #########
        self.button_ClearAll.setEnabled(False)
        self.groupBox_LoadStacks.setEnabled(False)

        # TODO: Removing temporary files
        # for _tmp in self.temp_files:
        #     # Try deleting with GDAL
        #     try:
        #         ds = gdal.Open(_tmp.name, gdal.GA_Update)
        #         driver = ds.GetDriver()
        #         for f in ds.GetFileList():
        #             logger.info('Removing file {f}'.format(f=f))
        #             driver.Delete(f)
        #     except:
        #         logger.warning('Could not delete {f} using GDAL'.format(f=f))
        #
        #     # Try deleting using tempfile
        #     try:
        #         _tmp.close()
        #     except:
        #         pass
