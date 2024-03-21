import os
import geopandas as gpd
from tqdm import tqdm
import argparse
from batiRecalage import charger_bati, charger_bati_gouttieres




def get_id_max(chemin):
    id_max = -1
    gdf = gpd.read_file(chemin)
    for geometry in gdf.iterfeatures():
        id_max = max(id_max, geometry["properties"]["id"])
    return [[] for i in range(id_max+1)]




def construire_geoseries(batis_par_shapefile):
    geoseries = {}
    for shapefile in batis_par_shapefile:
        geometries = []
        for bati in shapefile["batis"]:
            geometries.append(bati.emprise_sol())

        geoseries[shapefile["shapefile"]] = gpd.GeoSeries(geometries).make_valid()

    return geoseries


def association(batis_par_shapefile, geoseries):
    # On parcourt chaque shapefile
    for shapefile in batis_par_shapefile:
        # On parcourt les batiments du shapefile
        for bati in shapefile["batis"]:
            # On parcourt les autres shapefiles
            for s2 in batis_par_shapefile:
                if s2["shapefile"] != shapefile["shapefile"]:
                    geoserie = geoseries[s2["shapefile"]]

                    bati_emprise = bati.emprise_sol()
                   
                    try:
                        if geoserie.intersects(bati_emprise).any():
                            intersection = geoserie.intersection(bati_emprise)

                            aire_commune = intersection.area

                            bati_homologue = s2["batis"][aire_commune.argmax()]

                            bati_homologue.add_homologue(bati)
                            bati.add_homologue(bati_homologue)
                    except:
                        print("Erreur")


def graphe_connexe(batis_par_shapefile):
    id_bati = 0
    for shapefile in batis_par_shapefile:
        for bati in tqdm(shapefile["batis"]):
            if not bati.marque:
                liste = [bati]
                bati.id = id_bati
                bati.marque = True

                while len(liste) > 0:
                    b = liste.pop()
                    for homologue in b.homologue:
                        if not homologue.marque:
                            homologue.id = id_bati
                            homologue.marque = True
                            if homologue not in liste:
                                liste.append(homologue)

                id_bati += 1


def sauvegarde_projection(batis_par_shapefile):
    for shapefile in batis_par_shapefile:
        id = []
        polygones = []
        id_origine = []
        for bati in tqdm(shapefile["batis"]):
            polygones.append(bati.linestring())
        
            id.append(bati.id)
            id_origine.append(bati.id_origine)

        d = {"id": id, "id_origine":id_origine, "geometry": polygones}
        gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
        gdf.to_file(os.path.join(output, shapefile["shapefile"]+".shp"))



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="On associe le même identifiant à tous les polygones représentant un même bâtiment")
    parser.add_argument('--input_gouttieres', help='Répertoire où se trouvent les bâtiments fermés')
    parser.add_argument('--input_BD_Uni', help='Répertoire contenant les bâtiments de la BD Uni à recaler')
    parser.add_argument('--output', help='Répertoire où sauvegarder les résultats')
    args = parser.parse_args()


    input_gouttieres = args.input_gouttieres
    input_BD_Uni = args.input_BD_Uni
    output = args.output

    if not os.path.exists(output):
        os.makedirs(output)


    liste_id = get_id_max(input_gouttieres)
    bati_goutieres = charger_bati_gouttieres(input_gouttieres, "id", liste_id=liste_id)
    bati_bd_uni = charger_bati(input_BD_Uni, "level_1")


    batis_par_shapefile = [{"shapefile":"goutieres", "batis":bati_goutieres}, {"shapefile":"bd_uni", "batis":bati_bd_uni}]

    geoseries = construire_geoseries(batis_par_shapefile)

    association(batis_par_shapefile, geoseries)

    graphe_connexe(batis_par_shapefile)

    sauvegarde_projection(batis_par_shapefile)