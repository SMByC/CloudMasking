# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking using different process suck as fmask
                              -------------------
        begin                : 2015-12-17
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Xavier Corredor Llano, SMBYC
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
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, QObject, SIGNAL
from PyQt4.QtGui import QAction, QIcon, QMenu
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from cloud_masking_dialog import CloudMaskingDialog
import os.path


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

        # Create the dialog (after translation) and keep reference
        self.dlg = CloudMaskingDialog()

        # Declare instance attributes
        self.actions = []
        
        # menu
        self.menu = None
        # Check if the menu exists and get it
        for menu_item in self.iface.mainWindow().menuBar().children(): 
            if isinstance(menu_item, QMenu) and menu_item.title() == u"SMBYC":
                self.menu = child
        # If the menu does not exist, create it!
        if not self.menu:
            self.menu = QMenu(self.iface.mainWindow().menuBar())
            self.menu.setObjectName(u'Plugins for the project SMBYC')
            self.menu.setTitle(u"SMBYC")
            

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
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/CloudMasking/icon.png'
        self.action = QAction(QIcon(icon_path), self.tr(u'&Cloud masking'), self.iface.mainWindow())
        self.action.setObjectName(u'CloudMasking')
        self.action.setWhatsThis(self.tr(u'Cloud masking ...'))
        self.action.setStatusTip(self.tr(u'This is status tip'))
        QObject.connect(self.action, SIGNAL("triggered()"), self.run)
        self.menu.addAction(self.action)
        
        self.menuBar = self.iface.mainWindow().menuBar()
        self.menuBar.insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.menu)


    def unload(self):
        for menu_item in self.iface.mainWindow().menuBar().children(): 
            if isinstance(menu_item, QMenu) and menu_item.title() == u"SMBYC":
                menu_item.removeAction(self.action)
                # TODO: remove menu_item "SMBYC" if this is empty (actions)


    def run(self):
        """Run method that performs all the real work"""
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass
