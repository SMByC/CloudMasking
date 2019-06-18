# CloudMasking

CloudMasking is a Qgis plugin for make the masking of clouds, cloud shadow, cirrus, aerosols, ice/snow and water for Landsat (4, 5, 7 and 8) products using different process and filters such as Fmask, Blue Band, Cloud QA, Aerosol and Pixel QA.

## Motivation

There are several ways for make cloud masking automatically, such as apply the default fmask band or cloud filter using a fixed pixel values in the QA bands. But these "by default" bands and values are not always good, and their efficiency varies in different regions and depends to a great extent on the type of terrain, vegetation or environmental conditions. The purpose of the plugin is to make cloud masking very personalized and configurable to perform the best possible masking by combining and using of various bands and filters.

## Documentation

Home page documentation: [https://smbyc.bitbucket.io/qgisplugins/cloudmasking](https://smbyc.bitbucket.io/qgisplugins/cloudmasking)

## Installation

- The plugin can be installed using the QGIS Plugin Manager
- Go into Qgis to `Plugins` menu and `Manage and install plugins`
- In `All` section search for `Cloud Masking` click and press Install plugin
- The plugin will be available in the `Plugins` menu and `Plugins toolbar`

(see more about [installation and upgrade](https://smbyc.bitbucket.io/qgisplugins/cloudmasking/installation))

## Source code

The official version control system repository of the plugin:
[https://bitbucket.org/smbyc/qgisplugin-cloudmasking](https://bitbucket.org/smbyc/qgisplugin-cloudmasking)

The home plugin in plugins.qgis.org: [https://plugins.qgis.org/plugins/CloudMasking/](https://plugins.qgis.org/plugins/CloudMasking/)

## Issue Tracker

Issues, ideas and enhancements: [https://bitbucket.org/smbyc/qgisplugin-cloudmasking/issues](https://bitbucket.org/smbyc/qgisplugin-cloudmasking/issues)

## Get involved

The CloudMasking plugin is open source and you can help in different ways:

* help with developing and/or improve the docs cloning the repository and doing the push request ([howto](https://confluence.atlassian.com/bitbucket/fork-a-teammate-s-repository-774243391.html)).
* or just test it, report issues, ideas and enhancements in the issue tracker.

***

Copyright (C) Xavier Corredor Llano <xcorredorl@ideam.gov.co>  
Sistema de Monitoreo de Bosques y Carbono (SMByC) and FAO  
General Public License - GPLv3
