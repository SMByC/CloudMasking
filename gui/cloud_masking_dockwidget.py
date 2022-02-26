# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMaskingDockWidget
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                             -------------------
        copyright            : (C) 2016-2022 by Xavier Corredor Llano, SMByC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import configparser
import os
import tempfile
import webbrowser

from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, pyqtSlot, QTimer, Qt
from qgis.core import QgsWkbTypes, QgsFeature, edit, QgsVectorLayer
from qgis.gui import QgsMapTool, QgsRubberBand, QgsMapToolPan
from qgis.PyQt.QtGui import QColor
from qgis.utils import iface
from qgis.PyQt.QtWidgets import QFileDialog, QDockWidget

# from plugins
from CloudMasking.core import cloud_masking_utils
from CloudMasking.core.utils import get_prefer_name
from CloudMasking.gui.about_dialog import AboutDialog

# plugin path
plugin_folder = os.path.dirname(os.path.dirname(__file__))
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    plugin_folder, 'ui', 'cloud_masking_dockwidget_base.ui'))

cfg = configparser.ConfigParser()
cfg.read(os.path.join(plugin_folder, 'metadata.txt'))
VERSION = cfg.get('general', 'version')
HOMEPAGE = cfg.get('general', 'homepage')


class CloudMaskingDockWidget(QDockWidget, FORM_CLASS):
    # Fmask parameters by default
    cloud_prob_thresh = 0.225
    cloud_buffer = 4
    shadow_buffer = 6
    cirrus_prob_ratio = 0.04
    nir_fill_thresh = 0.02
    swir2_thresh = 0.03
    whiteness_thresh = 0.7
    swir2_water_test = 0.03
    nir_snow_thresh = 0.11
    green_snow_thresh = 0.1
    # Blue Band by default
    bb_threshold_L457 = 110  # for L4, L5 and L7
    bb_threshold_L89 = 14000  # for L89

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

    def closeEvent(self, event):
        self.delete_all_aoi()
        self.restart_map_tool()
        self.closingPlugin.emit()
        event.accept()

    def setup_gui(self):
        # plugin info #########
        self.about_dialog = AboutDialog()
        self.QPBtn_PluginInfo.setText("v{}".format(VERSION))
        self.QPBtn_PluginInfo.clicked.connect(self.about_dialog.show)

        # find MTL file #########
        self.button_FindMTL.clicked.connect(self.fileDialog_findMTL)
        # load MTL: this is called from cloud_masking
        # MTL info
        self.status_LoadedMTL.setChecked(False)
        self.status_LoadedMTL.setText(self.tr("No MTL file loaded yet."))
        self.status_LoadedMTL.clicked.connect(self.onlyread)

        # FMask filters #########
        # start hidden
        self.widget_FMask.setHidden(True)
        self.widget_FMask_advanced.setHidden(True)
        self.FMask_FileStatus.setHidden(True)
        self.checkBox_FMask.setChecked(False)
        # Synchronize the slider with the spin box
        # Cloud probability threshold
        self.horizontalSlider_CPT.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_CPT, self.horizontalSlider_CPT.value(), 1000))
        self.doubleSpinBox_CPT.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_CPT, self.doubleSpinBox_CPT.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_CPT, self.cloud_prob_thresh, 1000)  # initial value
        self.update_slider(self.horizontalSlider_CPT, self.cloud_prob_thresh, 1000)  # initial value
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
        # NirSnowThresh (float values)
        self.horizontalSlider_NST.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_NST, self.horizontalSlider_NST.value(), 1000))
        self.doubleSpinBox_NST.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_NST, self.doubleSpinBox_NST.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_NST, self.nir_snow_thresh, 1000)  # initial value
        self.update_slider(self.horizontalSlider_NST, self.nir_snow_thresh, 1000)  # initial value
        # GreenSnowThresh (float values)
        self.horizontalSlider_GST.valueChanged.connect(
            lambda: self.update_spinbox(self.doubleSpinBox_GST, self.horizontalSlider_GST.value(), 1000))
        self.doubleSpinBox_GST.valueChanged.connect(
            lambda: self.update_slider(self.horizontalSlider_GST, self.doubleSpinBox_GST.value(), 1000))
        self.update_spinbox(self.doubleSpinBox_GST, self.green_snow_thresh, 1000)  # initial value
        self.update_slider(self.horizontalSlider_GST, self.green_snow_thresh, 1000)  # initial value

        # Blue Band threshold #########
        # start hidden
        self.widget_BlueBand.setHidden(True)
        self.checkBox_BlueBand.setChecked(False)
        # Synchronize the slider with the spin box
        self.horizontalSlider_BB.sliderMoved.connect(self.doubleSpinBox_BB.setValue)
        self.doubleSpinBox_BB.valueChanged.connect(self.horizontalSlider_BB.setValue)
        self.doubleSpinBox_BB.setValue(self.bb_threshold_L457)  # initial value

        # Cloud QA L457 filter #########
        # start hidden
        self.label_CloudQA_FileStatus.setHidden(True)
        self.frame_CloudQA_L457.setHidden(True)
        self.widget_CloudQA_L457.setHidden(True)
        self.checkBox_CloudQA.setChecked(False)

        # Aerosol L89 filter #########
        # start hidden
        self.frame_Aerosol_L89.setHidden(True)
        self.label_Aerosol_FileStatus.setHidden(True)
        self.widget_Aerosol_L89.setHidden(True)
        self.widget_Aerosol_Content.setHidden(True)
        self.checkBox_Aerosol.setChecked(False)

        # Pixel QA filter #########
        # start hidden
        self.PixelQA_FileStatus.setHidden(True)
        self.widget_PixelQA.setHidden(True)
        self.widget_CloudConfidence.setHidden(True)
        self.widget_CirrusConfidence.setHidden(True)
        # only for landsat 8
        self.groupBox_CirrusConfidence.setHidden(True)
        self.PixelQA_TerrainO_mask.setHidden(True)
        self.checkBox_PixelQA.setChecked(False)

        # QA Band C1 L457 filter #########
        # start hidden
        self.QABandC1L457_FileStatus.setVisible(False)
        self.checkBox_QABandC1L457.setChecked(False)
        self.widget_QABandC1L457.setHidden(True)
        self.QABandC1L89_FileStatus.setVisible(False)
        self.checkBox_QABandC1L89.setChecked(False)
        self.widget_QABandC1L89.setHidden(True)
        self.groupBox_RadiometricSaturation_qabandl457.setHidden(True)
        self.widget_CloudConfidence_qabandl457.setHidden(True)
        self.widget_CloudShadow_qabandl457.setHidden(True)
        self.widget_SnowIce_qabandl457.setHidden(True)
        # QA Band C1 L89 filter #########
        self.widget_RadiometricSaturation_qabandl89.setHidden(True)
        self.widget_CloudConfidence_qabandl89.setHidden(True)
        self.widget_CloudShadow_qabandl89.setHidden(True)
        self.widget_SnowIce_qabandl89.setHidden(True)
        self.widget_CirrusConfidence_qabandl89.setHidden(True)

        # QA Band C2 filter #########
        # start hidden
        self.QABandC2_FileStatus.setVisible(False)
        self.checkBox_QABandC2.setChecked(False)
        self.widget_QABandC2.setHidden(True)
        self.widget_CloudConfidence_qabandc2.setHidden(True)
        self.widget_CloudShadowConfidence_qabandc2.setHidden(True)
        self.widget_SnowIceConfidence_qabandc2.setHidden(True)
        self.widget_CirrusConfidence_qabandc2.setHidden(True)

        # Generate the cloud mask #########
        # shape and selected area start hidden
        self.widget_AOISelector.setHidden(True)
        self.widget_ShapeSelector.setHidden(True)

        # show/hide blocks in only aoi or shape file
        def selector(widget_from, widget_to):
            if widget_from.isChecked():
                widget_to.setChecked(False)

        self.checkBox_AOISelector.toggled.connect(
            lambda: selector(self.checkBox_AOISelector, self.checkBox_ShapeSelector))
        self.checkBox_ShapeSelector.toggled.connect(
            lambda: selector(self.checkBox_ShapeSelector, self.checkBox_AOISelector))

        # AOI picker
        self.VisibleAOI.clicked.connect(self.visible_aoi)
        self.AOI_Picker.clicked.connect(
            lambda: self.canvas.setMapTool(PickerAOIPointTool(self), clean=True))
        self.UndoAOI.clicked.connect(self.undo_aoi)
        self.DeleteAllAOI.clicked.connect(self.delete_all_aoi)
        self.pan_zoom_tool = QgsMapToolPan(self.canvas)
        self.rubber_bands = []
        self.tmp_rubber_bands = []
        # init temporal AOI layer
        self.aoi_features = None

        # Extent selector widget #########
        self.checkBox_AOISelector.toggled.connect(self.switchClippingMode)

        # Apply and save #########
        # start hidden
        self.radioButton_ToSR_Bands.setEnabled(False)
        self.widget_ApplyToFile.setHidden(True)

    # radiobutton status MTL
    @pyqtSlot()
    def onlyread(self):
        if self.status_LoadedMTL.isChecked():
            self.status_LoadedMTL.setChecked(False)
        else:
            self.status_LoadedMTL.setChecked(True)

    ### SpinBox and Slider float connections (Qslider(int) with QdoubleSpinBox(float))
    def update_spinbox(self, spinbox, value, multiplier):
        spinbox.setValue(value / float(multiplier))

    def update_slider(self, slider, value, multiplier):
        slider.setValue(int(round(value * multiplier, 0)))

    ### Extent selector widget
    def switchClippingMode(self):
        if self.checkBox_AOISelector.isChecked():
            self.VisibleAOI.setChecked(True)
            self.visible_aoi()
        elif self.VisibleAOI.isChecked():
            self.VisibleAOI.setChecked(False)
            self.visible_aoi()

    @pyqtSlot()
    def fileDialog_findMTL(self):
        """Open QFileDialog to find a MTL file
        """
        dialog_mtl_path, _ = QFileDialog.getOpenFileName(self, self.tr("Select the MTL file"),
                                                         "", self.tr("MTL files (*MTL.txt);;All files (*.*)"))
        if dialog_mtl_path != '':
            self.lineEdit_PathMTL.setText(dialog_mtl_path)

    @pyqtSlot()
    def load_MTL(self):
        """Load a new MTL file currently specified in QLineEdit"""

        self.mtl_path = self.lineEdit_PathMTL.text()

        # check if MTL exist
        if not os.path.isfile(self.mtl_path):
            self.status_LoadedMTL.setText(self.tr("Error: File not exist"))
            self.unload_MTL()
            return

        # parse the new MTL file
        try:
            self.mtl_file = cloud_masking_utils.mtl2dict(self.mtl_path)
            # get the landsat version
            self.landsat_version = int(self.mtl_file['SPACECRAFT_ID'][-1])
            if 'COLLECTION_NUMBER' in self.mtl_file:
                self.collection = int(self.mtl_file['COLLECTION_NUMBER'])
            else:
                self.collection = 1
                self.mtl_file['COLLECTION_NUMBER'] = 1
            if 'PROCESSING_LEVEL' in self.mtl_file:
                self.processing_level = self.mtl_file['PROCESSING_LEVEL'][0:2]
            else:
                self.processing_level = "L1"
                self.mtl_file['PROCESSING_LEVEL'] = "L1"
            # normalize metadata for old MLT format (old Landsat 4 and 5)
            if 'BAND1_FILE_NAME' in self.mtl_file:
                for N in [1, 2, 3, 4, 5, 7, 6]:
                    self.mtl_file['FILE_NAME_BAND_' + str(N)] = self.mtl_file['BAND' + str(N) + '_FILE_NAME']
            if 'METADATA_L1_FILE_NAME' in self.mtl_file:
                self.mtl_file['LANDSAT_SCENE_ID'] = self.mtl_file['METADATA_L1_FILE_NAME'].split('_MTL.txt')[0]
        except:
            self.status_LoadedMTL.setText(self.tr("Error: Cannot parse MTL file"))
            self.unload_MTL()
            return

        # check if there are the basic images for process
        # these are: "_bandX.tif" or "_BX.TIF"
        #
        # set bands for reflective and thermal
        if self.landsat_version in [4, 5]:
            # get the reflective file names bands
            reflective_and_thermal_bands = [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_' + str(N)])
                for N in [1, 2, 3, 4, 5, 7, 6]]
        if self.landsat_version in [7]:
            # get the reflective file names bands
            reflective_and_thermal_bands = [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_' + str(N)])
                for N in [1, 2, 3, 4, 5, 7]]
            reflective_and_thermal_bands += [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_6_VCID_' + str(N)])
                for N in [1, 2]]
        if self.landsat_version in [8, 9]:
            # get the reflective file names bands
            reflective_and_thermal_bands = [
                os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_' + str(N)])
                for N in [1, 2, 3, 4, 5, 6, 7, 9, 10, 11]]

        # set the prefer file name band for process
        reflective_and_thermal_bands = [get_prefer_name(file_path) for file_path in reflective_and_thermal_bands]

        # check if reflective_and_thermal_bands exists
        self.FMask_FileStatus.setHidden(True)
        self.frame_FMask.setEnabled(True)
        for file_path in reflective_and_thermal_bands:
            if not os.path.isfile(file_path):
                self.FMask_FileStatus.setVisible(True)
                self.frame_FMask.setEnabled(False)

        #### Process post MTL loaded (If we load it okay)
        # tmp dir for process this MTL
        self.tmp_dir = tempfile.mkdtemp()
        # MTL info
        self.status_LoadedMTL.setChecked(True)
        self.status_LoadedMTL.setText(self.mtl_file['LANDSAT_SCENE_ID']
                                      + ' (L{}) (C{})'.format(self.landsat_version, self.collection))

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
        # activate SaveApply
        self.groupBox_SelectMask.setEnabled(True)
        self.groupBox_ApplyMask.setEnabled(True)

        #### set reflectance bands
        if self.landsat_version in [4, 5, 7]:
            self.reflectance_bands = [1, 2, 3, 4, 5, 7]
        if self.landsat_version in [8, 9]:
            self.reflectance_bands = [2, 3, 4, 5, 6, 7]

        #### set items to RGB combobox
        self.label_SelectBands.setText("Bands to visualize (Landsat {}):".format(self.landsat_version))
        self.SelectBand_R.addItems([str(b) for b in self.reflectance_bands])
        self.SelectBand_G.addItems([str(b) for b in self.reflectance_bands])
        self.SelectBand_B.addItems([str(b) for b in self.reflectance_bands])
        self.SelectBand_R.setCurrentIndex(-1)
        self.SelectBand_G.setCurrentIndex(-1)
        self.SelectBand_B.setCurrentIndex(-1)

        #### blue Band adjusts UI limits
        if self.landsat_version in [4, 5, 7]:
            self.horizontalSlider_BB.setMaximum(255)
            self.horizontalSlider_BB.setValue(self.bb_threshold_L457)
            self.doubleSpinBox_BB.setMaximum(255)
            self.doubleSpinBox_BB.setValue(self.bb_threshold_L457)
        if self.landsat_version in [8, 9]:
            self.horizontalSlider_BB.setMaximum(40000)
            self.horizontalSlider_BB.setValue(self.bb_threshold_L89)
            self.doubleSpinBox_BB.setMaximum(40000)
            self.doubleSpinBox_BB.setValue(self.bb_threshold_L89)

        #### Cloud QA L457 adjusts
        # hidden blocks and unchecked
        self.frame_CloudQA_L457.setHidden(True)
        self.checkBox_CloudQA.setChecked(False)
        self.label_CloudQA_FileStatus.setVisible(False)
        self.widget_CloudQA_L457.setHidden(True)
        # search and check Cloud QA files
        if self.landsat_version in [4, 5, 7] and self.collection == 1:
            self.frame_CloudQA_L457.setVisible(True)
            self.cloud_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                              self.mtl_file['FILE_NAME_BAND_1'].replace(
                                                  self.mtl_file['FILE_NAME_BAND_1'].split("_")[-1],
                                                  "sr_cloud_qa.tif"))
            # check Cloud QA files
            if os.path.isfile(self.cloud_qa_file):
                self.checkBox_CloudQA.setEnabled(True)
            else:
                self.checkBox_CloudQA.setEnabled(False)
                self.label_CloudQA_FileStatus.setVisible(True)

        #### Aerosol L89 adjusts
        self.widget_Aerosol_L89.setHidden(True)
        self.frame_Aerosol_L89.setHidden(True)
        self.checkBox_Aerosol.setChecked(False)
        self.label_Aerosol_FileStatus.setVisible(False)
        if self.landsat_version in [8, 9] and self.collection == 1:
            self.frame_Aerosol_L89.setVisible(True)
            self.aerosol_file = os.path.join(os.path.dirname(self.mtl_path),
                                             self.mtl_file['FILE_NAME_BAND_1'].replace(
                                                 self.mtl_file['FILE_NAME_BAND_1'].split("_")[-1],
                                                 "sr_aerosol.tif"))
            # check Aerosol file
            if os.path.isfile(self.aerosol_file):
                self.checkBox_Aerosol.setEnabled(True)
            else:
                self.checkBox_Aerosol.setEnabled(False)
                self.label_Aerosol_FileStatus.setVisible(True)

        #### Pixel QA adjusts
        # hidden blocks and unchecked
        self.PixelQA_FileStatus.setVisible(False)
        self.checkBox_PixelQA.setChecked(False)
        self.widget_PixelQA.setHidden(True)
        self.groupBox_CirrusConfidence.setHidden(True)
        self.PixelQA_TerrainO_mask.setHidden(True)
        # search and check pixel QA file
        self.pixel_qa_file = ""
        if self.collection == 1:
            self.frame_PixelQA.setVisible(True)
            self.pixel_qa_file = os.path.join(os.path.dirname(self.mtl_path),
                                              self.mtl_file['FILE_NAME_BAND_1'].replace(
                                                  self.mtl_file['FILE_NAME_BAND_1'].split("_")[-1], "pixel_qa.tif"))
        # check pixel QA file exists
        if os.path.isfile(self.pixel_qa_file):
            self.checkBox_PixelQA.setEnabled(True)
            # only for landsat 8
            if self.landsat_version in [8, 9]:
                self.groupBox_CirrusConfidence.setVisible(True)
                self.PixelQA_TerrainO_mask.setVisible(True)
        else:
            if self.collection == 1:
                self.PixelQA_FileStatus.setVisible(True)
                self.checkBox_PixelQA.setEnabled(False)
            if self.collection == 2:
                self.frame_PixelQA.setHidden(True)

        #### QA Band C1 L457
        # hidden blocks and unchecked
        self.QABandC1L457_FileStatus.setVisible(False)
        self.checkBox_QABandC1L457.setChecked(False)
        self.widget_QABandC1L457.setHidden(True)
        self.qabandc1_file_l457 = ""
        # check QA Band C1 file exists
        if self.collection == 1 and self.processing_level == "L1" and self.landsat_version in [4, 5, 7]:
            self.qabandc1_file_l457 = os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_QUALITY'])
            if not os.path.isfile(self.qabandc1_file_l457):
                self.qabandc1_file_l457 = self.qabandc1_file_l457.replace("BQA.TIF", "bqa.tif")

            if os.path.isfile(self.qabandc1_file_l457):
                self.checkBox_QABandC1L457.setEnabled(True)
                self.frame_QA_Band_C1_L457.setVisible(True)
            else:
                self.frame_QA_Band_C1_L457.setVisible(True)
                self.QABandC1L457_FileStatus.setVisible(True)
                self.checkBox_QABandC1L457.setEnabled(False)
                self.checkBox_QABandC1L457.setChecked(False)
        else:
            self.frame_QA_Band_C1_L457.setVisible(False)

        #### QA Band C1 L89
        # hidden blocks and unchecked
        self.QABandC1L89_FileStatus.setVisible(False)
        self.checkBox_QABandC1L89.setChecked(False)
        self.widget_QABandC1L89.setHidden(True)
        self.qabandc1_file_l89 = ""
        # check QA Band C1 file exists
        if self.collection == 1 and self.processing_level == "L1" and self.landsat_version in [8, 9]:
            self.qabandc1_file_l89 = os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_QUALITY'])
            if not os.path.isfile(self.qabandc1_file_l89):
                self.qabandc1_file_l89 = self.qabandc1_file_l89.replace("BQA.TIF", "bqa.tif")

            if os.path.isfile(self.qabandc1_file_l89):
                self.checkBox_QABandC1L89.setEnabled(True)
                self.frame_QA_Band_C1_L89.setVisible(True)
            else:
                self.frame_QA_Band_C1_L89.setVisible(True)
                self.QABandC1L89_FileStatus.setVisible(True)
                self.checkBox_QABandC1L89.setEnabled(False)
                self.checkBox_QABandC1L89.setChecked(False)
        else:
            self.frame_QA_Band_C1_L89.setVisible(False)

        #### QA Band C2 adjusts
        # hidden blocks and unchecked
        self.QABandC2_FileStatus.setVisible(False)
        self.checkBox_QABandC2.setChecked(False)
        self.widget_QABandC2.setHidden(True)
        self.qabandc2_file = ""
        # check Band C2 file exists
        if self.collection == 1:
            self.frame_QA_Band_C2.setHidden(True)
        if self.collection == 2:
            self.frame_QA_Band_C2.setVisible(True)
            self.qabandc2_file = os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_QUALITY_L1_PIXEL'])
            if os.path.isfile(self.qabandc2_file):
                self.checkBox_QABandC2.setEnabled(True)
            else:
                self.QABandC2_FileStatus.setVisible(True)
                self.checkBox_QABandC2.setEnabled(False)

        #### Enable apply to raw stack if are available
        exists_raw_files = [os.path.isfile(get_prefer_name(os.path.join(os.path.dirname(self.mtl_path),
                                                                        self.mtl_file['FILE_NAME_BAND_' + str(N)])))
                            for N in self.reflectance_bands]

        if all(exists_raw_files):
            self.radioButton_ToRaw_Bands.setEnabled(True)
            self.radioButton_ToRaw_Bands.setChecked(True)
        else:
            self.radioButton_ToRaw_Bands.setEnabled(False)
            if self.collection == 2:
                self.horizontalSlider_BB.setMaximum(40000)
                self.horizontalSlider_BB.setValue(self.bb_threshold_L89)
                self.doubleSpinBox_BB.setMaximum(40000)
                self.doubleSpinBox_BB.setValue(self.bb_threshold_L89)

        #### Enable apply to SR reflectance stack if they are available
        exists_sr_files = \
            [os.path.isfile(f) for f in [os.path.join(os.path.dirname(self.mtl_path),
                self.mtl_file['FILE_NAME_BAND_' + str(N)].replace("_B", "_sr_band").replace(".TIF", ".tif"))
                for N in self.reflectance_bands]]

        if not all(exists_sr_files):
            # check if exist SR C2 files
            exists_sr_files = \
                [os.path.isfile(os.path.join(os.path.dirname(self.mtl_path), self.mtl_file['FILE_NAME_BAND_SR_' + str(N)]))
                 for N in self.reflectance_bands if 'FILE_NAME_BAND_SR_' + str(N) in self.mtl_file]

        if exists_sr_files and all(exists_sr_files):
            self.radioButton_ToSR_Bands.setEnabled(True)
            self.radioButton_ToSR_Bands.setChecked(True)

        #### Set the stack bands by default in stack to apply
        if self.landsat_version in [4, 5, 7]:
            reflectance_bands = [1, 2, 3, 4, 5, 7]
        if self.landsat_version in [8, 9]:
            reflectance_bands = [2, 3, 4, 5, 6, 7]
        self.lineEdit_StackBands.setText(','.join([str(x) for x in reflectance_bands]))

    def unload_MTL(self):
        """Disconnect, unload and remove temporal files of old MTL
        and old process
        """

        # MTL info
        self.status_LoadedMTL.setChecked(False)
        self.mtl_path = None
        # deactivate filters box
        self.groupBox_Filters.setEnabled(False)
        self.groupBox_GenerateMask.setEnabled(False)
        # deactivate save and apply box
        self.groupBox_SelectMask.setEnabled(False)
        self.groupBox_ApplyMask.setEnabled(False)
        self.radioButton_ToSR_Bands.setEnabled(False)
        self.radioButton_ToRaw_Bands.setChecked(True)
        self.widget_ApplyToFile.setHidden(True)

        # Load stack and clear all #########
        self.button_ClearAll.setEnabled(False)
        self.groupBox_LoadStacks.setEnabled(False)

    def restart_map_tool(self):
        # action pan and zoom
        self.canvas.setMapTool(self.pan_zoom_tool, clean=True)

    @pyqtSlot()
    def visible_aoi(self):
        # first clean all rubber bands
        [rubber_band.reset() for rubber_band in self.rubber_bands]
        [rubber_band.reset() for rubber_band in self.tmp_rubber_bands]
        self.rubber_bands = []
        self.tmp_rubber_bands = []

        if self.VisibleAOI.isChecked() and self.aoi_features is not None:
            for feat in self.aoi_features.getFeatures():
                color = QColor("red")
                color.setAlpha(70)
                rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
                rubber_band.setToGeometry(feat.geometry())
                rubber_band.setColor(color)
                rubber_band.setWidth(3)
                self.rubber_bands.append(rubber_band)
                tmp_rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
                tmp_rubber_band.setToGeometry(feat.geometry())
                tmp_rubber_band.setColor(color)
                tmp_rubber_band.setWidth(3)
                tmp_rubber_band.setLineStyle(Qt.DotLine)
                self.tmp_rubber_bands.append(tmp_rubber_band)

    @pyqtSlot()
    def undo_aoi(self):
        # delete feature
        features_ids = [f.id() for f in self.aoi_features.getFeatures()]
        with edit(self.aoi_features):
            self.aoi_features.deleteFeature(features_ids[-1])
        # delete rubber bands
        self.rubber_bands.pop().reset(QgsWkbTypes.PolygonGeometry)
        self.tmp_rubber_bands.pop().reset(QgsWkbTypes.PolygonGeometry)
        # update
        if len(list(self.aoi_features.getFeatures())) > 0:
            self.aoi_changes()
        else:  # empty
            self.delete_all_aoi()

    @pyqtSlot()
    def delete_all_aoi(self):
        # clear/reset all rubber bands
        for rubber_band in self.rubber_bands + self.tmp_rubber_bands:
            rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self.rubber_bands = []
        self.tmp_rubber_bands = []
        # remove all features in aoi
        if self.aoi_features is not None:
            self.aoi_features.dataProvider().truncate()
            self.aoi_features = None
        # disable undo delete buttons
        self.UndoAOI.setEnabled(False)
        self.DeleteAllAOI.setEnabled(False)
        self.VisibleAOI.setEnabled(False)

    @pyqtSlot()
    def aoi_changes(self, new_features=None):
        """Actions after added each polygon in the AOI"""
        # update AOI
        if new_features is not None:
            if self.aoi_features is None:
                self.aoi_features = QgsVectorLayer(
                    "MultiPolygon?crs=" + iface.mapCanvas().mapSettings().destinationCrs().toWkt(), "aoi", "memory")
            with edit(self.aoi_features):
                self.aoi_features.addFeatures(new_features)
        # enable undo and delete buttons
        self.UndoAOI.setEnabled(True)
        self.DeleteAllAOI.setEnabled(True)
        self.VisibleAOI.setEnabled(True)
        if not self.VisibleAOI.isChecked():
            self.VisibleAOI.setChecked(True)
            self.visible_aoi()


