import os
import geopandas as gpd
import argparse
from tqdm import tqdm


parser = argparse.ArgumentParser(description="On regroupe les géométries jointives en une seule géométrie")
parser.add_argument('--input', help='Répertoire où se trouvent les prédictions de frame field learning')
parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
args = parser.parse_args()

input = args.input
output = args.output

if not os.path.exists(output):
    os.makedirs(output)

shapefiles = [i for i in os.listdir(input) if i[-4:]==".shp"]

for shapefile in tqdm(shapefiles):
    gdf = gpd.GeoDataFrame.from_file(os.path.join(input, shapefile))
    gdf_dissolved = gdf.dissolve()
    gdf_exploded = gdf_dissolved.explode(index_parts=True)
    gdf_repaired = gdf_exploded.make_valid()
    gdf_repaired.to_file(os.path.join(output, shapefile))