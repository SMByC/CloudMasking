# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                              -------------------
        copyright            : (C) 2016-2018 by Xavier Corredor Llano, SMByC
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
import os.path
import shutil
import tempfile
import traceback
from datetime import datetime
from time import sleep
from osgeo import gdal

from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, pyqtSlot
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QApplication, QFileDialog, QListWidgetItem, QSizePolicy
from qgis.PyQt.QtGui import QIcon, QCursor
from qgis.PyQt.QtWidgets import QCheckBox, QGroupBox, QRadioButton
from qgis.core import QgsMessageLog, QgsProject, QgsRasterLayer, QgsMapLayer, QgsCoordinateTransform, \
    QgsMapLayerProxyModel, Qgis
# Initialize Qt resources from file resources.py
from . import resources

from CloudMasking.core import cloud_filters, color_stack
from CloudMasking.core.utils import apply_symbology, get_prefer_name, update_process_bar, get_extent, \
    load_and_select_filepath_in, get_file_path_of_layer
from CloudMasking.libs import gdal_calc, gdal_merge
from CloudMasking.gui.cloud_masking_dockwidget import CloudMaskingDockWidget
from CloudMasking.gui.about_dialog import AboutDialog


class CloudMasking(object):
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'CloudMasking_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        print("** INITIALIZING CloudMasking")

        self.menu_name_plugin = self.tr("&Cloud masking for Landsat products")
        self.pluginIsActive = False
        self.dockwidget = None

        # Obtaining the map canvas
        self.canvas = iface.mapCanvas()

        self.about_dialog = AboutDialog()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('CloudMasking', message)

    def initGui(self):
        ### Main dockwidget
        # Create action that will start plugin configuration
        icon_path = ':/plugins/CloudMasking/icons/cloud_masking.svg'
        self.dockable_action = QAction(QIcon(icon_path), self.tr('&Cloud Masking'), self.iface.mainWindow())
        # connect the action to the run method
        self.dockable_action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.dockable_action)
        self.iface.addPluginToMenu(self.menu_name_plugin, self.dockable_action)

        ### About dialog
        # Create action that will start plugin configuration
        icon_path = ':/plugins/CloudMasking/icons/about.svg'
        self.about_action = QAction(QIcon(icon_path), self.tr('About'), self.iface.mainWindow())
        # connect the action to the run method
        self.about_action.triggered.connect(self.about)
        # Add toolbar button and menu item
        self.iface.addPluginToMenu(self.menu_name_plugin, self.about_action)

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        print("** CLOSING CloudMasking")
        self.removes_temporary_files()

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        self.canvas.layersChanged.disconnect(self.updateLayersList_MultipleLayerMask)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        self.dockwidget.deleteLater()
        self.dockwidget = None

        self.pluginIsActive = False

        from qgis.utils import reloadPlugin
        reloadPlugin("CloudMasking")

    def about(self):
        self.about_dialog.show()

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        print("** UNLOAD CloudMasking")
        self.removes_temporary_files()

        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(self.menu_name_plugin, self.dockable_action)
        self.iface.removePluginMenu(self.menu_name_plugin, self.about_action)
        self.iface.removeToolBarIcon(self.dockable_action)

    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING CloudMasking"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = CloudMaskingDockWidget()

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.tabWidget.setCurrentWidget(self.dockwidget.tab_OL)  # focus first tab
            self.dockwidget.show()

        # initial masking and color stack instance
        self.masking_result = None
        self.color_stack_scene = None
        # set properties to QgsMapLayerComboBox for mask list
        self.dockwidget.select_SingleLayerMask.setCurrentIndex(-1)
        self.dockwidget.select_SingleLayerMask.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.dockwidget.OnlyMaskLayers_SingleMask.clicked.connect(self.updateLayersList_SingleLayerMask)
        QgsProject.instance().layersAdded.connect(self.updateLayersList_SingleLayerMask)
        self.updateLayersList_SingleLayerMask()

        # tabwidget
        self.update_tab_select_mask(0)
        self.dockwidget.select_layer_mask.currentChanged.connect(self.update_tab_select_mask)
        # set properties to list for select multiple layer mask
        self.updateLayersList_MultipleLayerMask()
        self.dockwidget.OnlyMaskLayers_MultipleMask.clicked.connect(self.updateLayersList_MultipleLayerMask)
        self.canvas.layersChanged.connect(self.updateLayersList_MultipleLayerMask)
        self.dockwidget.QPBtn_SelectAll.clicked.connect(self.selectAll_MultipleLayerMask)
        self.dockwidget.QPBtn_DeselectAll.clicked.connect(self.deselectAll_MultipleLayerMask)

        # set properties to QgsMapLayerComboBox for shape area
        self.dockwidget.QCBox_MaskInShapeArea.setCurrentIndex(-1)
        self.dockwidget.QCBox_MaskInShapeArea.setFilters(QgsMapLayerProxyModel.VectorLayer)
        # call to browse the shape area for make mask inside it
        self.dockwidget.button_BrowseShapeArea.clicked.connect(lambda: self.fileDialog_browse(
            self.dockwidget.QCBox_MaskInShapeArea,
            dialog_title=self.tr("Select the shape file"),
            dialog_types=self.tr("Shape files (*.shp);;All files (*.*)"),
            layer_type="vector", suggested_path=os.path.dirname(self.dockwidget.mtl_path)))

        # call to load MTL file
        self.dockwidget.button_LoadMTL.clicked.connect(self.buttom_load_mtl)
        # call to clear all
        self.dockwidget.button_ClearAll.clicked.connect(self.buttom_clear_all)
        # call to load natural color stack
        self.dockwidget.button_NaturalColorStack.clicked.connect(lambda: self.set_color_stack("natural_color"))
        # call to load false color stack
        self.dockwidget.button_FalseColorStack.clicked.connect(lambda: self.set_color_stack("false_color"))
        # call to load infrareds stack
        self.dockwidget.button_InfraredsStack.clicked.connect(lambda: self.set_color_stack("infrareds"))
        # call to process load stack
        self.dockwidget.button_processLoadStack.clicked.connect(self.load_stack)
        # call to process mask
        self.dockwidget.button_processMask.clicked.connect(self.process_mask)
        # save mask
        self.dockwidget.button_SaveMask.clicked.connect(self.fileDialog_saveMask)
        # select result
        self.dockwidget.button_SelectResult.clicked.connect(self.fileDialog_SaveResult)
        # select result
        self.dockwidget.button_SelectPFile.clicked.connect(self.fileDialog_SelectPFile)
        # button for Apply Mask
        self.dockwidget.button_processApplyMask.clicked.connect(self.apply_mask)

    def error_handler(func_name):
        def decorate(f):
            def applicator(self, *args, **kwargs):
                try:
                    f(self, *args, **kwargs)
                except Exception as e:
                    # restore mouse
                    QApplication.restoreOverrideCursor()
                    QApplication.processEvents()

                    # message in status bar
                    msg_error = "An error has occurred in '{0}': {1}. " \
                                "See more in Qgis log message.".format(func_name, e)
                    self.iface.messageBar().pushMessage("Error", msg_error,
                                                        level=Qgis.Critical, duration=0)

                    # message in log
                    msg_error = "\n################## ERROR IN CLOUD MASKING PLUGIN:"
                    msg_error += "\nAn error has occurred in '{0}': {1}\n".format(func_name, e)
                    msg_error += traceback.format_exc()
                    msg_error += "\nPlease report the error in:\n" \
                                 "\thttps://bitbucket.org/smbyc/qgisplugin-cloudmasking/issues"
                    msg_error += "\n################## END REPORT"
                    QgsMessageLog.logMessage(msg_error)

            return applicator
        return decorate

    def update_tab_select_mask(self, current_tab_idx):
        """Adjust the size tab based on the content"""
        for tab_idx in range(self.dockwidget.select_layer_mask.count()):
            if tab_idx != current_tab_idx:
                self.dockwidget.select_layer_mask.widget(tab_idx).setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.dockwidget.select_layer_mask.widget(current_tab_idx).setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.dockwidget.select_layer_mask.widget(current_tab_idx).resize(
            self.dockwidget.select_layer_mask.widget(current_tab_idx).minimumSizeHint())
        self.dockwidget.select_layer_mask.widget(current_tab_idx).adjustSize()

    def updateLayersList_SingleLayerMask(self):
        # filtering
        excepted = []
        if self.dockwidget.OnlyMaskLayers_SingleMask.isChecked():
            for layer in [l for l in self.iface.legendInterface().layers() if l.type() == QgsMapLayer.RasterLayer]:
                if not layer.name().startswith("Cloud Mask"):
                    excepted.append(layer)
        # set excepted layers
        self.dockwidget.select_SingleLayerMask.setExceptedLayerList(excepted)

    def updateLayersList_MultipleLayerMask(self):
        # delete items
        self.dockwidget.select_MultipleLayerMask.clear()
        # filtering
        for layer in [l for l in self.iface.legendInterface().layers() if l.type() == QgsMapLayer.RasterLayer]:
            if self.dockwidget.OnlyMaskLayers_MultipleMask.isChecked() and not layer.name().startswith("Cloud Mask"):
                continue
            item = QListWidgetItem(layer.name())
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setCheckState(Qt.Unchecked)
            self.dockwidget.select_MultipleLayerMask.addItem(item)

    def selectAll_MultipleLayerMask(self):
        for x in range(self.dockwidget.select_MultipleLayerMask.count()):
            self.dockwidget.select_MultipleLayerMask.item(x).setCheckState(Qt.Checked)

    def deselectAll_MultipleLayerMask(self):
        for x in range(self.dockwidget.select_MultipleLayerMask.count()):
            self.dockwidget.select_MultipleLayerMask.item(x).setCheckState(Qt.Unchecked)

    def getLayerByName(self, layer_name):
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == layer_name:
                return layer

    def set_color_stack(self, color_type):
        # select the bands for color stack for Landsat 4, 5 y 7
        if self.dockwidget.landsat_version in [4, 5, 7]:
            if color_type == "natural_color":
                bands = [3, 2, 1]
            if color_type == "false_color":
                bands = [4, 3, 2]
            if color_type == "infrareds":
                bands = [4, 5, 7]
        # select the bands for color stack for Landsat 8
        if self.dockwidget.landsat_version == 8:
            if color_type == "natural_color":
                bands = [4, 3, 2]
            if color_type == "false_color":
                bands = [5, 4, 3]
            if color_type == "infrareds":
                bands = [5, 6, 7]

        self.dockwidget.SelectBand_R.setCurrentIndex(self.dockwidget.reflectance_bands.index(bands[0]))
        self.dockwidget.SelectBand_G.setCurrentIndex(self.dockwidget.reflectance_bands.index(bands[1]))
        self.dockwidget.SelectBand_B.setCurrentIndex(self.dockwidget.reflectance_bands.index(bands[2]))

    @error_handler('load stack')
    def load_stack(self, *args):
        update_process_bar(self.dockwidget.bar_progressLoadStack, 40,
                           self.dockwidget.status_processLoadStack, self.tr("Loading stack..."))
        bands = []
        bands.append(int(self.dockwidget.SelectBand_R.currentText()))
        bands.append(int(self.dockwidget.SelectBand_G.currentText()))
        bands.append(int(self.dockwidget.SelectBand_B.currentText()))

        self.color_stack_scene = color_stack.ColorStack(self.dockwidget.mtl_path,
                                                        self.dockwidget.mtl_file,
                                                        bands,
                                                        self.dockwidget.tmp_dir)
        self.color_stack_scene.do_color_stack()
        self.color_stack_scene.load_color_stack()
        update_process_bar(self.dockwidget.bar_progressLoadStack, 100,
                           self.dockwidget.status_processLoadStack, self.tr("DONE"))

    @pyqtSlot()
    def fileDialog_browse(self, combo_box, dialog_title, dialog_types, layer_type, suggested_path=""):
        file_path, _, _ = QFileDialog.getOpenFileName(self.dockwidget, dialog_title, suggested_path, dialog_types)
        if file_path != '' and os.path.isfile(file_path):
            # load to qgis and update combobox list
            load_and_select_filepath_in(combo_box, file_path, layer_type)

    @error_handler('process mask')
    def process_mask(self, *args):
        """Make the process
        """
        # initialize the symbology
        enable_symbology = [False, False, False, False, False, False, False, False]

        # check if any filters has been enabled before process
        if (not self.dockwidget.checkBox_FMask.isChecked() and
            not self.dockwidget.checkBox_BlueBand.isChecked() and
            not self.dockwidget.checkBox_CloudQA.isChecked() and
            not self.dockwidget.checkBox_Aerosol.isChecked() and
            not self.dockwidget.checkBox_PixelQA.isChecked()):
            self.dockwidget.status_processMask.setText(
                self.tr("Error: no filters enabled for apply"))
            return

        # create the masking result instance if not exist
        if (not isinstance(self.masking_result, cloud_filters.CloudMaskingResult) or
            not self.masking_result.landsat_scene == self.dockwidget.mtl_file['LANDSAT_SCENE_ID']):
            # create a new instance of cloud masking result
            self.masking_result = cloud_filters.CloudMaskingResult(self.dockwidget.mtl_path,
                                                                   self.dockwidget.mtl_file,
                                                                   self.dockwidget.tmp_dir)
            self.masking_result.process_status = self.dockwidget.status_processMask
            self.masking_result.process_bar = self.dockwidget.bar_processMask

        # re-init the result masking files
        self.masking_result.cloud_masking_files = []

        ########################################
        ## Set the extent selector
        # set for rectangular region
        if self.dockwidget.checkBox_ExtentSelector.isChecked() and self.dockwidget.isExtentAreaSelected:
            self.masking_result.clipping_extent = True
            self.masking_result.extent_x1 = float(self.dockwidget.widget_ExtentSelector.x1CoordEdit.text())
            self.masking_result.extent_y1 = float(self.dockwidget.widget_ExtentSelector.y1CoordEdit.text())
            self.masking_result.extent_x2 = float(self.dockwidget.widget_ExtentSelector.x2CoordEdit.text())
            self.masking_result.extent_y2 = float(self.dockwidget.widget_ExtentSelector.y2CoordEdit.text())
        else:
            self.masking_result.clipping_extent = False
        # set for the shape selector
        if self.dockwidget.checkBox_ShapeSelector.isChecked():
            self.masking_result.clipping_with_shape = True
            self.masking_result.shape_layer = self.dockwidget.QCBox_MaskInShapeArea.currentLayer()
            # get and save trim extent of shapefile for clip
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            shape_crs = self.masking_result.shape_layer.crs()
            shape_canvas_transform = QgsCoordinateTransform(shape_crs, canvas_crs)
            self.masking_result.shape_extent = shape_canvas_transform.transform(self.masking_result.shape_layer.extent())

            self.masking_result.shape_path = get_file_path_of_layer(self.dockwidget.QCBox_MaskInShapeArea.currentLayer())
            if self.dockwidget.shapeSelector_CutWithShape.isChecked():
                self.masking_result.crop_to_cutline = True
            else:
                self.masking_result.crop_to_cutline = False
        else:
            self.masking_result.clipping_with_shape = False

        # check extent area selector and shape file
        if self.dockwidget.checkBox_ExtentSelector.isChecked() and not self.dockwidget.isExtentAreaSelected:
            self.dockwidget.status_processMask.setText(
                self.tr("Error: not area selected in canvas"))
            return

        if self.dockwidget.checkBox_ShapeSelector.isChecked():
            if not self.masking_result.shape_path:
                self.dockwidget.status_processMask.setText(
                    self.tr("Error: not shape file defined"))
                return
            if not os.path.isfile(self.masking_result.shape_path):
                self.dockwidget.status_processMask.setText(
                    self.tr("Error: shape file not exists"))
                return

        ########################################
        # FMask filter

        if self.dockwidget.checkBox_FMask.isChecked():
            # get enabled Fmask filters from UI and set symbology
            enable_symbology[0:4] = [False, False, False, False]
            filters_enabled = {"Fmask Cloud": False, "Fmask Shadow": False, "Fmask Snow": False, "Fmask Water": False, }
            # Cloud
            if self.dockwidget.checkBox_FMask_Cloud.isChecked():
                enable_symbology[0] = True
                filters_enabled["Fmask Cloud"] = True
            # Shadow
            if self.dockwidget.checkBox_FMask_Shadow.isChecked():
                enable_symbology[1] = True
                filters_enabled["Fmask Shadow"] = True
            # Snow
            if self.dockwidget.checkBox_FMask_Snow.isChecked():
                enable_symbology[2] = True
                filters_enabled["Fmask Snow"] = True
            # Water
            if self.dockwidget.checkBox_FMask_Water.isChecked():
                enable_symbology[3] = True
                filters_enabled["Fmask Water"] = True

            # fmask filter
            self.masking_result.do_fmask(
                filters_enabled=filters_enabled,
                cloud_prob_thresh=float(self.dockwidget.doubleSpinBox_CPT.value()),
                cirrus_prob_ratio=float(self.dockwidget.doubleSpinBox_CPR.value()),
                cloud_buffer_size=float(self.dockwidget.doubleSpinBox_CB.value()),
                shadow_buffer_size=float(self.dockwidget.doubleSpinBox_SB.value()),
                nir_fill_thresh=float(self.dockwidget.doubleSpinBox_NFT.value()),
                swir2_thresh=float(self.dockwidget.doubleSpinBox_S2T.value()),
                whiteness_thresh=float(self.dockwidget.doubleSpinBox_WT.value()),
                swir2_water_test=float(self.dockwidget.doubleSpinBox_S2WT.value()),
                nir_snow_thresh=float(self.dockwidget.doubleSpinBox_NST.value()),
                green_snow_thresh=float(self.dockwidget.doubleSpinBox_GST.value()),
            )

        ########################################
        # Blue Band filter

        if self.dockwidget.checkBox_BlueBand.isChecked():
            self.masking_result.do_blue_band(int(self.dockwidget.doubleSpinBox_BB.value()))
            enable_symbology[4] = True

        ########################################
        # Cloud QA L457 filter

        if self.dockwidget.checkBox_CloudQA.isChecked():
            if self.dockwidget.landsat_version in [4, 5, 7]:
                checked_items = {}

                # one bit items selected
                cloud_qa_items_1b = ["Dark Dense Vegetation (bit 0)", "Cloud (bit 1)", "Cloud Shadow (bit 2)",
                                     "Adjacent to cloud (bit 3)", "Snow (bit 4)", "Water (bit 5)"]
                for checkbox in self.dockwidget.widget_CloudQA_L457_bits.findChildren(QCheckBox):
                    if checkbox.text() in cloud_qa_items_1b:
                        checked_items[checkbox.text()] = checkbox.isChecked()

                # set and check the specific decimal values
                try:
                    cloud_qa_svalues = self.dockwidget.CloudQA_L457_svalues.text()
                    if cloud_qa_svalues:
                        cloud_qa_svalues = [int(sv) for sv in cloud_qa_svalues.split(",")]
                    else:
                        cloud_qa_svalues = []
                except:
                    self.dockwidget.status_processMask.setText(
                        self.tr("Error: setting the specific values in Cloud QA"))
                    return

                # check is not selected any Cloud QA filter
                if not any(checked_items.values()) and not cloud_qa_svalues:
                    self.dockwidget.status_processMask.setText(
                        self.tr("Error: no filters selected in Cloud QA"))
                    return

                self.masking_result.do_cloud_qa_l457(self.dockwidget.cloud_qa_file, checked_items, cloud_qa_svalues)

            enable_symbology[5] = True

        ########################################
        # Aerosol L8 filter

        if self.dockwidget.checkBox_Aerosol.isChecked():
            if self.dockwidget.landsat_version in [8]:
                checked_items = {}

                # one bit items selected
                aerosol_items_1b = ["Aerosol Retrieval - Valid (bit 1)", "Aerosol Retrieval - Interpolated (bit 2)",
                                    "Water Pixel (bit 3)"]
                for checkbox in self.dockwidget.widget_Aerosol_bits.findChildren(QCheckBox):
                    if checkbox.text() in aerosol_items_1b:
                        checked_items[checkbox.text()] = checkbox.isChecked()

                # two bits items selected
                aerosol_items_2b = ["Aerosol Content (bits 6-7)"]
                levels = ["Climatology content", "Low content", "Average content", "High content"]

                for groupbox in self.dockwidget.widget_Aerosol_bits.findChildren(QGroupBox):
                    if groupbox.title() in aerosol_items_2b and groupbox.isChecked():
                        levels_selected = []
                        for radiobutton in groupbox.findChildren(QRadioButton):
                            if radiobutton.text() in levels and radiobutton.isChecked():
                                levels_selected.append(radiobutton.text())
                        if levels_selected:
                            checked_items[groupbox.title()] = levels_selected

                # set and check the specific decimal values
                try:
                    aerosol_svalues = self.dockwidget.Aerosol_L8_svalues.text()
                    if aerosol_svalues:
                        aerosol_svalues = [int(sv) for sv in aerosol_svalues.split(",")]
                    else:
                        aerosol_svalues = []
                except:
                    self.dockwidget.status_processMask.setText(
                        self.tr("Error: setting the specific values in Aerosol"))
                    return

                # check is not selected any Aerosol filter
                if not any(checked_items.values()) and not aerosol_svalues:
                    self.dockwidget.status_processMask.setText(
                        self.tr("Error: no filters selected in Aerosol"))
                    return

                self.masking_result.do_aerosol_l8(self.dockwidget.aerosol_file, checked_items, aerosol_svalues)

            enable_symbology[6] = True

        ########################################
        # Pixel QA filter

        if self.dockwidget.checkBox_PixelQA.isChecked():
            checked_items = {}

            # one bit items selected
            if self.dockwidget.landsat_version in [4, 5, 7]:
                pixel_qa_items_1b = ["Fill-nodata (bit 0)","Water (bit 2)", "Cloud Shadow (bit 3)",
                                     "Snow (bit 4)", "Cloud (bit 5)"]
            if self.dockwidget.landsat_version in [8]:
                pixel_qa_items_1b = ["Fill-nodata (bit 0)", "Water (bit 2)", "Cloud Shadow (bit 3)",
                                     "Snow (bit 4)", "Cloud (bit 5)", "Terrain Occlusion (bit 10)"]
            for checkbox in self.dockwidget.widget_PixelQA_bits.findChildren(QCheckBox):
                if checkbox.text() in pixel_qa_items_1b:
                    checked_items[checkbox.text()] = checkbox.isChecked()

            # two bits items selected
            if self.dockwidget.landsat_version in [4, 5, 7]:
                pixel_qa_items_2b = ["Cloud Confidence (bits 6-7)"]
            if self.dockwidget.landsat_version in [8]:
                pixel_qa_items_2b = ["Cloud Confidence (bits 6-7)", "Cirrus Confidence (bits 8-9)"]
            levels = ["0% None", "0-33% Low", "34-66% Medium", "67-100% High"]

            for groupbox in self.dockwidget.widget_PixelQA_bits.findChildren(QGroupBox):
                if groupbox.title() in pixel_qa_items_2b and groupbox.isChecked():
                    levels_selected = []
                    for radiobutton in groupbox.findChildren(QRadioButton):
                        if radiobutton.text() in levels and radiobutton.isChecked():
                            levels_selected.append(radiobutton.text())
                    if levels_selected:
                        checked_items[groupbox.title()] = levels_selected

            # set and check the specific decimal values
            try:
                pixel_qa_svalues = self.dockwidget.PixelQA_svalues.text()
                if pixel_qa_svalues:
                    pixel_qa_svalues = [int(sv) for sv in pixel_qa_svalues.split(",")]
                else:
                    pixel_qa_svalues = []
            except:
                self.dockwidget.status_processMask.setText(
                    self.tr("Error: setting the specific values in Pixel QA"))
                return

            # check is not selected any Pixel QA filter
            if not any(checked_items.values()) and not pixel_qa_svalues:
                self.dockwidget.status_processMask.setText(
                    self.tr("Error: no filters selected in Pixel QA"))
                return

            self.masking_result.do_pixel_qa(self.dockwidget.pixel_qa_file, checked_items, pixel_qa_svalues)

            enable_symbology[7] = True

        ########################################
        # Blended cloud masking files

        # only one filter is activated
        if len(self.masking_result.cloud_masking_files) == 1:
            self.final_cloud_mask_file = self.masking_result.cloud_masking_files[0]

        # two filters are activated
        if len(self.masking_result.cloud_masking_files) == 2:
            self.final_cloud_mask_file = os.path.join(self.dockwidget.tmp_dir,
                                                      "cloud_blended_{}.tif".format(datetime.now().strftime('%H%M%S')))
            gdal_calc.Calc(calc="A*(A>1)+B*(A==1)", outfile=self.final_cloud_mask_file,
                           A=self.masking_result.cloud_masking_files[0], B=self.masking_result.cloud_masking_files[1])

        # three filters are activated
        if len(self.masking_result.cloud_masking_files) == 3:
            self.final_cloud_mask_file = os.path.join(self.dockwidget.tmp_dir,
                                                      "cloud_blended_{}.tif".format(datetime.now().strftime('%H%M%S')))
            gdal_calc.Calc(calc="A*(A>1)+B*logical_and(A==1,B>1)+C*logical_and(A==1,B==1)",
                           outfile=self.final_cloud_mask_file,
                           A=self.masking_result.cloud_masking_files[0], B=self.masking_result.cloud_masking_files[1],
                           C=self.masking_result.cloud_masking_files[2])

        # four filters are activated
        if len(self.masking_result.cloud_masking_files) == 4:
            self.final_cloud_mask_file = os.path.join(self.dockwidget.tmp_dir,
                                                      "cloud_blended_{}.tif".format(datetime.now().strftime('%H%M%S')))
            gdal_calc.Calc(calc="A*(A>1)+B*logical_and(A==1,B>1)+C*logical_and(logical_and(A==1,B==1),C>1)"
                           "+D*logical_and(logical_and(A==1,B==1),C==1)", outfile=self.final_cloud_mask_file,
                           A=self.masking_result.cloud_masking_files[0], B=self.masking_result.cloud_masking_files[1],
                           C=self.masking_result.cloud_masking_files[2], D=self.masking_result.cloud_masking_files[3])

        ########################################
        # mask the nodata value as 255 value
        self.masking_result.do_nodata_mask(self.final_cloud_mask_file)

        ########################################
        # Keep the original size if made the mask in selected area
        if self.dockwidget.checkBox_ExtentSelector.isChecked() and \
           self.dockwidget.widget_ExtentSelector.extentSelector_KeepOriginalSize.isChecked():
            img_path = get_prefer_name(os.path.join(os.path.dirname(self.dockwidget.mtl_path),
                                                    self.dockwidget.mtl_file['FILE_NAME_BAND_1']))
            extent = get_extent(img_path)
            # expand
            gdal.Translate(self.final_cloud_mask_file.replace(".tif", "1.tif"), self.final_cloud_mask_file,
                           projWin=extent, noData=1)
            os.remove(self.final_cloud_mask_file)
            # unset the nodata, leave the 1 (valid fields)
            gdal.Translate(self.final_cloud_mask_file, self.final_cloud_mask_file.replace(".tif", "1.tif"), noData="none")
            # only left the final file
            os.remove(self.final_cloud_mask_file.replace(".tif", "1.tif"))
        else:
            # unset the nodata
            gdal.Translate(self.final_cloud_mask_file.replace(".tif", "1.tif"), self.final_cloud_mask_file, noData="none")
            os.remove(self.final_cloud_mask_file)
            os.rename(self.final_cloud_mask_file.replace(".tif", "1.tif"), self.final_cloud_mask_file)

        ########################################
        # keep the data outside the shape area as valid data (=1), important for apply several mask
        if self.dockwidget.checkBox_ShapeSelector.isChecked() and not self.dockwidget.shapeSelector_CutWithShape.isChecked():
            self.masking_result.clip(self.final_cloud_mask_file, self.final_cloud_mask_file.replace(".tif", "1.tif"),
                                     nodata=1, process_bar=False)
            os.remove(self.final_cloud_mask_file)
            # expand to original extent
            img_path = get_prefer_name(os.path.join(os.path.dirname(self.dockwidget.mtl_path),
                                                    self.dockwidget.mtl_file['FILE_NAME_BAND_1']))
            extent = get_extent(img_path)
            gdal.Translate(self.final_cloud_mask_file.replace(".tif", "2.tif"), self.final_cloud_mask_file.replace(".tif", "1.tif"),
                           projWin=extent, noData=1)
            os.remove(self.final_cloud_mask_file.replace(".tif", "1.tif"))
            # unset the nodata
            gdal.Translate(self.final_cloud_mask_file, self.final_cloud_mask_file.replace(".tif", "2.tif"), noData="none")
            os.remove(self.final_cloud_mask_file.replace(".tif", "2.tif"))
        ########################################
        # Delete data outside the shapefile or selected area, as 255 value
        if (self.dockwidget.checkBox_ShapeSelector.isChecked() and self.dockwidget.shapeSelector_CutWithShape.isChecked()) or \
           (self.dockwidget.checkBox_ExtentSelector.isChecked() and not self.dockwidget.widget_ExtentSelector.extentSelector_KeepOriginalSize.isChecked()):
            # expand to original extent
            img_path = get_prefer_name(os.path.join(os.path.dirname(self.dockwidget.mtl_path),
                                                    self.dockwidget.mtl_file['FILE_NAME_BAND_1']))
            extent = get_extent(img_path)
            gdal.Translate(self.final_cloud_mask_file.replace(".tif", "1.tif"), self.final_cloud_mask_file,
                           projWin=extent, noData=255)
            os.remove(self.final_cloud_mask_file)
            # unset the nodata
            gdal.Translate(self.final_cloud_mask_file, self.final_cloud_mask_file.replace(".tif", "1.tif"), noData="none")
            # only left the final file
            os.remove(self.final_cloud_mask_file.replace(".tif", "1.tif"))

        ########################################
        # Post process mask

        # delete unused output
        # from fmask
        if self.dockwidget.checkBox_FMask.isChecked():
            os.remove(self.masking_result.angles_file)
            os.remove(self.masking_result.saturationmask_file)
            os.remove(self.masking_result.toa_file)
            if os.path.isfile(self.masking_result.reflective_stack_clip_file):
                os.remove(self.masking_result.reflective_stack_clip_file)
            if os.path.isfile(self.masking_result.thermal_stack_clip_file):
                os.remove(self.masking_result.thermal_stack_clip_file)
        # from blue band
        if self.dockwidget.checkBox_BlueBand.isChecked():
            if os.path.isfile(self.masking_result.blue_band_clip_file):
                os.remove(self.masking_result.blue_band_clip_file)
        # from cloud QA
        if self.dockwidget.checkBox_CloudQA.isChecked():
            if os.path.isfile(self.masking_result.cloud_qa_clip_file):
                os.remove(self.masking_result.cloud_qa_clip_file)
        # from aerosol
        if self.dockwidget.checkBox_Aerosol.isChecked():
            if os.path.isfile(self.masking_result.aerosol_clip_file):
                os.remove(self.masking_result.aerosol_clip_file)
        # from Pixel QA
        if self.dockwidget.checkBox_PixelQA.isChecked():
            if os.path.isfile(self.masking_result.pixel_qa_clip_file):
                os.remove(self.masking_result.pixel_qa_clip_file)

        # from original blended files
        for cloud_masking_file in self.masking_result.cloud_masking_files:
            if cloud_masking_file != self.final_cloud_mask_file:
                os.remove(cloud_masking_file)

        # hide the extent selector
        if self.dockwidget.checkBox_ExtentSelector.isChecked():
            self.dockwidget.checkBox_ExtentSelector.setChecked(False)

        # Add to QGIS the reflectance stack file and cloud file
        if self.masking_result.clipping_extent:
            masking_result_name = self.tr("Cloud Mask in area ({})".format(datetime.now().strftime('%H:%M:%S')))
        elif self.dockwidget.checkBox_ShapeSelector.isChecked():
            masking_result_name = self.tr("Cloud Mask in shape ({})".format(datetime.now().strftime('%H:%M:%S')))
        else:
            masking_result_name = self.tr("Cloud Mask ({})".format(datetime.now().strftime('%H:%M:%S')))
        self.cloud_mask_rlayer = QgsRasterLayer(self.final_cloud_mask_file, masking_result_name)
        QgsProject.instance().addMapLayer(self.cloud_mask_rlayer)

        # Set symbology (thematic color and name) for new raster layer
        symbology = {
            'Fmask Cloud': (255, 0, 255, 255),
            'Fmask Shadow': (255, 255, 0, 255),
            'Fmask Snow': (85, 255, 255, 255),
            'Fmask Water': (0, 0, 200, 255),
            'Blue Band': (120, 212, 245, 255),
            'Cloud QA': (255, 170, 0, 255),
            'Aerosol': (255, 170, 0, 255),
            'Pixel QA': (20, 180, 140, 255),
        }
        # apply
        apply_symbology(self.cloud_mask_rlayer,
                        symbology,
                        enable_symbology,
                        transparent=[])
        # Refresh layer symbology
        self.iface.legendInterface().refreshLayerSymbology(self.cloud_mask_rlayer)

    def fileDialog_saveMask(self):
        """Open QFileDialog for save mask file
        """
        suggested_filename_mask = self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + "_Mask.tif"
        mask_outpath, _, _ = QFileDialog.getSaveFileName(self.dockwidget, self.tr("Save mask file"),
                                                   os.path.join(os.path.dirname(self.dockwidget.mtl_path),
                                                                suggested_filename_mask),
                                                   self.tr("Tif files (*.tif);;All files (*.*)"))
        mask_inpath = str(self.getLayerByName(self.dockwidget.select_SingleLayerMask.currentText()).dataProvider().dataSourceUri())

        if mask_outpath != '' and mask_inpath != '':
            # set nodata to valid data (1) and copy to destination
            # warning: this cause that external load and apply not masked correctly if before not do unset the nodata
            gdal.Translate(mask_outpath, mask_inpath, noData=1)

    def fileDialog_SelectPFile(self):
        """Open QFileDialog for select particular file to apply mask
        """
        p_file_path, _, _ = QFileDialog.getOpenFileName(self.dockwidget, self.tr("Select particular file to apply mask"),
                                                  os.path.dirname(self.dockwidget.mtl_path),
                                                  self.tr("Tif files (*.tif);;All files (*.*)"))

        if p_file_path != '':
            self.dockwidget.lineEdit_ParticularFile.setText(p_file_path)

    def fileDialog_SaveResult(self):
        """Open QFileDialog for save result after apply mask
        """
        if self.dockwidget.radioButton_ToSR_Bands.isChecked():
            suggested_filename_result = self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + "SR_Enmask.tif"
        else:
            suggested_filename_result = self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + "_Enmask.tif"

        result_path, _, _ = QFileDialog.getSaveFileName(self.dockwidget, self.tr("Save result"),
                                                  os.path.join(os.path.dirname(self.dockwidget.mtl_path),
                                                               suggested_filename_result),
                                                  self.tr("Tif files (*.tif);;All files (*.*)"))

        if result_path != '':
            self.dockwidget.lineEdit_ResultPath.setText(result_path)

    @error_handler('apply mask')
    def apply_mask(self, *args):
        # init progress bar
        update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                           self.tr("Preparing the mask files..."))

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))  # mouse wait

        # get result path
        result_path = self.dockwidget.lineEdit_ResultPath.text()
        if result_path is None or result_path == '':
            update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                               self.tr("Error: Not selected file for save"))
            return

        def prepare_mask(layer):
            # get mask layer
            try:
                mask_path = str(layer.dataProvider().dataSourceUri())
            except:
                update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                                   self.tr("Not valid mask '{}'".format(layer.name())))
                return None, None

            # check mask layer
            if not os.path.isfile(mask_path):
                update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                                   self.tr("Mask file not exists '{}'".format(layer.name())))
                return None, None

            # fix nodata to null, unset the nodata else the result lost the data in the valid value to mask (1)
            mask_fd, tmp_mask_file = tempfile.mkstemp(prefix='mask_', suffix='.tif', dir=self.dockwidget.tmp_dir)
            gdal.Translate(tmp_mask_file, mask_path, noData="none")
            mask_path = tmp_mask_file

            return mask_fd, mask_path

        ## Single mask layer
        if self.dockwidget.select_layer_mask.currentIndex() == 0:
            final_mask_fd, final_mask_path = prepare_mask(self.getLayerByName(self.dockwidget.select_SingleLayerMask.currentText()))
            if not final_mask_path:
                return

        ## Multiple mask layer
        if self.dockwidget.select_layer_mask.currentIndex() == 1:
            items = [self.dockwidget.select_MultipleLayerMask.item(i) for i in range(self.dockwidget.select_MultipleLayerMask.count())]
            layers_selected = [self.getLayerByName(item.text()) for item in items if item.checkState() == Qt.Checked]
            if not layers_selected:
                update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                                   self.tr("Error: Not mask layers selected to apply"))
                return
            # prepare
            masks = [prepare_mask(layer) for layer in layers_selected]
            # merge all mask
            final_mask_fd, final_mask_path = tempfile.mkstemp(prefix='merge_masks_', suffix='.tif', dir=self.dockwidget.tmp_dir)
            gdal_merge.main(["", "-of", "GTiff", "-o", final_mask_path, "-n", "1"] + [mask[1] for mask in masks])

        # get and set stack bands for make layer stack for apply mask
        if self.dockwidget.radioButton_ToRaw_Bands.isChecked() or self.dockwidget.radioButton_ToSR_Bands.isChecked():
            update_process_bar(self.dockwidget.bar_processApplyMask, 20, self.dockwidget.status_processApplyMask,
                               self.tr("Making the stack bands..."))

            reflectance_bands = self.dockwidget.lineEdit_StackBands.text()
            try:
                reflectance_bands = [int(x) for x in reflectance_bands.split(',')]
            except:
                update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                                   self.tr("Error: Invalid stack bands"))
                return

        ## Select the stack or file to apply mask
        # reflectance stack, normal bands (_bands and _B)
        if self.dockwidget.radioButton_ToRaw_Bands.isChecked():
            stack_bands = [os.path.join(os.path.dirname(self.dockwidget.mtl_path), self.dockwidget.mtl_file['FILE_NAME_BAND_' + str(N)])
                           for N in reflectance_bands]
            stack_bands = [get_prefer_name(file_path) for file_path in stack_bands]
        # SR reflectance stack if are available (_sr_bands)
        if self.dockwidget.radioButton_ToSR_Bands.isChecked():
            stack_bands = \
                [os.path.join(os.path.dirname(self.dockwidget.mtl_path),
                    self.dockwidget.mtl_file['FILE_NAME_BAND_' + str(N)].replace("_B", "_sr_band").replace(".TIF", ".tif"))
                    for N in reflectance_bands]
        # select particular file for apply mask
        if self.dockwidget.radioButton_ToParticularFile.isChecked():
            self.reflective_stack_file = self.dockwidget.lineEdit_ParticularFile.text()
            # check if exists
            if not os.path.isfile(self.reflective_stack_file):
                update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                                   self.tr("Error: The particular file not exists"))
                return
            # only tif
            if not self.reflective_stack_file.endswith((".tif", ".TIF")):
                update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                                   self.tr("Error: The particular file should be tif"))
                return

        # make stack to apply mask in tmp file
        if self.dockwidget.radioButton_ToRaw_Bands.isChecked() or self.dockwidget.radioButton_ToSR_Bands.isChecked():
            self.reflective_stack_file = os.path.join(self.dockwidget.tmp_dir, "Reflective_stack_" +
                                                      self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + ".tif")

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-o",
                             self.reflective_stack_file] + stack_bands)

        update_process_bar(self.dockwidget.bar_processApplyMask, 50, self.dockwidget.status_processApplyMask,
                           self.tr("Applying mask..."))

        # check images size if is different, this mean that the mask is a selected area
        # and "keep the original image size" is not selected. Then resize the reflective
        # stack to mask size
        inprogress_file = self.reflective_stack_file\
            .replace(".tif", "_inprogress.tif").replace(".TIF", "_inprogress.tif")
        if get_extent(self.reflective_stack_file) != get_extent(final_mask_path):
            extent_mask = get_extent(final_mask_path)
            gdal.Translate(inprogress_file, self.reflective_stack_file, projWin=extent_mask)
            os.remove(self.reflective_stack_file)
            os.rename(inprogress_file, self.reflective_stack_file)

        # apply mask to stack
        if self.dockwidget.select_layer_mask.currentIndex() == 0:
            gdal_calc.Calc(calc="A*(B==1)", A=self.reflective_stack_file, B=final_mask_path,
                           outfile=inprogress_file, allBands='A', overwrite=True)
        if self.dockwidget.select_layer_mask.currentIndex() == 1:
            gdal_calc.Calc(calc="A*(B==0)", A=self.reflective_stack_file, B=final_mask_path,
                           outfile=inprogress_file, allBands='A', overwrite=True)

        # unset the nodata
        gdal.Translate(result_path, inprogress_file, noData="none")

        # clean
        if not self.dockwidget.radioButton_ToParticularFile.isChecked():
            os.remove(self.reflective_stack_file)
        os.remove(inprogress_file)
        # delete tmp mask file
        if self.dockwidget.select_layer_mask.currentIndex() == 0:
            os.close(final_mask_fd)
            os.remove(final_mask_path)
        if self.dockwidget.select_layer_mask.currentIndex() == 1:
            os.close(final_mask_fd)
            os.remove(final_mask_path)
            for mask_fd, mask_path in masks:
                os.close(mask_fd)
                os.remove(mask_path)
        # load into canvas when finished
        if self.dockwidget.checkBox_LoadResult.isChecked():
            # Add to QGIS the result saved
            result_qgis_name = self.dockwidget.mtl_file['LANDSAT_SCENE_ID']
            result_rlayer = QgsRasterLayer(result_path, os.path.basename(result_path))
            QgsProject.instance().addMapLayer(result_rlayer)

        update_process_bar(self.dockwidget.bar_processApplyMask, 100, self.dockwidget.status_processApplyMask,
                           self.tr("DONE"))

    def buttom_load_mtl(self):
        # check if is the same MTL
        if self.dockwidget.mtl_path == self.dockwidget.lineEdit_PathMTL.text():
            return

        # first prompt to user if delete the current
        # process and load a new MTL file
        if self.dockwidget.status_LoadedMTL.isChecked():
            quit_msg = "Are you sure you want to clean all the old MTL and load the new MTL file?"
            reply = QMessageBox.question(self.dockwidget, 'Loading the new MTL...',
                                         quit_msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        # run clean temp files
        self.removes_temporary_files()

        # run load MTL
        self.dockwidget.load_MTL()

    def buttom_clear_all(self):
        # first prompt
        quit_msg = "Are you sure you want to clean all: delete unsaved masks, clean tmp files, unload processed images?"
        reply = QMessageBox.question(self.dockwidget, 'Cleaning all for the current MTL file...',
                                           quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        # run clean temp files
        self.removes_temporary_files()

        self.onClosePlugin()
        from qgis.utils import plugins
        plugins["CloudMasking"].run()

    def removes_temporary_files(self):

        # message
        if isinstance(self.dockwidget, CloudMaskingDockWidget):
            self.dockwidget.tabWidget.setCurrentWidget(self.dockwidget.tab_OL)  # focus first tab
            self.dockwidget.status_LoadedMTL.setText(self.tr("Cleaning temporal files ..."))
            self.dockwidget.status_LoadedMTL.repaint()
            QApplication.processEvents()
            sleep(0.3)

        # unload MTL file and extent selector
        try:
            self.dockwidget.unload_MTL()
            self.dockwidget.widget_ExtentSelector.stop()
        except: pass

        # unload all layers instances from Qgis saved in tmp dir
        layers_loaded = QgsProject.instance().mapLayers().values()
        try:
            d = self.dockwidget.tmp_dir
            files_in_tmp_dir = [os.path.join(d, f) for f in os.listdir(d)
                                if os.path.isfile(os.path.join(d, f))]
        except: files_in_tmp_dir = []

        layersToRemove = []
        for file_tmp in files_in_tmp_dir:
            for layer_loaded in layers_loaded:
                if file_tmp == layer_loaded.dataProvider().dataSourceUri():
                    layersToRemove.append(layer_loaded)
        QgsProject.instance().removeMapLayers(layersToRemove)

        # unload shape area if exists
        for layer_name, layer_loaded in QgsProject.instance().mapLayers().items():
            if layer_name.startswith("Shape_area__"):
                QgsProject.instance().removeMapLayer(layer_loaded)

        # clear self.dockwidget.tmp_dir
        try:
            shutil.rmtree(self.dockwidget.tmp_dir, ignore_errors=True)
            self.dockwidget.tmp_dir.close()
            self.dockwidget.tmp_dir = None
        except: pass

