from __future__ import annotations
from v2.shot import Shot, MNT
from v2.batiment import Batiment
from v2.pateMaison import PateMaison
import geopandas as gpd
from typing import List
from shapely import Polygon
import os
import numpy as np
from shapely.ops import unary_union


class Prediction:
    """
    Classe représentant une image avec ses prédictions 
    """

    def __init__(self, shot:Shot, path_predictions:str, mnt_global:MNT, emprise):
        """
        shot : paramètres de l'acquisition de la photo
        path_predictions : chemin vers le fichier shapefile avec les prédictions
        """
        self.shot:Shot = shot
        self.path_predictions:str = path_predictions
        self.mnt:MNT = MNT.from_mnt(mnt_global, shot.emprise, f"shot_{shot.image}")
        self.batiments:List[Batiment] = []
        self.pates_maisons:List[PateMaison] = []
        self.emprise = emprise
        self.emprise_image = self.emprise_to_geom_image(emprise, mnt_global)

        self.gdf:gpd.GeoDataFrame = None
        self.gdf_pate_maisons:gpd.GeoDataFrame = None
        self.read_file()

    
    def emprise_to_geom_image(self, emprise:gpd.GeoSeries, mnt_global:MNT):
        xmin, ymin, xmax, ymax = emprise.total_bounds
        polygon = Polygon.from_bounds(xmin, ymin, xmax, ymax)


        x, y = polygon.exterior.coords.xy
        z = []
        for i in range(len(x)):
            z.append(mnt_global.get(x[i], y[i])[0])
        x = np.array(x)
        y = np.array(y)
        z = np.array(z)

        c, l = self.shot.world_to_image(x, y, z)

        image_points = []
        for i in range(c.shape[0]):
            image_points.append([c[i], -l[i]])
        emprise_image = Polygon(image_points) 
        return emprise_image

        

    def read_file(self) -> List[Batiment]:
        """
        Ouvre le fichier shapefile associé à la prédiction et crée un ensemble de bâtiments
        """
        gdf = gpd.read_file(self.path_predictions)
        gdf = gdf[gdf.intersects(self.emprise_image)]
        batiments:List[Batiment] = []
        for geometry in gdf.geometry:
            if isinstance(geometry, Polygon):
                batiments.append(Batiment(geometry, self.shot, self.mnt))
        self.batiments = batiments
        self.create_pate_maisons(gdf)


    def create_pate_maisons(self, gdf:gpd.GeoDataFrame):
        merged = unary_union(gdf.geometry)
        if isinstance(merged, Polygon):
            polygons = [merged]
        else:
            polygons = list(merged.geoms)
        for polygon in polygons:
            self.pates_maisons.append(PateMaison(polygon, self.shot, self.mnt))


    def associate_batiment_pate(self):
        geometries = [pm.geometrie_image.buffer(0.1) for pm in self.pates_maisons]
        gdf_pates_maisons = gpd.GeoDataFrame({"geometry":geometries, "id":range(len(geometries))})
        for batiment in self.batiments:
            pate_maison = gdf_pates_maisons[gdf_pates_maisons.contains(batiment.get_image_geometrie())]
            if pate_maison.shape[0]!=1:
                raise ValueError(f"Pas un seul bâtiment : {pate_maison.shape[0]}")
            pate_maison = pate_maison.iloc[0]
            self.pates_maisons[pate_maison["id"]].add_batiment(batiment)
    

    def lisser_geometries(self):
        for batiment in self.batiments:
            batiment.lisser_geometries()
        self.delete_batiments_invalides()

    
    def get_image_name(self)->str:
        return self.shot.image


    def export_geometry_image(self, dir_path:str):
        geometries = []
        identifiant = []

        for batiment in self.batiments:
            if batiment.is_valid():
                geometries.append(batiment.get_image_geometrie())
                identifiant.append(batiment.get_identifiant())

        gdf = gpd.GeoDataFrame({"id":identifiant, "geometry":geometries})
        gdf.to_file(os.path.join(dir_path, self.get_image_name()+".gpkg"))

    
    def compute_ground_geometry(self):
        for batiment in self.batiments:
            if batiment.is_valid():
                batiment.compute_ground_geometry()

    def compute_ground_geometry_pate_maison(self):
        for pate_maisons in self.pates_maisons:
            pate_maisons.compute_ground_geometry()


    def check_in_emprise(self, emprise):
        liste_valide = []
        for batiment in self.batiments:
            if batiment.geometrie_terrain is not None and batiment.geometrie_terrain.within(emprise).any():
                liste_valide.append(batiment)
        self.batiments = liste_valide

    def check_in_emprise_pate_maisons(self, emprise):
        liste_valide = []
        for pm in self.pates_maisons:
            if pm.geometrie_terrain.intersects(emprise).any():
                liste_valide.append(pm)
        self.pates_maisons = liste_valide


    def create_geodataframe(self):
        geometries = []
        identifiant = []
        self.batiments_keep = []
        identifiant_pm = []

        for batiment in self.batiments:
            if batiment.is_valid() and not batiment._marque:
                geometries.append(batiment.get_geometrie_terrain())
                identifiant.append(batiment.get_identifiant())
                self.batiments_keep.append(batiment)
                identifiant_pm.append(batiment.get_groupe_batiment_id())
        self.gdf = gpd.GeoDataFrame({"id":identifiant, "geometry":geometries, "id_gpm":identifiant_pm})

    def create_geodataframe_pates_maisons(self):
        geometries = []
        identifiant = []
        for pm in self.pates_maisons:
            geometries.append(pm.get_geometrie_terrain())
            identifiant.append(pm.get_identifiant())
        self.gdf_pate_maisons = gpd.GeoDataFrame({"id":identifiant, "geometry":geometries})

    def get_geodataframe(self)->gpd.GeoDataFrame:
        return self.gdf
    
    def get_geodataframe_pate_maison(self)->gpd.GeoDataFrame:
        return self.gdf_pate_maisons
    
    def delete_batiments_invalides(self)->None:
        batiments:List[Batiment] = []
        for batiment in self.batiments:
            if batiment.is_valid():
                batiments.append(batiment)
        self.batiments = batiments

    def get_batiment_i(self, i:int)->Batiment:
        return self.batiments_keep[i]
    
    def get_pate_maison_i(self, i:int)->PateMaison:
        return self.pates_maisons[i]
    
    def get_batiments(self):
        return self.batiments
    
    def get_pates_maisons(self):
        return self.pates_maisons
    

    def export_geometry_terrain(self, dir_path:str):
        geometries = []
        identifiant = []
        identifiant_batiment = []
        z_mean = []
        nb_images = []
        methode = []

        for batiment in self.batiments:
            geometries.append(batiment.get_geometrie_terrain())
            identifiant.append(batiment.get_identifiant())
            identifiant_batiment.append(batiment.get_groupe_batiment_id())
            z_mean.append(batiment.get_z_mean())
            nb_images.append(batiment.groupe_batiment_nb_images_z_estim)
            methode.append(batiment.groupe_batiment_methode_estimation_hauteur)

        gdf = gpd.GeoDataFrame({"id":identifiant, "id_bati":identifiant_batiment, "z_mean":z_mean, "nb_images":nb_images, "methode":methode, "geometry":geometries}, crs="EPSG:2154")
        gdf.to_file(os.path.join(dir_path, self.get_image_name()+"_proj.gpkg"))

    def export_pate_maison_geometry_terrain(self, dir_path:str):
        geometries = []
        identifiant = []
        identifiant_gpm = []

        for pm in self.pates_maisons:
            geometries.append(pm.get_geometrie_terrain())
            identifiant.append(pm.get_identifiant())
            identifiant_gpm.append(pm.get_id_groupe_pate_maison())

        gdf = gpd.GeoDataFrame({"id":identifiant, "id_groupe_pm":identifiant_gpm, "geometry":geometries}, crs="EPSG:2154")
        gdf.to_file(os.path.join(dir_path, self.get_image_name()+"_proj.gpkg"))
    

    def export_segment_geometry_terrain(self, dir_path:str):
        geometries = []
        identifiant = []
        identifiant_segment = []
        identifiant_bati = []
        voisin_1 = []
        voisin_2 = []

        for batiment in self.batiments:
            for segment in batiment.get_segments():
                geometries.append(segment.get_geometrie_terrain())
                identifiant.append(segment.get_identifiant())
                identifiant_segment.append(segment.get_identifiant_groupe())
                identifiant_bati.append(segment.get_identifiant_batiment())
                voisin_1.append(segment.get_voisin_1().get_identifiant())
                voisin_2.append(segment.get_voisin_2().get_identifiant())

        gdf = gpd.GeoDataFrame({"id":identifiant, "id_segment":identifiant_segment, "id_bati":identifiant_bati, "voisin_1":voisin_1, "voisin_2":voisin_2, "geometry":geometries}, crs="EPSG:2154")
        gdf.to_file(os.path.join(dir_path, self.get_image_name()+"_proj.gpkg"))


    def association_pates_maisons(self, prediction_2:Prediction):
        geoserie_1:gpd.GeoDataFrame = self.get_geodataframe_pate_maison().geometry
        # On parcourt les autres shapefile
        if self.shot.image!=prediction_2.shot.image:
            # On récupère la géosérie du deuxième shapefile
            
            geoserie_2:gpd.GeoDataFrame = prediction_2.get_geodataframe_pate_maison().geometry
            if geoserie_1.shape[0]==0 or geoserie_2.shape[0]==0:
                return
            # On récupère les intersections entre les géométries terrain des bâtiments
            intersections = geoserie_2.sindex.query(geoserie_1, predicate="intersects")
            for i in range(geoserie_1.shape[0]):
                
                # Pour chaque bâtiment, on récupère parmi les bâtiments qu'il intersecte celui avec lequel il partage la plus grande aire
                pm_1 = self.get_pate_maison_i(i)
                
                pm_1_emprise = pm_1.get_geometrie_terrain()
                area_max = 0
                id_max = None
                indices = np.where(intersections[0,:]==i)[0]
                for j in range(indices.shape[0]):
                    indice = indices[j]                                
                    pm_2_emprise = prediction_2.get_pate_maison_i(intersections[1,indice])
                    aire_commune = pm_1_emprise.intersection(pm_2_emprise.get_geometrie_terrain()).area
                    if aire_commune > area_max:
                        area_max = aire_commune
                        id_max = pm_2_emprise
                if id_max is not None:
                    pm_1.add_homologue(id_max.identifiant)
                    id_max.add_homologue(pm_1.identifiant)