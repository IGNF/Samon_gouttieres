from v2.shot import Shot, MNT
from v2.batiment import Batiment
import geopandas as gpd
from typing import List
from shapely import Polygon
from tqdm import tqdm
import os

class Prediction:
    """
    Classe représentant une image avec ses prédictions 
    """

    def __init__(self, shot:Shot, path_predictions:str, mnt:MNT):
        """
        shot : paramètres de l'acquisition de la photo
        path_predictions : chemin vers le fichier shapefile avec les prédictions
        """
        self.shot:Shot = shot
        self.path_predictions:str = path_predictions
        self.mnt:MNT = mnt
        self.batiments:List[Batiment] = self.read_file()

        self.gdf:gpd.GeoDataFrame = None
        

    def read_file(self) -> List[Batiment]:
        """
        Ouvre le fichier shapefile associé à la prédiction et crée un ensemble de bâtiments
        """
        gdf = gpd.read_file(self.path_predictions)
        batiments:List[Batiment] = []
        for geometry in gdf.geometry:
            if isinstance(geometry, Polygon):
                batiments.append(Batiment(geometry, self.shot, self.mnt))
        return batiments
    

    def lisser_geometries(self):
        for batiment in tqdm(self.batiments):
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
        for batiment in tqdm(self.batiments):
            if batiment.is_valid():
                batiment.compute_ground_geometry()


    def create_geodataframe(self):
        geometries = []
        identifiant = []

        for batiment in tqdm(self.batiments):
            if batiment.is_valid():
                geometries.append(batiment.get_geometrie_terrain())
                identifiant.append(batiment.get_identifiant())

        self.gdf = gpd.GeoDataFrame({"id":identifiant, "geometry":geometries})

    def get_geodataframe(self)->gpd.GeoDataFrame:
        return self.gdf
    
    def delete_batiments_invalides(self)->None:
        batiments:List[Batiment] = []
        for batiment in self.batiments:
            if batiment.is_valid():
                batiments.append(batiment)
        self.batiments = batiments

    def get_batiment_i(self, i:int)->Batiment:
        return self.batiments[i]
    
    def get_batiments(self):
        return self.batiments
    

    def export_geometry_terrain(self, dir_path:str):
        geometries = []
        identifiant = []
        identifiant_batiment = []
        z_mean = []

        for batiment in self.batiments:
            if batiment.is_valid():
                geometries.append(batiment.get_geometrie_terrain())
                identifiant.append(batiment.get_identifiant())
                identifiant_batiment.append(batiment.get_groupe_batiment_id())
                z_mean.append(batiment.get_z_mean())

        gdf = gpd.GeoDataFrame({"id":identifiant, "id_bati":identifiant_batiment, "z_mean":z_mean, "geometry":geometries})
        gdf.to_file(os.path.join(dir_path, self.get_image_name()+"_proj.gpkg"))