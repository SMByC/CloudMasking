import os

from CloudMasking.core.cloud_masking_utils import mtl2dict

real_mtl = {'REFLECTANCE_MINIMUM_BAND_9': -0.09998, 'THERMAL_LINES': 7731.0, 'EARTH_SUN_DISTANCE': 0.988947,
            'SCENE_CENTER_TIME': '15:07:42.0386660Z', 'CORNER_LL_PROJECTION_Y_PRODUCT': 43500.0,
            'REFLECTANCE_ADD_BAND_6': -0.1, 'REQUEST_ID': '0501703173371_00009',
            'TIRS_STRAY_LIGHT_CORRECTION_SOURCE': 'TIRS', 'CORNER_LL_LAT_PRODUCT': 0.39355,
            'RADIANCE_MULT_BAND_5': 0.0062513, 'RADIANCE_MULT_BAND_4': 0.010215, 'RADIANCE_MULT_BAND_3': 0.012114,
            'RADIANCE_MULT_BAND_2': 0.013146, 'QUANTIZE_CAL_MIN_BAND_9': 1.0, 'GEOMETRIC_RMSE_MODEL': 22.492,
            'QUANTIZE_CAL_MIN_BAND_7': 1.0, 'QUANTIZE_CAL_MIN_BAND_6': 1.0, 'QUANTIZE_CAL_MIN_BAND_5': 1.0,
            'QUANTIZE_CAL_MIN_BAND_4': 1.0, 'QUANTIZE_CAL_MIN_BAND_3': 1.0, 'QUANTIZE_CAL_MIN_BAND_2': 1.0,
            'QUANTIZE_CAL_MIN_BAND_1': 1.0, 'ELEVATION_SOURCE': 'GLS2000', 'REFLECTANCE_MAXIMUM_BAND_8': 1.2107,
            'CORNER_LR_LON_PRODUCT': -72.52217, 'REFLECTANCE_MAXIMUM_BAND_6': 1.2107,
            'REFLECTANCE_MAXIMUM_BAND_7': 1.2107, 'REFLECTANCE_MAXIMUM_BAND_4': 1.2107,
            'REFLECTANCE_MAXIMUM_BAND_5': 1.2107, 'REFLECTANCE_MAXIMUM_BAND_2': 1.2107,
            'REFLECTANCE_MAXIMUM_BAND_3': 1.2107, 'REFLECTANCE_MAXIMUM_BAND_1': 1.2107,
            'GROUND_CONTROL_POINTS_VERSION': 4.0, 'TRUNCATION_OLI': 'UPPER', 'RADIANCE_MAXIMUM_BAND_4': 618.38562,
            'ELLIPSOID': 'WGS84', 'REFLECTANCE_ADD_BAND_8': -0.1, 'REFLECTANCE_ADD_BAND_4': -0.1,
            'REFLECTANCE_ADD_BAND_7': -0.1, 'RADIANCE_MAXIMUM_BAND_10': 22.0018, 'RADIANCE_MAXIMUM_BAND_11': 22.0018,
            'ANGLE_COEFFICIENT_FILE_NAME': 'LC08_L1TP_007059_20161115_20170318_01_T2_ANG.txt',
            'GRID_CELL_SIZE_THERMAL': 30.0, 'REFLECTANCE_ADD_BAND_5': -0.1, 'QUANTIZE_CAL_MAX_BAND_11': 65535.0,
            'QUANTIZE_CAL_MAX_BAND_10': 65535.0, 'RADIANCE_MAXIMUM_BAND_5': 378.42114, 'QUANTIZE_CAL_MIN_BAND_10': 1.0,
            'REFLECTANCE_ADD_BAND_3': -0.1, 'REFLECTANCE_ADD_BAND_2': -0.1, 'REFLECTANCE_ADD_BAND_1': -0.1,
            'CORNER_UL_LAT_PRODUCT': 2.49154, 'WRS_PATH': 7.0, 'REFLECTANCE_MINIMUM_BAND_4': -0.09998,
            'RADIANCE_MAXIMUM_BAND_6': 94.1099, 'GROUP': 'PROJECTION_PARAMETERS', 'DATA_TYPE': 'L1TP',
            'REFLECTANCE_MULT_BAND_8': 2e-05,
            'FILE_NAME_BAND_QUALITY': 'LC08_L1TP_007059_20161115_20170318_01_T2_BQA.TIF',
            'METADATA_FILE_NAME': 'LC08_L1TP_007059_20161115_20170318_01_T2_MTL.txt',
            'QUANTIZE_CAL_MAX_BAND_4': 65535.0, 'QUANTIZE_CAL_MAX_BAND_7': 65535.0, 'QUANTIZE_CAL_MAX_BAND_6': 65535.0,
            'QUANTIZE_CAL_MAX_BAND_1': 65535.0, 'QUANTIZE_CAL_MAX_BAND_3': 65535.0, 'QUANTIZE_CAL_MAX_BAND_2': 65535.0,
            'QUANTIZE_CAL_MAX_BAND_9': 65535.0, 'QUANTIZE_CAL_MAX_BAND_8': 65535.0, 'REFLECTIVE_LINES': 7731.0,
            'IMAGE_QUALITY_TIRS': 9.0, 'SPACECRAFT_ID': 'LANDSAT_8', 'STATION_ID': 'LGN',
            'CPF_NAME': 'LC08CPF_20161001_20161231_01.01', 'CORNER_UR_LON_PRODUCT': -72.51991,
            'REFLECTANCE_MULT_BAND_9': 2e-05, 'RADIANCE_MULT_BAND_7': 0.000524, 'QUANTIZE_CAL_MIN_BAND_11': 1.0,
            'SENSOR_ID': 'OLI_TIRS', 'RADIANCE_MULT_BAND_6': 0.0015546, 'REFLECTANCE_MULT_BAND_1': 2e-05,
            'REFLECTANCE_MULT_BAND_3': 2e-05, 'REFLECTANCE_MULT_BAND_2': 2e-05, 'REFLECTANCE_MULT_BAND_5': 2e-05,
            'REFLECTANCE_MULT_BAND_4': 2e-05, 'REFLECTANCE_MULT_BAND_7': 2e-05, 'REFLECTANCE_MULT_BAND_6': 2e-05,
            'WRS_ROW': 59.0, 'REFLECTANCE_MINIMUM_BAND_5': -0.09998, 'REFLECTANCE_MINIMUM_BAND_6': -0.09998,
            'REFLECTANCE_MINIMUM_BAND_7': -0.09998, 'REFLECTANCE_MINIMUM_BAND_1': -0.09998,
            'REFLECTANCE_MINIMUM_BAND_2': -0.09998, 'REFLECTANCE_MINIMUM_BAND_3': -0.09998, 'TARGET_WRS_PATH': 7.0,
            'GEOMETRIC_RMSE_MODEL_X': 16.775, 'GEOMETRIC_RMSE_MODEL_Y': 14.983, 'THERMAL_SAMPLES': 7581.0,
            'RADIANCE_MAXIMUM_BAND_8': 699.84235, 'RADIANCE_MAXIMUM_BAND_9': 147.89557, 'SATURATION_BAND_8': 'N',
            'SATURATION_BAND_9': 'N', 'RADIANCE_MULT_BAND_1': 0.012838, 'SATURATION_BAND_2': 'N',
            'SATURATION_BAND_3': 'N', 'RADIANCE_MAXIMUM_BAND_2': 795.80829, 'SATURATION_BAND_1': 'N',
            'SATURATION_BAND_6': 'N', 'SATURATION_BAND_7': 'N', 'SATURATION_BAND_4': 'N', 'SATURATION_BAND_5': 'Y',
            'DATE_ACQUIRED': '2016-11-15', 'REFLECTANCE_ADD_BAND_9': -0.1,
            'RLUT_FILE_NAME': 'LC08RLUT_20150303_20431231_01_12.h5', 'K2_CONSTANT_BAND_10': 1321.0789,
            'LANDSAT_SCENE_ID': 'LC80070592016320LGN01', 'CORNER_LR_PROJECTION_Y_PRODUCT': 43500.0,
            'SUN_AZIMUTH': 133.01953314, 'CORNER_LL_PROJECTION_X_PRODUCT': 548400.0,
            'CORNER_UR_PROJECTION_Y_PRODUCT': 275400.0, 'RADIANCE_MULT_BAND_9': 0.0024431, 'CLOUD_COVER_LAND': 44.74,
            'BPF_NAME_TIRS': 'LT8BPF20161114203648_20161203213854.01', 'QUANTIZE_CAL_MIN_BAND_8': 1.0,
            'RADIANCE_MULT_BAND_8': 0.011561, 'GRID_CELL_SIZE_REFLECTIVE': 30.0, 'ORIENTATION': 'NORTH_UP',
            'REFLECTANCE_MINIMUM_BAND_8': -0.09998, 'CORNER_LR_PROJECTION_X_PRODUCT': 775800.0,
            'RADIANCE_MULT_BAND_11': 0.0003342, 'RADIANCE_MULT_BAND_10': 0.0003342, 'RADIANCE_MINIMUM_BAND_10': 0.10033,
            'RADIANCE_MINIMUM_BAND_11': 0.10033, 'PANCHROMATIC_SAMPLES': 15161.0,
            'ORIGIN': 'Image courtesy of the U.S. Geological Survey', 'TARGET_WRS_ROW': 59.0, 'UTM_ZONE': 18.0,
            'PROCESSING_SOFTWARE_VERSION': 'LPGS_2.7.0', 'REFLECTANCE_MAXIMUM_BAND_9': 1.2107,
            'CORNER_UL_PROJECTION_Y_PRODUCT': 275400.0, 'SUN_ELEVATION': 59.8749502, 'COLLECTION_CATEGORY': 'T2',
            'MAP_PROJECTION': 'UTM', 'IMAGE_QUALITY_OLI': 9.0, 'QUANTIZE_CAL_MAX_BAND_5': 65535.0,
            'FILE_DATE': '2017-03-18T05:16:39Z', 'RESAMPLING_OPTION': 'CUBIC_CONVOLUTION',
            'RADIANCE_MAXIMUM_BAND_1': 777.14728, 'CORNER_UR_LAT_PRODUCT': 2.48927, 'TIRS_SSM_MODEL': 'FINAL',
            'PANCHROMATIC_LINES': 15461.0, 'NADIR_OFFNADIR': 'NADIR', 'CORNER_LR_LAT_PRODUCT': 0.39319,
            'REFLECTIVE_SAMPLES': 7581.0, 'GRID_CELL_SIZE_PANCHROMATIC': 15.0, 'COLLECTION_NUMBER': 1.0,
            'END_GROUP': 'L1_METADATA_FILE', 'TIRS_SSM_POSITION_STATUS': 'ESTIMATED',
            'GROUND_CONTROL_POINTS_MODEL': 30.0, 'RADIANCE_MAXIMUM_BAND_7': 31.72007,
            'FILE_NAME_BAND_3': 'LC08_L1TP_007059_20161115_20170318_01_T2_B3.TIF',
            'FILE_NAME_BAND_2': 'LC08_L1TP_007059_20161115_20170318_01_T2_B2.TIF',
            'FILE_NAME_BAND_1': 'LC08_L1TP_007059_20161115_20170318_01_T2_B1.TIF', 'RADIANCE_MINIMUM_BAND_5': -31.25014,
            'FILE_NAME_BAND_7': 'LC08_L1TP_007059_20161115_20170318_01_T2_B7.TIF',
            'FILE_NAME_BAND_6': 'LC08_L1TP_007059_20161115_20170318_01_T2_B6.TIF',
            'FILE_NAME_BAND_5': 'LC08_L1TP_007059_20161115_20170318_01_T2_B5.TIF',
            'FILE_NAME_BAND_4': 'LC08_L1TP_007059_20161115_20170318_01_T2_B4.TIF', 'CLOUD_COVER': 44.74,
            'FILE_NAME_BAND_9': 'LC08_L1TP_007059_20161115_20170318_01_T2_B9.TIF',
            'FILE_NAME_BAND_8': 'LC08_L1TP_007059_20161115_20170318_01_T2_B8.TIF', 'RADIANCE_MINIMUM_BAND_8': -57.79321,
            'RADIANCE_MINIMUM_BAND_9': -12.21326, 'RADIANCE_ADD_BAND_9': -12.21571, 'RADIANCE_ADD_BAND_8': -57.80477,
            'CORNER_UL_PROJECTION_X_PRODUCT': 548400.0,
            'FILE_NAME_BAND_11': 'LC08_L1TP_007059_20161115_20170318_01_T2_B11.TIF',
            'FILE_NAME_BAND_10': 'LC08_L1TP_007059_20161115_20170318_01_T2_B10.TIF', 'RADIANCE_ADD_BAND_1': -64.18991,
            'BPF_NAME_OLI': 'LO8BPF20161115144844_20161115153323.01', 'RADIANCE_ADD_BAND_3': -60.57079,
            'RADIANCE_ADD_BAND_2': -65.73125, 'RADIANCE_ADD_BAND_5': -31.25639, 'RADIANCE_ADD_BAND_4': -51.0767,
            'RADIANCE_ADD_BAND_7': -2.61998, 'RADIANCE_ADD_BAND_6': -7.77318, 'RADIANCE_MINIMUM_BAND_6': -7.77163,
            'LANDSAT_PRODUCT_ID': 'LC08_L1TP_007059_20161115_20170318_01_T2', 'RADIANCE_MINIMUM_BAND_7': -2.61945,
            'OUTPUT_FORMAT': 'GEOTIFF', 'RADIANCE_MINIMUM_BAND_4': -51.06649, 'K1_CONSTANT_BAND_10': 774.8853,
            'K1_CONSTANT_BAND_11': 480.8883, 'RADIANCE_MINIMUM_BAND_2': -65.71811, 'CORNER_UL_LON_PRODUCT': -74.56464,
            'RADIANCE_MINIMUM_BAND_3': -60.55867, 'RADIANCE_ADD_BAND_11': 0.1, 'RADIANCE_ADD_BAND_10': 0.1,
            'CORNER_UR_PROJECTION_X_PRODUCT': 775800.0, 'RADIANCE_MINIMUM_BAND_1': -64.17707, 'DATUM': 'WGS84',
            'K2_CONSTANT_BAND_11': 1201.1442, 'ROLL_ANGLE': -0.001, 'CORNER_LL_LON_PRODUCT': -74.56504,
            'RADIANCE_MAXIMUM_BAND_3': 733.33051}


def test_load_mtl_file(python_path_project):
    mtl_file = os.path.abspath("test/mtl/LC08_L1TP_007059_20161115_20170318_01_T2_MTL.txt")
    mtl = mtl2dict(mtl_file)

    assert mtl == real_mtl
