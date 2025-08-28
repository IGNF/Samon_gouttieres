from pathlib import Path
import geopandas as gpd
from tqdm import tqdm

couche_ref = Path("chantiers/datasets_evaluation/Martigne/bd_topo/bati_bd_topo.gpkg")
couche_pred = Path("chantiers/datasets_evaluation/Martigne/gouttieres/batiments_fermes/batiments_fermes_20.gpkg")

gdf_ref = gpd.read_file(couche_ref).to_crs(epsg=2154)
gdf_pred = gpd.read_file(couche_pred)

values = [0,0]

for i in tqdm(range(gdf_ref.shape[0])):
    geometry = gdf_ref.iloc[i].geometry
    
    if geometry.intersects(gdf_pred.geometry).any():
        values[0]+=1
    else:
        values[1]+=1

rappel = values[0]/(sum(values))
print("rappel : ", rappel)


values = [0,0]

for i in tqdm(range(gdf_pred.shape[0])):
    geometry = gdf_pred.iloc[i].geometry
    
    if geometry.intersects(gdf_ref.geometry).any():
        values[0]+=1
    else:
        values[1]+=1
print(values)

precision = values[0]/(sum(values))
print("précision : ", precision)

print("F1-score : ", 2*precision*rappel/(precision+rappel))