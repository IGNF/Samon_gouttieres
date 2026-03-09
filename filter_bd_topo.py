import geopandas as gpd
import geopandas as gpd
import numpy as np
from shapely.ops import unary_union
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from shapely import Polygon


def group_batis(gdf):
    distance = 0.5

    # index spatial
    sindex = gdf.sindex

    rows = []
    cols = []

    for i, geom in enumerate(gdf.geometry):
        # candidats dans un buffer de 0.5 m
        possible = list(sindex.query(geom.buffer(distance)))
        
        for j in possible:
            if i >= j:
                continue
            
            if geom.distance(gdf.geometry.iloc[j]) <= distance:
                rows.append(i)
                cols.append(j)

    # matrice d'adjacence
    n = len(gdf)
    data = np.ones(len(rows))
    adj_matrix = csr_matrix((data, (rows, cols)), shape=(n, n))

    # symétriser
    adj_matrix = adj_matrix + adj_matrix.T

    # composantes connexes
    n_components, labels = connected_components(adj_matrix)

    # ajouter label de groupe
    gdf["group"] = labels
    gdf_merged = gdf.dissolve(by="group")
    gdf_merged = gdf_merged.reset_index()
    return gdf_merged


def get_type_acqu_plani(bd_topo_intersects):
    photogrammetrie = True
    for i in range(bd_topo_intersects.shape[0]):
        if bd_topo_intersects.iloc[i]["ACQU_PLANI"]!="Photogrammétrie":
            photogrammetrie = False
    return photogrammetrie

chantier = "D17_2024"

# bd topo d06
#bd_topo = "/media/store-ref/bases-vectorielles/BDTopo/Shapefile/254/BDTOPO_3-5_TOUSTHEMES_SHP_LAMB93_D006_2025-12-15/BDTOPO/1_DONNEES_LIVRAISON_2025-12-00073/BDT_3-5_SHP_LAMB93_D006-ED2025-12-15/BATI/BATIMENT.shp"
#bd topo d17
bd_topo = "/media/store-ref/bases-vectorielles/BDTopo/Shapefile/254/BDTOPO_3-5_TOUSTHEMES_SHP_LAMB93_D017_2025-12-15/BDTOPO/1_DONNEES_LIVRAISON_2025-12-00073/BDT_3-5_SHP_LAMB93_D017-ED2025-12-15/BATI/BATIMENT.shp"
for emprise_number in range(11):
    batis_samon = gpd.read_file(f"chantiers/{chantier}/gouttieres/{emprise_number}/gouttieres/batiments_fermes/batiments_fermes.gpkg")
    output_file = f"chantiers/{chantier}/gouttieres/{emprise_number}/gouttieres/batiments_fermes/post_correction.gpkg"
    batis_bd_topo = gpd.read_file(bd_topo)
    xmin, ymin,xmax,ymax = batis_samon.total_bounds
    emprise = Polygon.from_bounds(xmin, ymin,xmax,ymax) 
    batis_bd_topo = batis_bd_topo[batis_bd_topo.intersects(emprise)]


    batis_samon_groupe = group_batis(batis_samon)
    batis_bd_topo_groupe = group_batis(batis_bd_topo)

    batis_samon_groupe.to_file("batis_samon_groupe.gpkg")
    batis_bd_topo_groupe.to_file("batis_bd_topo_groupe.gpkg")

    seuil_iou = 0.3
    geometries = []
    origine = []
    for i in range(batis_samon_groupe.shape[0]):
        geom_samon = batis_samon_groupe.iloc[i]["geometry"]
        bd_topo_intersects = batis_bd_topo_groupe[batis_bd_topo_groupe.intersects(geom_samon)]
        if bd_topo_intersects.shape[0]>0:
            geom_bd_topo = unary_union(bd_topo_intersects.geometry)
            intersection = geom_bd_topo.intersection(geom_samon).area
            union = geom_bd_topo.union(geom_samon).area
            if intersection/union < seuil_iou:
                continue
            if get_type_acqu_plani(bd_topo_intersects):
                geometries.append(unary_union(bd_topo_intersects["geometry"]))
                origine.append("BD Topo")
            else:
                group = batis_samon_groupe.iloc[i]["group"]
                geoms_samon_origine = batis_samon[batis_samon["group"]==group]
                for k in range(geoms_samon_origine.shape[0]):
                
                    geometries.append(geoms_samon_origine.iloc[k]["geometry"])
                    origine.append("Samon")

    gpd.GeoDataFrame({"geometry":geometries, "origine":origine}).set_crs(epsg=2154).to_file(output_file)
