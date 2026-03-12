import time
from osgeo import gdal

path = "chantiers/datasets_evaluation/Mont_Dauphin/mnt/mnt.vrt"


tic = time.time()
ds = gdal.Open(path)
band = ds.GetRasterBand(1)
array = band.ReadAsArray(1000, 1000, 4000, 4000)
print("toc : ", time.time()-tic)

ds = gdal.Open(path)
band = ds.GetRasterBand(1)
array = band.ReadAsArray()
tic = time.time()
array2 = array[1000:5000,1000:5000]
print("toc : ", time.time()-tic)