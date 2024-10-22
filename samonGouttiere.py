import argparse
import os
from v2.shot import MNT, RAF, Shot
from v2.prediction import Prediction
from typing import List
from lxml import etree
from v2.association_batiment_engine import AssociationBatimentEngine

class SamonGouttiere:

    def __init__(self, path_chantier:str):
        
        # Chemin où se trouve le chantier
        if not os.path.isdir(path_chantier):
            return ValueError(f"{path_chantier} n'est pas un répertoire")
        self.path_chantier = path_chantier

        self.mnt:MNT = None
        self.raf:RAF = None
        self.shots:List[Shot] = []
        self.predictions:List[Prediction] = []

    
    def get_mnt_path(self) -> str:
        """
        Renvoie le chemin vers le mnt
        """
        path = os.path.join(self.path_chantier, "mnt", "mnt.vrt")
        if not os.path.isfile(path):
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
        predictions = [i for i in os.listdir(self.get_predictions_ffl_dir()) if i[-4:]==".shp"]
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
            return ValueError(f"Il ne faut qu'un seul fichier orientation dans {dir_path}")
        return os.path.join(dir_path, files[0])


    def get_shots(self, predictions_ffl:List[str]) -> List[Shot]:
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
            
            focal = root.find(".//focal")
            focale_x = float(focal.find(".//x").text)
            focale_y = float(focal.find(".//y").text)
            focale_z = float(focal.find(".//z").text)
            focale = [focale_x, focale_y, focale_z]
            
            for cliche in vol.getiterator("cliche"):
                image = cliche.find("image").text.strip()
                if image in pvas:
                    shot = Shot.createShot(cliche, focale, self.raf, centre_rep_local)
                    shots.append(shot)
        return shots

    

    def run(self):
        self.load()
        self.lisser_geometries()
        self.association_bati()



    def load(self):
        """
        Charge les données
        """
        self.mnt = MNT(self.get_mnt_path())
        self.raf = RAF(self.get_raf_path())
        predictions_ffl = self.get_predictions_ffl()
        self.shots = self.get_shots(predictions_ffl)

        
        predictions = []
        for prediction_ffl in predictions_ffl:
            for shot in self.shots:
                if shot.image+".shp" == prediction_ffl:
                    predictions.append(Prediction(shot, os.path.join(self.get_predictions_ffl_dir(), prediction_ffl), self.mnt))
        self.predictions = predictions


    def lisser_geometries(self):
        """
        Lisse les géométries de chaque polygones
        """
        
        print("Lissage de la géométrie")
        os.makedirs(os.path.join(self.path_chantier, "gouttieres", "nettoyage"), exist_ok=True)
        for prediction in self.predictions:
            prediction.lisser_geometries()
            prediction.export_geometry_image(os.path.join(self.path_chantier, "gouttieres", "nettoyage"))


    def association_bati(self):
        """
        Associer les bâtiments entre eux
        """
        association_batiments_engine = AssociationBatimentEngine(self.predictions)
        association_batiments_engine.run()

        os.makedirs(os.path.join(self.path_chantier, "gouttieres", "association_batiment"), exist_ok=True)
        for prediction in self.predictions:
            prediction.export_geometry_terrain(os.path.join(self.path_chantier, "gouttieres", "association_batiment"))






if __name__=="__main__":
    parser = argparse.ArgumentParser(description="On calcule la position des goutières")
    parser.add_argument('--input', help='Répertoire où se trouvent les résultats de association_segments')
    args = parser.parse_args()

    samonGouttiere =  SamonGouttiere(args.input)
    samonGouttiere.run()