class PickerAOIPointTool(QgsMapTool):
    def __init__(self, dockwidget):
        QgsMapTool.__init__(self, dockwidget.canvas)
        self.dockwidget = dockwidget
        # set rubber band style
        color = QColor("red")
        color.setAlpha(70)
        # create the main polygon rubber band
        self.rubber_band = QgsRubberBand(dockwidget.canvas, QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setColor(color)
        self.rubber_band.setWidth(3)
        # create the mouse/tmp polygon rubber band, this is main rubber band + current mouse position
        self.tmp_rubber_band = QgsRubberBand(dockwidget.canvas, QgsWkbTypes.PolygonGeometry)
        self.tmp_rubber_band.setColor(color)
        self.tmp_rubber_band.setWidth(3)
        self.tmp_rubber_band.setLineStyle(Qt.DotLine)

    def finish_drawing(self):
        self.rubber_band = None
        self.tmp_rubber_band = None
        # restart point tool
        self.clean()
        self.dockwidget.canvas.unsetMapTool(self)
        self.dockwidget.restart_map_tool()

    def canvasMoveEvent(self, event):
        if self.tmp_rubber_band is None:
            return
        if self.tmp_rubber_band and self.tmp_rubber_band.numberOfVertices():
            x = event.pos().x()
            y = event.pos().y()
            point = self.dockwidget.canvas.getCoordinateTransform().toMapCoordinates(x, y)
            self.tmp_rubber_band.removeLastPoint()
            self.tmp_rubber_band.addPoint(point)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Backspace or event.key() == Qt.Key_Delete:
            self.rubber_band.removeLastPoint()
            self.tmp_rubber_band.removeLastPoint()
        if event.key() == Qt.Key_Escape:
            self.rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self.tmp_rubber_band.reset(QgsWkbTypes.PolygonGeometry)

    def canvasPressEvent(self, event):
        if self.rubber_band is None:
            self.finish_drawing()
            return
        # new point on polygon
        if event.button() == Qt.LeftButton:
            x = event.pos().x()
            y = event.pos().y()
            point = self.dockwidget.canvas.getCoordinateTransform().toMapCoordinates(x, y)
            self.rubber_band.addPoint(point)
            self.tmp_rubber_band.addPoint(point)
        # save polygon
        if event.button() == Qt.RightButton:
            if self.rubber_band and self.rubber_band.numberOfVertices():
                if self.rubber_band.numberOfVertices() < 3:
                    self.finish_drawing()
                    return
                self.tmp_rubber_band.removeLastPoint()
                new_feature = QgsFeature()
                new_feature.setGeometry(self.rubber_band.asGeometry())
                self.dockwidget.rubber_bands.append(self.rubber_band)
                self.dockwidget.tmp_rubber_bands.append(self.tmp_rubber_band)
                self.rubber_band = None
                self.tmp_rubber_band = None
                self.finish_drawing()
                # add the new feature and update the statistics
                self.dockwidget.aoi_changes([new_feature])

    def keyReleaseEvent(self, event):
        if event.key() in [Qt.Key_Up, Qt.Key_Down, Qt.Key_Right, Qt.Key_Left, Qt.Key_PageUp, Qt.Key_PageDown]:
            QTimer.singleShot(10, self.dockwidget.render_widget.parent_view.canvas_changed)
