from v2.shot import Shot, MNT
from v2.batiment import Batiment, BatimentBDTopo, BatimentImageOrientee
import geopandas as gpd
from typing import List
from shapely import Polygon
import os
from abc import abstractmethod


class Prediction:
    
    def __init__(self, path, mnt):
        self.path_predictions:str = path
        self.mnt:MNT = mnt
        self.batiments:List[Batiment] = []
        self.gdf:gpd.GeoDataFrame = None


    @abstractmethod
    def lisser_geometries(self):
        pass


    @abstractmethod
    def export_geometry_image(self):
        pass

    @abstractmethod
    def compute_ground_geometry(self):
        pass

    @abstractmethod
    def export_geometry_image(self, dir_path:str):
        pass

    @abstractmethod
    def get_image_name(self)->str:
        pass

    def check_in_emprise(self, emprise):
        liste_valide = []
        for batiment in self.batiments:
            if batiment.geometrie_terrain.within(emprise).any():
                liste_valide.append(batiment)
        self.batiments = liste_valide

    def create_geodataframe(self):
        geometries = []
        identifiant = []
        self.batiments_keep = []

        for batiment in self.batiments:
            if batiment.is_valid() and not batiment._marque:
                geometries.append(batiment.get_geometrie_terrain())
                identifiant.append(batiment.get_identifiant())
                self.batiments_keep.append(batiment)

        self.gdf = gpd.GeoDataFrame({"id":identifiant, "geometry":geometries})

    
    def get_geodataframe(self)->gpd.GeoDataFrame:
        return self.gdf
    
    def get_batiment_i(self, i:int)->Batiment:
        return self.batiments_keep[i]
    
    def get_batiments(self)->List[Batiment]:
        return self.batiments
    
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
            nb_images.append(batiment.groupe_batiment.nb_images_z_estim)
            methode.append(batiment.groupe_batiment.get_methode_estimation_hauteur())

        gdf = gpd.GeoDataFrame({"id":identifiant, "id_bati":identifiant_batiment, "z_mean":z_mean, "nb_images":nb_images, "methode":methode, "geometry":geometries}, crs="EPSG:2154")
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

class PredictionBDTOPO(Prediction):

    def __init__(self, path_bd_topo, mnt:MNT, emprise:Polygon):
        super().__init__(path_bd_topo, mnt)
        
        self.batiments:List[BatimentBDTopo] = self.read_file(emprise)

    def read_file(self, emprise)->List[BatimentBDTopo]:
        gdf = gpd.read_file(self.path_predictions)
        gdf = gdf[gdf.within(emprise.unary_union)]
        batiments:List[BatimentBDTopo] = []
        for geometry in gdf.geometry:
            if isinstance(geometry, Polygon):
                batiments.append(BatimentBDTopo(geometry, self.mnt))
        return batiments
    
    def lisser_geometries(self):
        "Les géométries sont déjà propres, pas besoin de les lisser"
        pass

    def export_geometry_image(self):
        "Pas de géométrie image à exporter"
        pass

    def compute_ground_geometry(self):
        "Pas de géométrie terrain à calculer"
        pass

    def export_geometry_image(self, dir_path:str):
        pass

    def get_image_name(self)->str:
        return "BD_TOPO"

    def export_segment_geometry_terrain(self, dir_path:str):
        pass

    

    

class PredictionImageorientee(Prediction):
    """
    Classe représentant une image avec ses prédictions 
    """

    def __init__(self, shot:Shot, path_predictions:str, mnt:MNT):
        """
        shot : paramètres de l'acquisition de la photo
        path_predictions : chemin vers le fichier shapefile avec les prédictions
        """
        super().__init__(path_predictions, mnt)
        self.shot:Shot = shot
        self.batiments:List[BatimentImageOrientee] = self.read_file()


    def read_file(self) -> List[BatimentImageOrientee]:
        """
        Ouvre le fichier shapefile associé à la prédiction et crée un ensemble de bâtiments
        """
        gdf = gpd.read_file(self.path_predictions)
        batiments:List[BatimentImageOrientee] = []
        for geometry in gdf.geometry:
            if isinstance(geometry, Polygon):
                batiments.append(BatimentImageOrientee(geometry, self.shot, self.mnt))
        return batiments
    

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



    
    def delete_batiments_invalides(self)->None:
        batiments:List[BatimentImageOrientee] = []
        for batiment in self.batiments:
            if batiment.is_valid():
                batiments.append(batiment)
        self.batiments = batiments