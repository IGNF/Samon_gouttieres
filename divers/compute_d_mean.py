import geopandas as gpd
import argparse
import numpy as np






def run(path):
    gdf = gpd.read_file(path)
    values = [[] for i in range(30)]
    for i in range(gdf.shape[0]):
        gouttiere = gdf.iloc[i]
        d_mean = gouttiere["d_mean"]
        if not np.isnan(d_mean):
            nb_segments = gouttiere["nb_segments"]
            if nb_segments >= 10:
                nb_segments = 10
            values[nb_segments].append(d_mean)
    
    for i, l in enumerate(values):
        if len(l)!=0:
            print(f"Nb segments : {i}, Moyenne : {sum(l)/len(l)}, Nombre de segments : {len(l)}") 
            



if __name__=="__main__":
    parser = argparse.ArgumentParser(description="On calcule la distance moyenne entre le bord de toit et les plans")
    parser.add_argument('--path', help='Fichier intersection.gpkg')
    args = parser.parse_args()

    run(args.path)

    