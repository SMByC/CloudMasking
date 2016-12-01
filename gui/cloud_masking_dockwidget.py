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
from qgis.utils import iface
from PyQt4.QtGui import QMessageBox

# from plugins
from CloudMasking.core import cloud_masking_utils
from CloudMasking.core.utils import get_prefer_name

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

        # Cloud QA filter #########
        # start hidden
        self.label_CloudQA_FileStatus.setHidden(True)
        self.widget_CloudQA_L457.setHidden(True)
        self.widget_CloudQA_L8.setHidden(True)
        self.widget_CloudQA_Aerosol.setHidden(True)

        # QA Band filter #########
        # start hidden
        self.label_QABand_FileStatus.setHidden(True)
        self.widget_QABand.setHidden(True)
        self.widget_QA_Water.setHidden(True)
        self.widget_QA_SnowIce.setHidden(True)
        self.widget_QA_Cirrus.setHidden(True)
        self.widget_QA_Cloud.setHidden(True)

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
                                            "", self.tr(u"MTL files (*MTL.txt);;All files (*.*)")))
        if dialog_mtl_path != '':
            self.lineEdit_PathMTL.setText(dialog_mtl_path)

    @QtCore.pyqtSlot()
    def load_MTL(self):
        """Load a new MTL file currently specified in QLineEdit"""

        self.mtl_path = str(self.lineEdit_PathMTL.text())

        # check if MTL exist
        if not os.path.isfile(self.mtl_path):
            self.status_LoadedMTL.setText(self.tr(u"Error: File not exist"))
            self.unload_MTL()
            return

        # parse the new MTL file
        try:
            self.mtl_file = cloud_masking_utils.mtl2dict(self.mtl_path)
            # get the landsat version
            self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'].split('_')[-1])
        except:
            self.status_LoadedMTL.setText(self.tr(u"Error: Cannot parse MTL file"))
            self.unload_MTL()
            return

        # check if there are the basic images for process
        # these are: "_bandX.tif" or "_BX.TIF"
        #
        # set bands for reflective and thermal
        if self.landsat_version in [4, 5]:
            # get the reflective file names bands
            reflective_and_thermal_bands = [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1, 2, 3, 4, 5, 7, 6]]
        if self.landsat_version in [7]:
            # get the reflective file names bands
            reflective_and_thermal_bands = [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1, 2, 3, 4, 5, 7]]
            reflective_and_thermal_bands += [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_6_VCID_' + str(N)])
                for N in [1, 2]]
        if self.landsat_version in [8]:
            # get the reflective file names bands
            reflective_and_thermal_bands = [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_'+str(N)])
                for N in [1, 2, 3, 4, 5, 6, 7, 9, 10, 11]]

        # set the prefer file name band for process
        reflective_and_thermal_bands = [get_prefer_name(file_path) for file_path in reflective_and_thermal_bands]

        # check if reflective_and_thermal_bands exists
        for file_path in reflective_and_thermal_bands:
            if not os.path.isfile(file_path):
                msg = "The file {} not exists , is necessary that the raw bands _bandN.tif or _BN.TIF of Landsat " \
                           "are in the same location as the MTL file.".format(os.path.basename(file_path))
                QMessageBox.question(self, 'Problem while Loading the new MTL...',
                                             msg, QMessageBox.Ok)
                self.status_LoadedMTL.setText(self.tr(u"Error: Not raw landsat files"))
                self.unload_MTL()
                return

        #### Process post MTL loaded (If we load it okay)
        # MTL info
        self.status_LoadedMTL.setChecked(True)
        self.status_LoadedMTL.setText(self.mtl_file['LANDSAT_SCENE_ID'] + ' (L{})'.format(self.landsat_version))

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

        #### Cloud QA adjusts
        # search and check Cloud QA files
        if self.landsat_version in [4, 5, 7]:
            self.cloud_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                         self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_cloud_qa.tif"))
            self.shadow_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                              self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_cloud_shadow_qa.tif"))
            self.adjacent_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                              self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_adjacent_cloud_qa.tif"))
            # check Cloud QA files
            if os.path.isfile(self.cloud_qa_file) and os.path.isfile(self.shadow_qa_file) and os.path.isfile(self.adjacent_qa_file):
                self.checkBox_CloudQA.setEnabled(True)
                self.label_CloudQA_FileStatus.setVisible(False)
                try: self.checkBox_CloudQA.clicked.disconnect()
                except: pass
                self.widget_CloudQA_L8.setHidden(True)
                self.checkBox_CloudQA.setChecked(False)
                self.checkBox_CloudQA.clicked.connect(self.widget_CloudQA_L457.setVisible)
            else:
                self.label_CloudQA_FileStatus.setVisible(True)
                self.widget_CloudQA_L457.setHidden(True)
                self.checkBox_CloudQA.setChecked(False)
                self.checkBox_CloudQA.setEnabled(False)

        if self.landsat_version in [8]:
            self.cloud_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                         self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_sr_cloud.tif"))
            # check Cloud QA file
            if os.path.isfile(self.cloud_qa_file):
                self.label_CloudQA_FileStatus.setVisible(False)
                self.checkBox_CloudQA.setEnabled(True)
                try: self.checkBox_CloudQA.clicked.disconnect()
                except: pass
                self.widget_CloudQA_L457.setHidden(True)
                self.checkBox_CloudQA.setChecked(False)
                self.checkBox_CloudQA.clicked.connect(self.widget_CloudQA_L8.setVisible)
            else:
                self.label_CloudQA_FileStatus.setVisible(True)
                self.widget_CloudQA_L8.setHidden(True)
                self.checkBox_CloudQA.setChecked(False)
                self.checkBox_CloudQA.setEnabled(False)

        #### QA Band adjusts
        # search and check QA Band file
        self.qa_band_file = os.path.join(os.path.dirname(self.mtl_path),
                                         self.mtl_file['FILE_NAME_BAND_1'].replace("_B1.TIF", "_qa.tif"))
        # check QA Band file exists
        if os.path.isfile(self.qa_band_file):
            self.checkBox_QABand.setEnabled(True)
            self.label_QABand_FileStatus.setVisible(False)
            self.checkBox_QABand.clicked.connect(self.widget_QABand.setVisible)
        else:
            self.label_QABand_FileStatus.setVisible(True)
            self.widget_QABand.setVisible(False)
            self.checkBox_QABand.setChecked(False)
            self.checkBox_QABand.setEnabled(False)

        #### Enable apply to SR reflectance stack if are available
        exists_sr_files = \
            [os.path.isfile(f) for f in [os.path.join(os.path.dirname(self.mtl_path),
                self.mtl_file['FILE_NAME_BAND_' + str(N)].replace("_B", "_sr_band").replace(".TIF", ".tif"))
                for N in self.reflectance_bands]]
        if all(exists_sr_files):
            self.radioButton_ToSR_RefStack.setVisible(True)
            self.radioButton_ToSR_RefStack.setChecked(True)

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

