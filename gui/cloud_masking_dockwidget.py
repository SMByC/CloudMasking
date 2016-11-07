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
import tempfile

from PyQt4 import QtGui, uic, QtCore
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QMessageBox
from qgis.utils import iface

# from plugins
from CloudMasking.core import cloud_masking_utils

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'cloud_masking_dockwidget_base.ui'))


class CloudMaskingDockWidget(QtGui.QDockWidget, FORM_CLASS):

    # Fmask parameters by default
    cloud_buffer = 4
    shadow_buffer = 6
    cirrus_prob_ratio = 0.04
    nir_fill_thresh = 0.02
    swir2_thresh = 0.03
    whiteness_thresh = 0.7
    swir2_water_test = 0.03
    # Blue band by default
    bb_threshold_L457 = 110  # for L4, L5 and L7
    bb_threshold_L8 = 14000  # for L8

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
        self.status_LoadedMTL.setChecked(False)
        self.status_LoadedMTL.setText(self.tr(u"No MTL file loaded yet."))
        self.status_LoadedMTL.clicked.connect(self.onlyread)

        # FMask filters #########
        # start hidden
        self.widget_FMask.setHidden(True)
        # Synchronize the slider with the spin box
        # cloud_buffer
        self.horizontalSlider_CB.sliderMoved.connect(self.doubleSpinBox_CB.setValue)
        self.doubleSpinBox_CB.valueChanged.connect(self.horizontalSlider_CB.setValue)
        self.doubleSpinBox_CB.setValue(self.cloud_buffer)  # initial value
        # shadow_buffer
        self.horizontalSlider_SB.sliderMoved.connect(self.doubleSpinBox_SB.setValue)
        self.doubleSpinBox_SB.valueChanged.connect(self.horizontalSlider_SB.setValue)
        self.doubleSpinBox_SB.setValue(self.shadow_buffer)  # initial value
        # cirrus_prob_ratio (float values)
        self.horizontalSlider_CPR.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_CPR, self.horizontalSlider_CPR.value(), 1000))
        self.doubleSpinBox_CPR.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_CPR, self.doubleSpinBox_CPR.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_CPR, self.cirrus_prob_ratio, 1000)  # initial value
        self.update_slider(self.horizontalSlider_CPR, self.cirrus_prob_ratio, 1000)  # initial value
        # NIRFillThresh (float values)
        self.horizontalSlider_NFT.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_NFT, self.horizontalSlider_NFT.value(), 1000))
        self.doubleSpinBox_NFT.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_NFT, self.doubleSpinBox_NFT.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_NFT, self.nir_fill_thresh, 1000)  # initial value
        self.update_slider(self.horizontalSlider_NFT, self.nir_fill_thresh, 1000)  # initial value
        # Swir2Thresh (float values)
        self.horizontalSlider_S2T.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_S2T, self.horizontalSlider_S2T.value(), 1000))
        self.doubleSpinBox_S2T.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_S2T, self.doubleSpinBox_S2T.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_S2T, self.swir2_thresh, 1000)  # initial value
        self.update_slider(self.horizontalSlider_S2T, self.swir2_thresh, 1000)  # initial value
        # WhitenessThresh (float values)
        self.horizontalSlider_WT.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_WT, self.horizontalSlider_WT.value(), 1000))
        self.doubleSpinBox_WT.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_WT, self.doubleSpinBox_WT.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_WT, self.whiteness_thresh, 1000)  # initial value
        self.update_slider(self.horizontalSlider_WT, self.whiteness_thresh, 1000)  # initial value
        # Swir2WaterTest (float values)
        self.horizontalSlider_S2WT.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_S2WT, self.horizontalSlider_S2WT.value(), 1000))
        self.doubleSpinBox_S2WT.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_S2WT, self.doubleSpinBox_S2WT.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_S2WT, self.swir2_water_test, 1000)  # initial value
        self.update_slider(self.horizontalSlider_S2WT, self.swir2_water_test, 1000)  # initial value

        # Blue band threshold #########
        # start hidden
        self.widget_BlueBand.setHidden(True)
        # Synchronize the slider with the spin box
        self.horizontalSlider_BB.sliderMoved.connect(self.doubleSpinBox_BB.setValue)
        self.doubleSpinBox_BB.valueChanged.connect(self.horizontalSlider_BB.setValue)
        self.doubleSpinBox_BB.setValue(self.bb_threshold_L457)  # initial value

        # QA Masks filter #########
        # start hidden
        self.label_QA_FileStatus.setHidden(True)
        self.widget_QA_Masks_L457.setHidden(True)
        self.widget_QA_Masks_L8.setHidden(True)


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

        # Apply and save #########
        # start hidden
        self.radioButton_ToSR_RefStack.setHidden(True)
        self.widget_ApplyToFile.setHidden(True)

    # radiobutton status MTL
    @QtCore.pyqtSlot()
    def onlyread(self):
        if self.status_LoadedMTL.isChecked():
            self.status_LoadedMTL.setChecked(False)
        else:
            self.status_LoadedMTL.setChecked(True)

    ### SpinBox and Slider float connections (Qslider(int) with QdoubleSpinBox(float))
    def update_spinbox(self, spinbox, value, multiplier):
        spinbox.setValue(value/float(multiplier))
    def update_slider(self, slider, value, multiplier):
        slider.setValue(value*multiplier)

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
        dialog_mtl_path = str(QtGui.QFileDialog.
                            getOpenFileName(self, self.tr(u"Select the MTL file"),
                                            self.mtl_path if os.path.isdir(self.mtl_path)
                                            else os.path.dirname(self.mtl_path),
                                            self.tr(u"MTL files (*MTL.txt);;All files (*.*)")))
        if dialog_mtl_path != '':
            self.lineEdit_PathMTL.setText(dialog_mtl_path)

    @QtCore.pyqtSlot()
    def load_MTL(self):
        """Load MTL file currently specified in QLineEdit"""

        # process and load a new MTL file

        self.mtl_path = str(self.lineEdit_PathMTL.text())

        if not os.path.isfile(self.mtl_path):
            self.status_LoadedMTL.setText(self.tr(u"Error: File not exist"))
            return

        # load the MTL file
        try:
            self.mtl_file = cloud_masking_utils.mtl2dict(self.mtl_path)
            # get the landsat version
            self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])
        except:
            self.status_LoadedMTL.setText(self.tr(u"Error: Cannot parse MTL file"))
            return

        #### Process post MTL loaded (If we load it okay)
        # MTL info
        self.status_LoadedMTL.setChecked(True)
        self.status_LoadedMTL.setText(self.mtl_file['LANDSAT_SCENE_ID'] + ' (L{})'.format(self.landsat_version))

        # set QCflags if this MTL have QC file
        self.set_QCflags()

        #### activate, load and adjust UI
        self.activate_UI()

    def activate_UI(self):
        """UI adjust after load MTL file for some configurations
        based on landsat version or availability files"""

        #### first activate sections
        # Load stack and clear all #########
        self.button_ClearAll.setEnabled(True)
        self.groupBox_LoadStacks.setEnabled(True)
        # active filters box
        self.groupBox_Filters.setEnabled(True)
        # active generate cloud mask box
        self.groupBox_GenerateMask.setEnabled(True)
        # tmp dir for process this MTL
        self.tmp_dir = tempfile.mkdtemp()
        # activate SaveApply
        self.groupBox_SelectMask.setEnabled(True)
        self.groupBox_ApplyMask.setEnabled(True)

        #### set reflectance bands
        if self.landsat_version in [4, 5, 7]:
            self.reflectance_bands = [1, 2, 3, 4, 5, 7]
        if self.landsat_version in [8]:
            self.reflectance_bands = [2, 3, 4, 5, 6, 7]

        #### set items to RGB combobox
        self.label_SelectBands.setText("Select bands (Landsat {})".format(self.landsat_version))
        self.SelectBand_R.addItems([str(b) for b in self.reflectance_bands])
        self.SelectBand_G.addItems([str(b) for b in self.reflectance_bands])
        self.SelectBand_B.addItems([str(b) for b in self.reflectance_bands])

        #### blue Band adjusts UI limits
        if self.landsat_version in [8]:
            self.horizontalSlider_BB.setMaximum(40000)
            self.horizontalSlider_BB.setValue(self.bb_threshold_L8)
            self.doubleSpinBox_BB.setMaximum(40000)
            self.doubleSpinBox_BB.setValue(self.bb_threshold_L8)

        #### QA Masks adjusts
        # search and check QA Masks files
        if self.landsat_version in [4, 5, 7]:
            self.cloud_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                         self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_cloud_qa.tif"))
            self.shadow_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                              self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_cloud_shadow_qa.tif"))
            self.ddv_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                              self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_ddv_qa.tif"))
            # check QA files
            if os.path.isfile(self.cloud_qa_file) and os.path.isfile(self.shadow_qa_file) and os.path.isfile(self.ddv_qa_file):
                self.checkBox_QA_Masks.setEnabled(True)
                self.label_QA_FileStatus.setVisible(False)
                self.checkBox_QA_Masks.clicked.connect(self.widget_QA_Masks_L457.setVisible)
            else:
                self.label_QA_FileStatus.setVisible(True)
                self.widget_QA_Masks_L457.setVisible(False)
                self.checkBox_QA_Masks.setChecked(False)
                self.checkBox_QA_Masks.setEnabled(False)

        if self.landsat_version in [8]:
            self.cloud_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                         self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_cloud.tif"))

            if os.path.isfile(self.cloud_qa_file):
                self.label_QA_FileStatus.setVisible(False)
                self.checkBox_QA_Masks.setEnabled(True)
                self.checkBox_QA_Masks.clicked.connect(self.widget_QA_Masks_L8.setVisible)

                # fill the QlistWidget of QA code
                # TODO
                for n in range(30):
                    item = QtGui.QListWidgetItem('Item {}'.format(n))
                    item.setCheckState(QtCore.Qt.Unchecked)
                    self.listWidget_QA_codes.addItem(item)

            else:
                self.label_QA_FileStatus.setVisible(True)
                self.widget_QA_Masks_L8.setVisible(False)
                self.checkBox_QA_Masks.setEnabled(False)

        #### Enable apply to SR reflectance stack if are available
        exists_sr_files = \
            [os.path.isfile(f) for f in [os.path.join(os.path.dirname(self.mtl_path),
                self.mtl_file['FILE_NAME_BAND_' + str(N)].replace("_B", "_sr_band").replace(".TIF", ".tif"))
                for N in self.reflectance_bands]]
        if all(exists_sr_files):
            self.radioButton_ToSR_RefStack.setVisible(True)
            self.radioButton_ToSR_RefStack.setChecked(True)

    def set_QCflags(self):
        # TODO
        self.frame_QCflags.setHidden(True)

    def unload_MTL(self):
        """Disconnect, unload and remove temporal files of old MTL
        and old process
        """

        # MTL info
        self.status_LoadedMTL.setChecked(False)
        self.mtl_path = None
        # deactivate filters box
        self.groupBox_Filters.setEnabled(False)
        # deactivate save and apply box
        self.groupBox_SelectMask.setEnabled(False)
        self.groupBox_ApplyMask.setEnabled(False)
        self.radioButton_ToSR_RefStack.setHidden(True)
        self.radioButton_ToRefStack.setChecked(True)
        self.widget_ApplyToFile.setHidden(True)

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
