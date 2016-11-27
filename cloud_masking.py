# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
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
import os.path
import shutil
from datetime import datetime
from time import sleep
from shutil import copyfile
import gdal

from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QObject, SIGNAL
from PyQt4.QtGui import QAction, QIcon, QMenu, QMessageBox, QApplication, QCursor, QFileDialog
from PyQt4.QtGui import QCheckBox, QGroupBox, QRadioButton
from qgis.core import QgsMapLayer, QgsMessageLog, QgsMapLayerRegistry, QgsRasterLayer
# Initialize Qt resources from file resources.py
import resources

from CloudMasking.core import cloud_filters, color_stack
from CloudMasking.core.utils import apply_symbology, get_prefer_name, update_process_bar
from CloudMasking.gui.cloud_masking_dockwidget import CloudMaskingDockWidget
from CloudMasking.libs import gdal_calc, gdal_merge, gdal_clip


class CloudMasking:
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
        self.canvas = self.iface.mapCanvas()

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

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Cloud Masking')
        #self.toolbar = self.iface.addToolBar(u'CloudMasking')
        #self.toolbar.setObjectName(u'CloudMasking')

        self.pluginIsActive = False
        self.dockwidget = None

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

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=False,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            ## set the smbyc menu
            self.smbyc_menu = None
            # Check if the menu exists and get it
            for menu_item in self.iface.mainWindow().menuBar().children():
                if isinstance(menu_item, QMenu) and menu_item.title() == u"SMBYC":
                    self.smbyc_menu = menu_item
            # If the menu does not exist, create it!
            if not self.smbyc_menu:
                self.smbyc_menu = QMenu(self.iface.mainWindow().menuBar())
                self.smbyc_menu.setObjectName(u'Plugins for the project SMBYC')
                self.smbyc_menu.setTitle(u"SMBYC")

            ## set the item plugin in smbyc menu
            self.action = QAction(QIcon(icon_path), self.menu, self.iface.mainWindow())
            self.action.setObjectName(u'CloudMasking')
            self.action.setWhatsThis(self.tr(u'Cloud masking ...'))
            self.action.setStatusTip(self.tr(u'This is status tip'))
            QObject.connect(self.action, SIGNAL("triggered()"), self.run)
            self.smbyc_menu.addAction(self.action)

            self.menuBar = self.iface.mainWindow().menuBar()
            self.menuBar.insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.smbyc_menu)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/CloudMasking/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Cloud Masking'),
            callback=self.run,
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        print "** CLOSING CloudMasking"
        self.clear_all()

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        print "** UNLOAD CloudMasking"
        self.clear_all()

        for action in self.actions:
            for menu_item in self.iface.mainWindow().menuBar().children():
                if isinstance(menu_item, QMenu) and menu_item.title() == u"SMBYC":
                    menu_item.removeAction(self.action)
                    # TODO: remove menu_item "SMBYC" if this is empty (actions)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        #del self.toolbar

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

        # set initial input layers list
        self.updateLayersList_MaskLayer()
        # initial masking and color stack instance
        self.masking_result = None
        self.color_stack_scene = None
        # handle connect when the list of layers changed
        QObject.connect(self.canvas, SIGNAL("layersChanged()"), self.updateLayersList_MaskLayer)
        self.dockwidget.checkBox_ActivatedLayers.clicked.connect(self.updateLayersList_MaskLayer)
        self.dockwidget.checkBox_MaskLayers.clicked.connect(self.updateLayersList_MaskLayer)
        # call to load MTL file
        QObject.connect(self.dockwidget.button_LoadMTL, SIGNAL("clicked()"), self.buttom_load_mtl)
        # call to clear all
        QObject.connect(self.dockwidget.button_ClearAll, SIGNAL("clicked()"), self.buttom_clear_all)
        # call to load natural color stack
        QObject.connect(self.dockwidget.button_NaturalColorStack, SIGNAL("clicked()"),
                        lambda: self.set_color_stack("natural_color"))
        # call to load false color stack
        QObject.connect(self.dockwidget.button_FalseColorStack, SIGNAL("clicked()"),
                        lambda: self.set_color_stack("false_color"))
        # call to load infrareds stack
        QObject.connect(self.dockwidget.button_InfraredsStack, SIGNAL("clicked()"),
                        lambda: self.set_color_stack("infrareds"))
        # call to process load stack
        QObject.connect(self.dockwidget.button_processLoadStack, SIGNAL("clicked()"), self.load_stack)
        # call to process mask
        QObject.connect(self.dockwidget.button_processMask, SIGNAL("clicked()"), self.process_mask)
        # save mask
        self.dockwidget.button_SaveMask.clicked.connect(self.fileDialog_saveMask)
        # select result
        self.dockwidget.button_SelectResult.clicked.connect(self.fileDialog_SaveResult)
        # select result
        self.dockwidget.button_SelectPFile.clicked.connect(self.fileDialog_SelectPFile)
        # button for Apply Mask
        self.dockwidget.button_processApplyMask.clicked.connect(self.apply_mask)

    def updateLayersList_MaskLayer(self):
        if self.dockwidget is not None:
            self.dockwidget.select_MaskLayer.clear()

            if self.dockwidget.checkBox_ActivatedLayers.isChecked():
                layers = self.canvas.layers()
            else:
                layers = QgsMapLayerRegistry.instance().mapLayers().values()

            for layer in layers:
                if self.dockwidget.checkBox_MaskLayers.isChecked():
                    if layer.name().startswith("Cloud Mask"):
                        self.dockwidget.select_MaskLayer.addItem(layer.name())
                else:
                    self.dockwidget.select_MaskLayer.addItem(layer.name())


    def getLayerByName(self, layer_name):
        for layer in self.canvas.layers():
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

    def load_stack(self):
        update_process_bar(self.dockwidget.bar_progressLoadStack, 40,
                           self.dockwidget.status_processLoadStack, self.tr(u"Loading stack..."))
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
                           self.dockwidget.status_processLoadStack, self.tr(u"DONE"))

    def process_mask(self):
        """Make the process
        """
        # initialize the symbology
        enable_symbology = [False, False, False, False, False, False, False, False]

        # check if any filters has been enabled before process
        if (not self.dockwidget.checkBox_FMask.isChecked() and
                not self.dockwidget.checkBox_BlueBand.isChecked() and
                not self.dockwidget.checkBox_CloudQA.isChecked() and
                not self.dockwidget.checkBox_QABand.isChecked()):
            self.dockwidget.status_processMask.setText(
                self.tr(u"Error: no filters enabled for apply")
            )
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
        # Set the extent selector
        if self.dockwidget.isExtentAreaSelected:
            self.masking_result.clipping_extent = True
            self.masking_result.extent_x1 = float(self.dockwidget.widget_ExtentSelector.x1CoordEdit.text())
            self.masking_result.extent_y1 = float(self.dockwidget.widget_ExtentSelector.y1CoordEdit.text())
            self.masking_result.extent_x2 = float(self.dockwidget.widget_ExtentSelector.x2CoordEdit.text())
            self.masking_result.extent_y2 = float(self.dockwidget.widget_ExtentSelector.y2CoordEdit.text())
        else:
            self.masking_result.clipping_extent = False

        ########################################
        # FMask filter

        if self.dockwidget.checkBox_FMask.isChecked():
            # get enabled Fmask filters from UI and set symbology
            enable_symbology[0:5] = [True, False, False, False, False]
            filters_enabled = {"Cloud": False, "Shadow": False, "Snow": False, "Water": False, }
            # Cloud
            if self.dockwidget.checkBox_FMask_Cloud.isChecked():
                enable_symbology[1] = True
                filters_enabled["Cloud"] = True
            # Shadow
            if self.dockwidget.checkBox_FMask_Shadow.isChecked():
                enable_symbology[2] = True
                filters_enabled["Shadow"] = True
            # Snow
            if self.dockwidget.checkBox_FMask_Snow.isChecked():
                enable_symbology[3] = True
                filters_enabled["Snow"] = True
            # Water
            if self.dockwidget.checkBox_FMask_Water.isChecked():
                enable_symbology[4] = True
                filters_enabled["Water"] = True

            # fmask filter
            self.masking_result.do_fmask(
                filters_enabled=filters_enabled,
                cirrus_prob_ratio=float(self.dockwidget.doubleSpinBox_CPR.value()),
                cloud_buffer_size=float(self.dockwidget.doubleSpinBox_CB.value()),
                shadow_buffer_size=float(self.dockwidget.doubleSpinBox_SB.value()),
                nir_fill_thresh=float(self.dockwidget.doubleSpinBox_NFT.value()),
                swir2_thresh=float(self.dockwidget.doubleSpinBox_S2T.value()),
                whiteness_thresh=float(self.dockwidget.doubleSpinBox_WT.value()),
                swir2_water_test=float(self.dockwidget.doubleSpinBox_S2WT.value()),
            )

        ########################################
        # Blue Band filter

        if self.dockwidget.checkBox_BlueBand.isChecked():
            self.masking_result.do_blue_band(int(self.dockwidget.doubleSpinBox_BB.value()))
            enable_symbology[0] = True
            enable_symbology[5] = True

        ########################################
        # Cloud QA filter

        if self.dockwidget.checkBox_CloudQA.isChecked():
            if self.dockwidget.landsat_version in [4, 5, 7]:
                cloud_qa_file, shadow_qa_file, ddv_qa_file = [None]*3
                if self.dockwidget.checkBox_CloudQA_mask.isChecked():
                    cloud_qa_file = self.dockwidget.cloud_qa_file
                if self.dockwidget.checkBox_ShadowQA_mask.isChecked():
                    shadow_qa_file = self.dockwidget.shadow_qa_file
                if self.dockwidget.checkBox_DDVQA_mask.isChecked():
                    ddv_qa_file = self.dockwidget.ddv_qa_file

                self.masking_result.do_cloud_qa_l457(cloud_qa_file, shadow_qa_file, ddv_qa_file)

            if self.dockwidget.landsat_version in [8]:
                checked_items = {}

                # one bit items selected
                cloud_qa_items_1b = ["Cirrus cloud (bit 0)", "Cloud (bit 1)",
                                     "Adjacent to cloud (bit 2)", "Cloud shadow (bit 3)"]
                for checkbox in self.dockwidget.widget_CloudQA_bits.findChildren(QCheckBox):
                    if checkbox.text() in cloud_qa_items_1b:
                        checked_items[checkbox.text()] = checkbox.isChecked()

                # two bits items selected
                cloud_qa_items_2b = ["Aerosol (bits 4-5)"]
                levels = ["Climatology content", "Low content", "Average content", "High content"]

                for groupbox in self.dockwidget.widget_CloudQA_bits.findChildren(QGroupBox):
                    if groupbox.title() in cloud_qa_items_2b and groupbox.isChecked():
                        levels_selected = []
                        for radiobutton in groupbox.findChildren(QRadioButton):
                            if radiobutton.text() in levels and radiobutton.isChecked():
                                levels_selected.append(radiobutton.text())
                        if levels_selected:
                            checked_items[groupbox.title()] = levels_selected

                # set and check the specific decimal values
                try:
                    cloud_qa_svalues = self.dockwidget.lineEdit_CloudQA_svalues.text()
                    if cloud_qa_svalues:
                        cloud_qa_svalues = [int(sv) for sv in cloud_qa_svalues.split(",")]
                    else:
                        cloud_qa_svalues = []
                except:
                    self.dockwidget.status_processMask.setText(
                        self.tr(u"Error: setting the specific values in Cloud QA"))
                    return

                # check is only selected one aerosol
                if len(checked_items) == 0 and not cloud_qa_svalues:
                    self.dockwidget.status_processMask.setText(
                        self.tr(u"Error: no filters selected in Cloud QA"))
                    return

                self.masking_result.do_cloud_qa_l8(self.dockwidget.cloud_qa_file, checked_items, cloud_qa_svalues)

            enable_symbology[0] = True
            enable_symbology[6] = True

        ########################################
        # QA Band filter

        if self.dockwidget.checkBox_QABand.isChecked():
            checked_items = {}

            # one bit items selected
            qa_band_items_1b = ["Dropped Frame (bit 1)", "Terrain Occlusion (bit 2)"]
            for checkbox in self.dockwidget.widget_QABand_bits.findChildren(QCheckBox):
                if checkbox.text() in qa_band_items_1b:
                    checked_items[checkbox.text()] = checkbox.isChecked()

            # two bits items selected
            qa_band_items_2b = ["Water (bits 4-5)", "Snow/ice (bits 10-11)", "Cirrus (bits 12-13)", "Cloud (bits 14-15)"]
            levels = ["Not Determined", "0-33% Confidence", "34-66% Confidence", "67-100% Confidence"]

            for groupbox in self.dockwidget.widget_QABand_bits.findChildren(QGroupBox):
                if groupbox.title() in qa_band_items_2b and groupbox.isChecked():
                    levels_selected = []
                    for radiobutton in groupbox.findChildren(QRadioButton):
                        if radiobutton.text() in levels and radiobutton.isChecked():
                            levels_selected.append(radiobutton.text())
                    if levels_selected:
                        checked_items[groupbox.title()] = levels_selected

            # set and check the specific decimal values
            try:
                qa_band_svalues = self.dockwidget.lineEdit_QABand_svalues.text()
                if qa_band_svalues:
                    qa_band_svalues = [int(sv) for sv in qa_band_svalues.split(",")]
                else:
                    qa_band_svalues = []
            except:
                self.dockwidget.status_processMask.setText(
                    self.tr(u"Error: setting the specific values in QA Band"))
                return

            self.masking_result.do_qa_band(self.dockwidget.qa_band_file, checked_items, qa_band_svalues)

            enable_symbology[0] = True
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
        # Keep the original size if made the
        # mask in selected area

        if self.dockwidget.checkBox_ExtentSelector.isChecked() and \
            self.dockwidget.widget_ExtentSelector.checkBox_KeepOriginalSize.isChecked():
            data = gdal.Open(get_prefer_name(os.path.join(os.path.dirname(self.dockwidget.mtl_path),
                                                          self.dockwidget.mtl_file['FILE_NAME_BAND_1'])), gdal.GA_ReadOnly)
            geoTransform = data.GetGeoTransform()
            minx = geoTransform[0]
            maxy = geoTransform[3]
            maxx = minx + geoTransform[1] * data.RasterXSize
            miny = maxy + geoTransform[5] * data.RasterYSize

            # expand
            gdal.Translate(self.final_cloud_mask_file.replace(".tif", "1.tif"), self.final_cloud_mask_file,
                           projWin=[minx, maxy, maxx, miny], noData=1)
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
        # Post process mask

        # delete unused output
        # from fmask
        if self.dockwidget.checkBox_FMask.isChecked():
            os.remove(self.masking_result.angles_file)
            os.remove(self.masking_result.saturationmask_file)
            os.remove(self.masking_result.toa_file)
            if self.masking_result.clipping_extent:
                os.remove(self.masking_result.reflective_stack_clip_file)
                os.remove(self.masking_result.thermal_stack_clip_file)
        # from blue band
        if self.dockwidget.checkBox_BlueBand.isChecked():
            if self.masking_result.clipping_extent:
                os.remove(self.masking_result.blue_band_clip_file)
        # from cloud QA
        if self.dockwidget.checkBox_CloudQA.isChecked():
            if self.masking_result.clipping_extent:
                os.remove(self.masking_result.cloud_qa_clip_file)
        # from original blended files
        for cloud_masking_file in self.masking_result.cloud_masking_files:
            if cloud_masking_file != self.final_cloud_mask_file:
                os.remove(cloud_masking_file)

        # Add to QGIS the reflectance stack file and cloud file
        if self.masking_result.clipping_extent:
            masking_result_name = self.tr(u"Cloud Mask in area ({})".format(datetime.now().strftime('%H:%M:%S')))
        else:
            masking_result_name = self.tr(u"Cloud Mask ({})".format(datetime.now().strftime('%H:%M:%S')))
        self.cloud_mask_rlayer = QgsRasterLayer(self.final_cloud_mask_file, masking_result_name)
        QgsMapLayerRegistry.instance().addMapLayer(self.cloud_mask_rlayer)

        # Set symbology (thematic color and name) for new raster layer
        symbology = {
            'Land': (0, 0, 0, 0),
            'Cloud': (255, 0, 255, 255),
            'Shadow': (255, 255, 0, 255),
            'Snow': (85, 255, 255, 255),
            'Water': (0, 0, 200, 255),
            'Blue band': (120, 212, 245, 255),
            'Cloud QA': (255, 170, 0, 255),
            'QA Band': (20, 180, 140, 255),
        }
        # apply
        apply_symbology(self.cloud_mask_rlayer,
                        symbology,
                        enable_symbology,
                        transparent=[255, 0])
        # Refresh layer symbology
        self.iface.legendInterface().refreshLayerSymbology(self.cloud_mask_rlayer)

    def fileDialog_saveMask(self):
        """Open QFileDialog for save mask file
        """
        suggested_filename_mask = self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + "_Mask.tif"
        mask_outpath = str(QFileDialog.getSaveFileName(self.dockwidget, self.tr(u"Save mask file"),
                                os.path.join(os.path.dirname(self.dockwidget.mtl_path), suggested_filename_mask),
                                self.tr(u"Tif files (*.tif);;All files (*.*)")))
        mask_inpath = unicode(self.getLayerByName(self.dockwidget.select_MaskLayer.currentText()).dataProvider().dataSourceUri())

        if mask_outpath != '' and mask_inpath != '':
            copyfile(mask_inpath, mask_outpath)

    def fileDialog_SelectPFile(self):
        """Open QFileDialog for select particular file to apply mask
        """
        p_file_path = str(QFileDialog.getOpenFileName(self.dockwidget, self.tr(u"Select particular file to apply mask"),
                                os.path.dirname(self.dockwidget.mtl_path),
                                self.tr(u"Tif files (*.tif);;All files (*.*)")))

        if p_file_path != '':
            self.dockwidget.lineEdit_ParticularFile.setText(p_file_path)

    def fileDialog_SaveResult(self):
        """Open QFileDialog for save result after apply mask
        """
        if self.dockwidget.radioButton_ToSR_RefStack.isChecked():
            suggested_filename_result = self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + "SR_Enmask.tif"
        else:
            suggested_filename_result = self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + "_Enmask.tif"

        result_path = str(QFileDialog.getSaveFileName(self.dockwidget, self.tr(u"Save result"),
                                os.path.join(os.path.dirname(self.dockwidget.mtl_path), suggested_filename_result),
                                self.tr(u"Tif files (*.tif);;All files (*.*)")))

        if result_path != '':
            self.dockwidget.lineEdit_ResultPath.setText(result_path)

    def apply_mask(self):
        # init progress bar
        update_process_bar(self.dockwidget.bar_processApplyMask, 0)

        # get mask layer
        try:
            mask_path = \
                unicode(self.getLayerByName(self.dockwidget.select_MaskLayer.currentText()).dataProvider().dataSourceUri())
        except:
            update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                               self.tr(u"Error: Mask for apply not valid"))
            return

        # check mask layer
        if not os.path.isfile(mask_path):
            update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                               self.tr(u"Error: Mask file not exists"))
            return

        # get result path
        result_path = self.dockwidget.lineEdit_ResultPath.text()
        if result_path is None or result_path == '':
            update_process_bar(self.dockwidget.bar_processApplyMask, 0, self.dockwidget.status_processApplyMask,
                               self.tr(u"Error: Not selected file for save"))
            return

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))  # mouse wait

        if not self.dockwidget.radioButton_ToParticularFile.isChecked():
            update_process_bar(self.dockwidget.bar_processApplyMask, 20, self.dockwidget.status_processApplyMask,
                               self.tr(u"Making the reflectance stack..."))

        # making layer stack
        if self.dockwidget.landsat_version in [4, 5, 7]:
            reflectance_bands = [1, 2, 3, 4, 5, 7]
        if self.dockwidget.landsat_version in [8]:
            reflectance_bands = [2, 3, 4, 5, 6, 7]

        ## Select the stack or file to apply mask
        # reflectance stack, normal bands (_bands and _B)
        if self.dockwidget.radioButton_ToRefStack.isChecked():
            stack_bands = [os.path.join(os.path.dirname(self.dockwidget.mtl_path), self.dockwidget.mtl_file['FILE_NAME_BAND_' + str(N)])
                           for N in reflectance_bands]
            stack_bands = [get_prefer_name(file_path) for file_path in stack_bands]
        # SR reflectance stack if are available (_sr_bands)
        if self.dockwidget.radioButton_ToSR_RefStack.isChecked():
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
                                   self.tr(u"Error: The particular file not exists"))
                return

        # make stack to apply mask in tmp file
        if self.dockwidget.radioButton_ToRefStack.isChecked() or self.dockwidget.radioButton_ToSR_RefStack.isChecked():
            self.reflective_stack_file = os.path.join(self.dockwidget.tmp_dir, "Reflective_stack_" +
                                                      self.dockwidget.mtl_file['LANDSAT_SCENE_ID'] + ".tif")

            gdal_merge.main(["", "-separate", "-of", "GTiff", "-o",
                             self.reflective_stack_file] + stack_bands)

        update_process_bar(self.dockwidget.bar_processApplyMask, 50, self.dockwidget.status_processApplyMask,
                           self.tr(u"Applying mask..."))

        # apply mask to stack
        gdal_calc.Calc(calc="A*(B==1)", A=self.reflective_stack_file, B=mask_path,
                       outfile=self.reflective_stack_file, allBands='A', overwrite=True)

        # unset the nodata
        gdal.Translate(result_path, self.reflective_stack_file, noData="none")

        # clean
        os.remove(self.reflective_stack_file)

        # load into canvas when finished
        if self.dockwidget.checkBox_LoadResult.isChecked():
            # Add to QGIS the result saved
            if self.dockwidget.radioButton_ToParticularFile.isChecked():
                result_qgis_name = self.dockwidget.mtl_file['LANDSAT_SCENE_ID']  #TODO
            else:
                result_qgis_name = self.dockwidget.mtl_file['LANDSAT_SCENE_ID']
            result_rlayer = QgsRasterLayer(result_path, "Result masked: " + result_qgis_name)
            QgsMapLayerRegistry.instance().addMapLayer(result_rlayer)

        update_process_bar(self.dockwidget.bar_processApplyMask, 100, self.dockwidget.status_processApplyMask,
                           self.tr(u"DONE"))

    def buttom_load_mtl(self):
        # check if is the same MTL
        if self.dockwidget.mtl_path == str(self.dockwidget.lineEdit_PathMTL.text()):
            return
        # first prompt to user if delete the current
        # process and load a new MTL file
        if self.dockwidget.status_LoadedMTL.isChecked():
            quit_msg = "Are you sure you want to clean all the old MTL and load the new MTL file?"
            reply = QMessageBox.question(self.dockwidget, 'Loading the new MTL...',
                                         quit_msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        # run clean all
        self.clear_all()
        # run load MTL
        self.dockwidget.load_MTL()

    def buttom_clear_all(self):
        # first prompt
        quit_msg = "Are you sure you want to clean all: delete unsaved masks, clean tmp files, unload processed images?"
        reply = QMessageBox.question(self.dockwidget, 'Cleaning all for the current MTL file...',
                                           quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        # run clean all
        self.clear_all()
        # clean MTL path
        self.dockwidget.lineEdit_PathMTL.setText('')

    def clear_all(self):

        # message
        if isinstance(self.dockwidget, CloudMaskingDockWidget):
            self.dockwidget.tabWidget.setCurrentWidget(self.dockwidget.tab_OL)  # focus first tab
            self.dockwidget.status_LoadedMTL.setText(self.tr(u"Cleaning temporal files ..."))
            self.dockwidget.status_LoadedMTL.repaint()
            QApplication.processEvents()
            sleep(0.3)

        # unload MTL file and extent selector
        try:
            self.dockwidget.unload_MTL()
            self.dockwidget.widget_ExtentSelector.stop()
        except: pass

        # unload all layers instances from Qgis saved in tmp dir
        layers_loaded = QgsMapLayerRegistry.instance().mapLayers().values()
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
        QgsMapLayerRegistry.instance().removeMapLayers(layersToRemove)

        # clear self.dockwidget.tmp_dir
        try:
            shutil.rmtree(self.dockwidget.tmp_dir, ignore_errors=True)
            self.dockwidget.tmp_dir = None
        except: pass

        # clear load bands select stack
        try:
            self.dockwidget.SelectBand_R.clear()
            self.dockwidget.SelectBand_G.clear()
            self.dockwidget.SelectBand_B.clear()
        except: pass

        # restore initial message
        if isinstance(self.dockwidget, CloudMaskingDockWidget):
            self.dockwidget.status_LoadedMTL.setText(self.tr(u"No MTL file loaded yet."))

