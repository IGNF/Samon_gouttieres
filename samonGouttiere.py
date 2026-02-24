import argparse
import os
from v2.shot import MNT, RAF, Shot, Calibration, ShotPompei, ShotOriente
from v2.prediction import Prediction, PredictionBDTOPO, PredictionImageorientee
from typing import List
from lxml import etree
from v2.association_batiment_engine import AssociationBatimentEngine
from v2.association_segments_engine import AssociationSegmentsEngine
from v2.groupe_batiments import GroupeBatiments
from v2.groupe_segments import GroupeSegments
from v2.calcul_intersection_engine import CalculIntersectionEngine
from v2.fermer_batiment_engine import FermerBatimentEngine
from v2.samon.monoscopie import Monoscopie
from v2.amelioration_bd_topo import AmeliorationBDTopoEngine
import geopandas as gpd
from shapely import Polygon
from tqdm import tqdm
import time
import warnings
from pathlib import Path
warnings.filterwarnings("ignore", message="'crs' was not provided")

class SamonGouttiere:

    def __init__(self, path_chantier:str, path_output:str, path_emprise:str, pompei:bool, path_bd_topo):
        
        # Chemin où se trouve le chantier
        if not os.path.isdir(path_chantier):
            return ValueError(f"{path_chantier} n'est pas un répertoire")
        self.path_chantier = path_chantier
        self.path_output = path_output
        os.makedirs(os.path.join(self.path_output, "gouttieres"), exist_ok=True)
        if os.path.isfile(path_bd_topo):
            self.path_bd_topo = Path(path_bd_topo)
        else:
            self.path_bd_topo = None
            print("Pas de BD Topo utilisée")

        self.mnt:MNT = None
        self.raf:RAF = None
        self.shots:List[Shot] = []
        self.predictions:List[Prediction] = []

        self.groupe_batiments:List[GroupeBatiments] = []
        self.groupe_segments:List[GroupeSegments] = []

        self.monoscopie:Monoscopie = []

        self.pompei = pompei

        self.emprise:gpd.GeoDataFrame = self.charger_emprise(path_emprise)


    def charger_emprise(self, chemin_emprise)->gpd.GeoDataFrame:
        gdf = None
        if chemin_emprise is not None and chemin_emprise is not None:
            gdf = gpd.read_file(chemin_emprise).geometry
        return gdf

    
    def get_mnt_path(self) -> str:
        """
        Renvoie le chemin vers le mnt
        """
        path = os.path.join(self.path_chantier, "mnt", "mnt.vrt")
        if not os.path.isfile(path):
            return ValueError(f"{path} n'existe pas")
        return path
    
    def get_pva_path(self)->str:
        path = os.path.join(self.path_chantier, "pvas")
        if not os.path.isdir(path):
            return ValueError(f"{path} n'existe pas")
        return path
    
    
    def get_raf_path(self) -> str:
        """
        Renvoie le chemin vers la grille raf
        """
        path = os.path.join(self.path_chantier, "raf", "raf2020_2154.tif")
        if not os.path.isfile(path):
            return ValueError(f"{path} n'existe pas")
        return path


    def get_predictions_ffl_dir(self) -> str:
        """
        Renvoie le répertoire avec les prédictions du frame field learning
        """
        path = os.path.join(self.path_chantier, "gouttieres", "predictions_FFL")
        if not os.path.isdir(path):
            return ValueError(f"{path} n'existe pas")
        return path

    def get_predictions_ffl(self) -> List[str]:
        """
        Renvoie les prédictions ffl sous format shapefile
        """
        predictions = [i for i in os.listdir(self.get_predictions_ffl_dir()) if i[-4:]==".shp" or i[-5:]==".gpkg"]
        return predictions
    
    def get_ta_path(self):
        """
        Renvoie le fichier ta.xml
        """
        dir_path = os.path.join(self.path_chantier, "orientation")
        if not os.path.isdir(dir_path):
            return ValueError(f"{dir_path} n'existe pas")
        files = [i for i in os.listdir(dir_path) if i[-4:]==".XML"]
        if len(files)!=1:
            raise ValueError(f"Il ne faut qu'un seul fichier orientation dans {dir_path}")
        return os.path.join(dir_path, files[0])


    def get_shots(self, predictions_ffl:List[str]) -> List[ShotOriente]:
        """
        Renvoie les objets shots pour chaque image orientée pour lesquelles on dispose des prédictions ffl
        """
        tree = etree.parse(self.get_ta_path())
        root = tree.getroot()

        centre_rep_local = root.find(".//centre_rep_local")
        centre_rep_local_x = float(centre_rep_local.find(".//x").text)
        centre_rep_local_y = float(centre_rep_local.find(".//y").text)
        centre_rep_local = [centre_rep_local_x, centre_rep_local_y]
        
        pvas = [i.split(".")[0] for i in predictions_ffl]
        shots = []
        for vol in root.getiterator("vol"):

            sensors = vol.findall(".//sensor")

            for cliche in vol.getiterator("cliche"):
                image = cliche.find("image").text.strip()
                if image in pvas:
                    shot = ShotOriente.createShot(cliche, self.raf, centre_rep_local, sensors)
                    emprise:Polygon = shot.emprise
                    if (self.emprise is not None and emprise.intersects(self.emprise).any()) or self.emprise is None:
                        shots.append(shot)
        return shots
    

    def get_cameras_pompei(self)->List[Calibration]:
        """
        Lit les fichiers de calibration Micmac
        """
        dir_path = os.path.join(self.path_chantier, "orientation")
        calib_files = [i for i in os.listdir(dir_path) if i[-4:]==".xml" and "AutoCal" in i]
        calibrations = {}
        for calib_file in calib_files:
            calib = Calibration.createCalibration(os.path.join(dir_path, calib_file))
            calibrations[calib_file] = calib
        return calibrations
    
    def get_shots_pompei(self, calibrations:List[Calibration], predictions_ffl:List[str], mnt:MNT):
        """
        Crée les objets Shot à partir des fichiers d'orientation Micmac
        """
        dir_path = os.path.join(self.path_chantier, "orientation")
        ori_files = [i for i in os.listdir(dir_path) if i[-4:]==".xml" and "Orientation" in i]
        shots = []
        for ori_file in ori_files:
            if not ori_file.replace("Orientation-", "").replace(".tif.xml", ".shp") in predictions_ffl:
                continue
                
            shot = ShotPompei.createShot(os.path.join(dir_path, ori_file), calibrations)
            shot.compute_emprise(mnt)
            shots.append(shot)  
        return shots
    

    def get_images_pompei(self, predictions_ffl:List[str], mnt:MNT)-> List[ShotPompei]:
        """
        Récupère les objets Shot à partir d'orientations Micmac
        """
        calibrations = self.get_cameras_pompei()
        shots = self.get_shots_pompei(calibrations, predictions_ffl, mnt)
        return shots

    

    def run(self):
        tic = time.time()
        self.load()
        self.lisser_geometries()
        self.association_bati()
        self.association_segments()
        self.calculer_intersections()
        self.fermer_batiment()
        self.ameliorer_avec_bd_topo()
        print(f"Durée du traitement : {time.time() - tic} secondes")



    def load(self):
        """
        Charge les données
        """
        self.mnt = MNT(self.get_mnt_path())
        self.raf = RAF(self.get_raf_path())
        predictions_ffl = self.get_predictions_ffl()
        if self.pompei:
            self.shots = self.get_images_pompei(predictions_ffl, self.mnt)
        else:
            self.shots = self.get_shots(predictions_ffl)

        
        predictions = []
        for prediction_ffl in tqdm(predictions_ffl):
            for shot in self.shots:
                if shot.image+".shp" == prediction_ffl or shot.image+".gpkg" == prediction_ffl:
                    predictions.append(PredictionImageorientee(shot, os.path.join(self.get_predictions_ffl_dir(), prediction_ffl), self.mnt))
        self.predictions = predictions

        if self.path_bd_topo is not None:
            self.predictions.append(PredictionBDTOPO(self.path_bd_topo, self.mnt, self.emprise))

        self.monoscopie = Monoscopie(self.get_pva_path(), self.mnt, self.raf, self.shots)


    def lisser_geometries(self):
        """
        Lisse les géométries de chaque polygones
        """
        
        print("Lissage de la géométrie")
        os.makedirs(os.path.join(self.path_output, "gouttieres", "nettoyage"), exist_ok=True)
        for prediction in tqdm(self.predictions):
            prediction.lisser_geometries()
            prediction.export_geometry_image(os.path.join(self.path_output, "gouttieres", "nettoyage"))


    def association_bati(self):
        """
        Associer les bâtiments entre eux
        """
        association_batiments_engine = AssociationBatimentEngine(self.predictions, self.monoscopie, self.emprise, self.pompei)
        self.groupe_batiments = association_batiments_engine.run()

        os.makedirs(os.path.join(self.path_output, "gouttieres", "association_batiment"), exist_ok=True)
        for prediction in self.predictions:
            prediction.export_geometry_terrain(os.path.join(self.path_output, "gouttieres", "association_batiment"))

    
    def association_segments(self):
        print("Association des segments")
        association_segments_engine = AssociationSegmentsEngine(self.groupe_batiments)
        self.groupe_segments = association_segments_engine.run()
        
        os.makedirs(os.path.join(self.path_output, "gouttieres", "association_segments"), exist_ok=True)
        for prediction in self.predictions:
            prediction.export_segment_geometry_terrain(os.path.join(self.path_output, "gouttieres", "association_segments"))


    def calculer_intersections(self):
        """
        On calcule les intersections de plans dans l'espace 
        """
        calcule_intersection_engine = CalculIntersectionEngine(self.groupe_segments)
        calcule_intersection_engine.run()
        self.export_intersections()


    def export_intersections(self):
        geometries = []
        nb_segments = []
        d_mean = []
        residus = []
        identifiant = []

        for groupe_segments in self.groupe_segments:
            if not groupe_segments._supprime:
                geometries.append(groupe_segments.get_geometrie())
                nb_segments.append(groupe_segments.get_nb_segments())
                d_mean.append(groupe_segments.get_d_mean())
                residus.append(groupe_segments.get_residu_moyen())
                identifiant.append(groupe_segments.get_identifiant())

        os.makedirs(os.path.join(self.path_output, "gouttieres", "intersections"), exist_ok=True)
        gdf = gpd.GeoDataFrame({"id":identifiant, "residus":residus, "d_mean":d_mean, "nb_segments":nb_segments, "geometry":geometries}, crs="EPSG:2154")
        gdf.to_file(os.path.join(self.path_output, "gouttieres", "intersections", "intersections.gpkg"))


    def fermer_batiment(self):
        fermer_batiment_engine = FermerBatimentEngine(self.groupe_batiments)
        fermer_batiment_engine.run()
        self.export_batiments_fermes()
        self.export_intersections_ajustees()

    def ameliorer_avec_bd_topo(self):
        ameliorationBDTopoEngine = AmeliorationBDTopoEngine(self.groupe_batiments)
        ameliorationBDTopoEngine.run()
        self.export_batiments_ameliores_bd_topo()

    def export_batiments_fermes(self):
        geometries = []
        identifiant = []
        methode = []
        methode_estimation_alti = []
        estimation_z = []
        delta_estim = []


        for groupe_batiment in self.groupe_batiments:
            geometrie = groupe_batiment.get_geometrie_fermee()
            for geom in geometrie.geoms:
                geometries.append(geom)
                identifiant.append(groupe_batiment.get_identifiant())
                methode.append(groupe_batiment.get_methode_fermeture())
                methode_estimation_alti.append(groupe_batiment.get_methode_estimation_hauteur())
                estimation_z.append(groupe_batiment.estim_z)

                delta_z_list = []
                for point in geom.exterior.coords:
                    z = self.mnt.get(point[0], point[1])
                    delta_z = point[2] - z
                    delta_z_list.append(delta_z[0])
                delta_z_mean = sum(delta_z_list)/len(delta_z_list)
                if groupe_batiment.estim_z is not None:
                    delta_estim.append(groupe_batiment.estim_z - delta_z_mean)
                else:
                    delta_estim.append(0)
        d = {"id_bati":identifiant, "methode":methode, "estim_alti":methode_estimation_alti, "estim_z":estimation_z, "delta_estim":delta_estim, "geometry":geometries}
        
        os.makedirs(os.path.join(self.path_output, "gouttieres", "batiments_fermes"), exist_ok=True)
        gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
        gdf.to_file(os.path.join(self.path_output, "gouttieres", "batiments_fermes", "batiments_fermes.gpkg"))

    def export_batiments_ameliores_bd_topo(self):
        geometries = []
        identifiant = []
        methode = []
        methode_estimation_alti = []
        estimation_z = []
        delta_estim = []
        origine = []


        for groupe_batiment in self.groupe_batiments:
            geometrie = groupe_batiment.get_geometrie_amelioree_bd_topo()
            if geometrie is None:
                continue
            for geom in geometrie.geoms:
                geometries.append(geom)
                identifiant.append(groupe_batiment.get_identifiant())
                methode.append(groupe_batiment.get_methode_fermeture())
                methode_estimation_alti.append(groupe_batiment.get_methode_estimation_hauteur())
                estimation_z.append(groupe_batiment.estim_z)
                origine.append(groupe_batiment.origine_geometrie_amelioree_bd_topo)

                delta_z_list = []
                for point in geom.exterior.coords:
                    z = self.mnt.get(point[0], point[1])
                    delta_z = point[2] - z
                    delta_z_list.append(delta_z[0])
                delta_z_mean = sum(delta_z_list)/len(delta_z_list)
                if groupe_batiment.estim_z is not None:
                    delta_estim.append(groupe_batiment.estim_z - delta_z_mean)
                else:
                    delta_estim.append(0)
        d = {"id_bati":identifiant, "methode":methode, "estim_alti":methode_estimation_alti, "estim_z":estimation_z, "delta_estim":delta_estim, "origine":origine, "geometry":geometries}
        
        os.makedirs(os.path.join(self.path_output, "gouttieres", "batiments_fermes"), exist_ok=True)
        gdf = gpd.GeoDataFrame(d, crs="EPSG:2154")
        gdf.to_file(os.path.join(self.path_output, "gouttieres", "batiments_fermes", "batiments_fermes_amelioration_bd_topo.gpkg"))
    
    
    
    def export_intersections_ajustees(self):
        geometries = []
        nb_segments = []
        d_mean = []
        residus = []
        identifiant = []
        identifiant_bati = []

        for groupe_batiments in self.groupe_batiments:
            for groupe_segments in groupe_batiments.groupes_segments:
            
                if groupe_segments.is_valid():
                    
                    geometries.append(groupe_segments.get_geometrie())
                    nb_segments.append(groupe_segments.get_nb_segments())
                    d_mean.append(groupe_segments.get_d_mean())
                    residus.append(groupe_segments.get_residu_moyen())
                    identifiant.append(groupe_segments.get_identifiant())
                    identifiant_bati.append(groupe_batiments.get_identifiant())

        os.makedirs(os.path.join(self.path_output, "gouttieres", "batiments_fermes"), exist_ok=True)
        gdf = gpd.GeoDataFrame({"id":identifiant, "residus":residus, "d_mean":d_mean, "nb_segments":nb_segments, "id_bati":identifiant_bati, "geometry":geometries}, crs="EPSG:2154")
        gdf.to_file(os.path.join(self.path_output, "gouttieres", "batiments_fermes", "intersections.gpkg"))
        






if __name__=="__main__":
    parser = argparse.ArgumentParser(description="On calcule la position des goutières")
    parser.add_argument('--input', help='Répertoire où se trouve le chantier')
    parser.add_argument('--output', help='Répertoire où enregistrer les résultats')
    parser.add_argument('--emprise', help='Emprise au sol des zones où il faut reconstruire les bâtiments', default=None)
    parser.add_argument('--pompei', help='True si le chantier a été produit avec Pompei', default=False, type=bool)
    parser.add_argument('--bd_topo', help='Utilise les emprises de la BD TOPO', default=None, type=str)
    args = parser.parse_args()

    samonGouttiere =  SamonGouttiere(args.input, args.output, args.emprise, args.pompei, args.bd_topo)
    samonGouttiere.run()