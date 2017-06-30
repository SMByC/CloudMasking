# Cloud filters

There are available four filters in the plugin, depend of the Landsat version or collection that you can use all of this filters. When you active more than one filter, the masking is accumulate from back to top (from Pixel QA to Fmask) and in this case some filters are cover by others (this is that one pixel is market with more than one filter)

**Filters available for Landsat 4, 5 and 7:**

* Fmask
* Blue Band
* Cloud QA (ESPA files)
* Pixel QA (ESPA files)

![](img/filters_layers_L457.png)

**Filters available for Landsat 8:**

* Fmask
* Blue Band
* Aerosol (ESPA files)
* Pixel QA (+cirrus) (ESPA files)

![](img/filters_layers_L8.png)

!!! warning "For Old ESPA version"
    If you want masking for old ESPA version, this plugin continue developing in branch repository, see [installation](installation.md#espa-format-version) for more information about it.

**Pixel values for the cloud mask:**

| Mask         | Pixel Value | Available for                  |
|:-------------|:------------|:-------------------------------|
| Fmask Cloud  | 2           | Raw and ESPA (Landsat 4,5,7,8) |
| Fmask Shadow | 3           | Raw and ESPA (Landsat 4,5,7,8) |
| Fmask Snow   | 4           | Raw and ESPA (Landsat 4,5,7,8) |
| Fmask Water  | 5           | Raw and ESPA (Landsat 4,5,7,8) |
| Blue Band    | 6           | Raw and ESPA (Landsat 4,5,7,8) |
| Cloud QA     | 7           | ESPA (Landsat 4,5,7)           |
| Aerosol      | 8           | ESPA (Landsat 8)               |
| Pixel QA     | 9           | ESPA (Landsat 4,5,7,8)         |
| No Data      | 255         | All                            |
| No Masked    | 1           | All                            |

## Fmask

The Fmask process use a python fmask implementation by  http://pythonfmask.org as a internal library in the plugin. The Fmask is a implement of the algorithms published in:

* Zhu, Z. and Woodcock, C.E. (2012). Object-based cloud and cloud shadow detection in Landsat imagery Remote Sensing of Environment 118 (2012) 83-94.

* Zhu, Z., Wang, S. and Woodcock, C.E. (2015). Improvement and expansion of the Fmask algorithm: cloud, cloud shadow, and snow detection for Landsats 4-7, 8, and Sentinel 2 images Remote Sensing of Environment 159 (2015) 269-277.

![](img/filter_fmask.png)

## Blue Band

This filter use the Landsat blue band for masking all pixel with values less than threshold set.

The blue band is:

* Landsat 4, 5, 7: `band 1`
* Landsat 8: `band 2`

The threshold range depend of the Landsat version:

* Landsat 4, 5, 7: `0-255` (8bits)
* Landsat 8: `0-65534` (16bits)

![](img/filter_blue_band.png)

## Cloud QA

The cloud QA are available for only SR Landsat (ESPA) collection and only for Landsat version 4, 5 and 7. The SR (Surface Reflectance) is a special Landsat collection with more and adjusted products than the raw Landsat products. You can download it from https://espa.cr.usgs.gov/ordering/new

The Cloud QA is a band of 8 bits, usually the filename ends in `*_sr_cloud_qa.tif`. These 8 bits are:

![](img/filter_cloud_qa_bits.png)

For more information consult the [QA description](https://landsat.usgs.gov/landsat-surface-reflectance-quality-assessment)

In the plugin is implemented this filter bit a bit (only the useful bits) and you can enable one or more than one bits, there is also the option for filter `specific decimal` values but applied as a binary value.

![](img/filter_cloud_qa.png)

When multiple bits are selected (and/or specific values) the plugin marked all pixels for each bit selected individually (and not the unique value which these represent together). For example, if cirrus (bit 0) and cloud (bit 1) is selected, first market all pixels that have cirrus regardless of the other values, after do the same with cloud.

## Aerosol

The Aerosol are available for only SR Landsat (ESPA) collection and only for Landsat version 8. The Aerosol is a band of 8 bits, usually the filename ends in `*_sr_aerosol.tif`. These 8 bits are:

![](img/filter_aerosol_bits.png)

For more information consult the [product guide](https://landsat.usgs.gov/sites/default/files/documents/lasrc_product_guide.pdf) and the [QA description](https://landsat.usgs.gov/landsat-surface-reflectance-quality-assessment)

In the plugin is implemented this filter bit a bit (only the useful bits) and you can enable one or more than one bits, there is also the option for filter `specific decimal` values but applied as a binary value.

![](img/filter_aerosol.png)

When multiple bits are selected (and/or specific values) the plugin marked all pixels for each bit selected individually (and not the unique value which these represent together).

## Pixel QA

The Pixel QA are available for only SR Landsat (ESPA) collection. The SR (Surface Reflectance) is a special Landsat collection with more and adjusted products than the raw Landsat products. You can download it from https://espa.cr.usgs.gov/ordering/new

The Pixel QA is a band of 16 bits, usually the filename ends in `*_pixel_qa.tif`.

- These 16 bits for Landsat 4,5,7 are:

![](img/filter_pixel_qa_l457_bits.png)

- These 16 bits for Landsat 8 are:

![](img/filter_pixel_qa_l8_bits.png)

For more information consult the [product guide](https://landsat.usgs.gov/sites/default/files/documents/lasrc_product_guide.pdf) and the [QA description](https://landsat.usgs.gov/landsat-surface-reflectance-quality-assessment)

In the plugin is implemented this filter bit a bit (only the useful bits) and you can enable one or more than one bits, there is also the option for filter `specific decimal` values but applied as a binary value.

- The Pixel QA with Landsat 4,5,7:

![](img/filter_pixel_qa_l457.png)

- The Pixel QA with Landsat 8:

![](img/filter_pixel_qa_l8.png)

When multiple bits are selected (and/or specific values) the plugin marked all pixels for each bit selected individually (and not the unique value which these represent together). For example, if cloud (bit 5) and cloud confidence 67-100% (bits 6-7) is selected, first market all pixels that have cloud (bit 5 as 1) regardless of the other values, after do the same with cloud confidence 67-100%.