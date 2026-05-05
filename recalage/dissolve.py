import os
import geopandas as gpd
import argparse
from tqdm import tqdm


def dissolve(input, output):
    if not os.path.exists(output):
        os.makedirs(output)

    gpkgs = [i for i in os.listdir(input) if i[-5:]==".gpkg"]

    for gpkg in tqdm(gpkgs):
        gdf = gpd.GeoDataFrame.from_file(os.path.join(input, gpkg))
        gdf = gdf[gdf["methode_d_acquisition_planimetrique"]!="Photogrammétrie"]
        gdf_dissolved = gdf.dissolve()
        gdf_exploded = gdf_dissolved.explode(index_parts=True)
        gdf_repaired = gdf_exploded.make_valid().set_crs(epsg=2154)
        gdf_repaired.to_file(os.path.join(output, gpkg))


if __name__=="__main__":
    parser = argparse.ArgumentParser(description="On regroupe les géométries jointives en une seule géométrie")
    parser.add_argument('--input', help='Répertoire où se trouvent les prédictions de frame field learning')
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()

    input = args.input
    output = args.output
    dissolve(input, output)