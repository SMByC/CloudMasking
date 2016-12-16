# How to use

(under construction)

### Active the plugin

When activate the plugin, it is load as a dockwidget plugin locate in the right position in Qgis by default:

![](img/how_to_use_01.png)

### Order to use the plugin

The plugin is divided and ordered by 3 sections; `(1) Open and Load` this is for open the MTL file and load the stack, `(2) Filters and Mask` for enable and configure the filters for apply cloud masking and `(3) Apply and Save` for save the mask and apply the mask to stack:

![](img/how_to_use_02.png)

### Browse and load the MTL file

The fists step you need to load a MTL file, click in `Browse` and `Load` for read the MTL file, when the MTL file is loaded the others widgets of the plugin is activated for use:

![](img/how_to_use_03.png)

### Load stacks (optional)

The `Load stacks` section you can make and open in Qgis the stack in RGB bands combination as you want for visualize and check the Landsat image, in the right side you can access for special stacks (more uses) RBG bands order, you need to do click in `Load stack` bottom for make and load the stack configured. This is not necessary for process only for view:

![](img/how_to_use_04.png)

### Select the filters to apply

The plugin have a 4 different filters to apply, the Fmask and Blue Band are available for all Landsat, but the Cloud QA and QA Band are available for only SR Landsat version (see more in [Cloud Filters](cloud_filters.md)). You can activate more than one filter at a time, the plugin accumulate the filters in the same order (bottom up).

![](img/how_to_use_05.png)



