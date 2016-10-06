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
from time import sleep

from PyQt4 import QtGui, uic, QtCore
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QApplication

import cloud_masking_utils

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'cloud_masking_dockwidget_base.ui'))


class CloudMaskingDockWidget(QtGui.QDockWidget, FORM_CLASS):

    # Fmask parameters by default
    cirrus_prob_ratio = 0.04
    cloud_buffer = 150
    shadow_buffer = 300
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
        self.setupUi(self)
        self.setup_gui()
        # Setup default MTL file
        self.mtl_path = os.getcwd()  # path to MTL file
        self.mtl_file = None  # dict with all parameters of MTL file

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    def setup_gui(self):
        # find MTL file #########
        self.Btn_FindMTL.clicked.connect(self.fileDialog_findMTL)
        self.Btn_LoadMTL.clicked.connect(self.load_MTL)
        # MTL info
        self.kled_LoadedMTL.off()
        self.label_LoadedMTL.setText('No MTL file loaded yet')

        # FMask filters #########
        # start hidden
        self.widget_FMask.setHidden(True)
        # Synchronize the slider with the spin box
        # cirrus_prob_ratio
        #self.update_cirrus_prob_ratio(self.cirrus_prob_ratio)
        self.horizontalSlider_CPR.valueChanged.connect(self.update_cirrus_prob_ratio_slider)
        self.doubleSpinBox_CPR.valueChanged.connect(self.update_cirrus_prob_ratio_box)
        # cloud_buffer
        self.update_cloud_buffer(self.cloud_buffer)
        self.horizontalSlider_CB.valueChanged.connect(self.update_cloud_buffer)
        self.doubleSpinBox_CB.valueChanged.connect(self.update_cloud_buffer)
        # shadow_buffer
        self.update_shadow_buffer(self.shadow_buffer)
        self.horizontalSlider_SB.valueChanged.connect(self.update_shadow_buffer)
        self.doubleSpinBox_SB.valueChanged.connect(self.update_shadow_buffer)

        # Blue band threshold #########
        # start hidden
        self.widget_BlueBand.setHidden(True)
        # Synchronize the slider with the spin box
        self.update_bb_threshold(self.bb_threshold)
        self.horizontalSlider_BB.valueChanged.connect(self.update_bb_threshold)
        self.doubleSpinBox_BB.valueChanged.connect(self.update_bb_threshold)

        # Quality control flags #########
        # start hidden
        self.widget_QCflags.setHidden(True)

        # Generate the cloud mask #########
        # selected area start hidden
        self.widget_SelectedArea.setHidden(True)

        # Save and apply #########
        # start hidden
        self.widget_SaveApply_01.setHidden(True)
        self.widget_SaveApply_02.setHidden(True)

    @QtCore.pyqtSlot(int)
    def update_cirrus_prob_ratio_slider(self, value):
        self.doubleSpinBox_CPR.setValue(value/1000.0)

    @QtCore.pyqtSlot(float)
    def update_cirrus_prob_ratio_box(self, value):
        self.horizontalSlider_CPR.setValue(value*1000)

    @QtCore.pyqtSlot(int)
    def update_cloud_buffer(self, value):
        """Save value and connect the slider and spinbox
        """
        self.cloud_buffer = value
        self.horizontalSlider_CB.setValue(value)
        self.doubleSpinBox_CB.setValue(value)

    @QtCore.pyqtSlot(int)
    def update_shadow_buffer(self, value):
        """Save value and connect the slider and spinbox
        """
        self.shadow_buffer = value
        self.horizontalSlider_SB.setValue(value)
        self.doubleSpinBox_SB.setValue(value)

    @QtCore.pyqtSlot(int)
    def update_bb_threshold(self, value):
        """Save value and connect the slider and spinbox
        """
        self.bb_threshold = value
        self.horizontalSlider_BB.setValue(value)
        self.doubleSpinBox_BB.setValue(value)

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

        # first unload old MTL and clean temp files
        self.unload_MTL()

        self.mtl_path = str(self.lineEdit_PathMTL.text())

        if not os.path.isfile(self.mtl_path):
            self.label_LoadedMTL.setText('Error - file not exist')
            return

        # load the MTL file
        try:
            self.mtl_file = cloud_masking_utils.mtl2dict(self.mtl_path)
            # get the landsat version
            self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])
        except:
            self.label_LoadedMTL.setText('Error - cannot parse MTL file')
            return

        #### If we load it okay
        # MTL info
        self.kled_LoadedMTL.on()
        self.label_LoadedMTL.setText('{} (Landsat {})'.format(self.mtl_file['LANDSAT_SCENE_ID'],
                                                              self.landsat_version))
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

        #### Clean
        self.label_LoadedMTL.setText('Cleaning temporal files ...')
        # repaint
        self.label_LoadedMTL.repaint()
        QApplication.processEvents()
        sleep(1)

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
