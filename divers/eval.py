import geopandas as gpd
import shapely
import numpy as np
from tqdm import tqdm
from shapely import LineString, Point

vt_path = "chantiers/Mont_Dauphin_presentation/vt_lidar.shp"
#predict_path = "chantiers/Mont_Dauphin_presentation/predictions_bd_ortho/ortho.shp"
predict_path = "chantiers/Mont_Dauphin_presentation/gouttieres/batiments_fermes/batiments_fermes.gpkg"


def get_points(path):
    gdf = gpd.read_file(path)
    points = []
    for i in range(gdf.shape[0]):
        geometry = gdf.iloc[i].geometry
        xx, yy = geometry.exterior.coords.xy
        xx = xx.tolist()
        yy = yy.tolist()
        for j in range(len(xx)):
            points.append([xx[j], yy[j]])
    return np.array(points)


points_vt = get_points(vt_path)
print(points_vt.shape)
points_predict = get_points(predict_path)
print(points_predict.shape)
linestrings = []
somme = 0
compte = 0
liste_distance = []
for i in tqdm(range(points_vt.shape[0])):
    distance = np.sqrt((points_predict[:,0]-points_vt[i,0])**2 + (points_predict[:,1]-points_vt[i,1])**2)
    minimum = np.min(distance)
    argmin = np.argmin(distance)
    if minimum < 2:
        liste_distance.append(minimum)
        somme += minimum
        compte += 1
        linestrings.append(LineString([Point(points_predict[argmin,0], points_predict[argmin,1]), Point(points_vt[i,0], points_vt[i,1])]))
liste_distance = np.array(liste_distance)
print(f"Compte : {compte}")
print(f"Moyenne : {np.mean(liste_distance)}")
print(f"Médiane : {np.median(liste_distance)}")
print(f"Std : {np.std(liste_distance)}")

#gpd.GeoDataFrame({"geometry":linestrings}).set_crs(epsg=2154).to_file("ortho_erreur.gpkg")
gpd.GeoDataFrame({"geometry":linestrings}).set_crs(epsg=2154).to_file("proj_erreur.gpkg")
