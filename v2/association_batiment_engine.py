from typing import List
from v2.prediction import Prediction
from tqdm import tqdm
import geopandas as gpd
from v2.groupe_batiments import GroupeBatiments
from v2.groupe_pate_maisons import GroupePatesMaisons
import numpy as np
from v2.batiment import Batiment
from v2.shot import MNT, RAF, Shot
from v2.parallelisation import compute_ground_geometrie, compute_estim_z, compute_batiment_association
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

class AssociationBatimentEngine:

    """
    Algorithme pour associer les bâtiments entre eux
    """

    def __init__(self, groupes_pates_maisons:List[GroupePatesMaisons], emprise:gpd.GeoDataFrame, pompei:bool, nb_cpus:int, pva_path:str, mnt:MNT, raf:RAF, shots:List[Shot]):
        self.groupes_pates_maisons:List[GroupePatesMaisons] = groupes_pates_maisons

        self.groupe_batiments:List[GroupeBatiments] = None

        self.emprise = emprise

        self.pompei = pompei

        self.nb_cpus = nb_cpus

        self.pva_path = pva_path
        self.mnt = mnt
        self.raf = raf
        self.shots = shots



    def run(self)->List[GroupeBatiments]:

        cs = int(len(self.groupes_pates_maisons)/(10*self.nb_cpus)+1)
            
        with multiprocessing.Pool(processes=self.nb_cpus) as pool:
            results = list(tqdm(
            pool.imap_unordered(compute_ground_geometrie, self.groupes_pates_maisons, chunksize=cs), 
            total=len(self.groupes_pates_maisons),
            desc="Calcul des géométries terrain"
        ))
        self.groupes_pates_maisons = results

        if self.emprise is not None:
            print("On ne conserve que les bâtiments à l'intérieur de l'emprise")
            for gpm in tqdm(self.groupes_pates_maisons):
                gpm.check_in_emprise(self.emprise)

        
        # Pour chaque prédictions du FFL, on crée des tableaux numpy qui permettront d'accélérer le calcul pour associer des bâtiments
        for gpm in tqdm(self.groupes_pates_maisons, desc="Calcul des géoséries"):
            gpm.create_geodataframe()

        # Pour chaque bâtiment, on cherche sur les autres prédictions le bâtiment avec lequel il se superpose le plus
        self.association()

        batiments = [None for i in range(Batiment.identifiant_global+1)]
        for gpm in self.groupes_pates_maisons:
            for pm in gpm.pates_maisons:
                for batiment in pm.batiments:
                    if batiments[batiment.identifiant] is None:
                        batiments[batiment.identifiant] = batiment
                    else:
                        batiment0 = batiments[batiment.identifiant]
                        for homologue_id in batiment.get_homologues():
                            if homologue_id not in batiment0.get_homologues():
                                batiment0.add_homologue(homologue_id)
        
        for batiment in batiments:
            if batiment is None:
                continue
            new_homologues = []
            for homologue_id in batiment.get_homologues():
                new_homologues.append(batiments[homologue_id])
            batiment.batiments_homologues = new_homologues

        # On crée le graphe connexe qui regroupe tous les bâtiments qui ont été associés
        self.groupe_batiments = self.graphe_connexe()

        print("Calcul du z moyen du bâtiment")
        # On calcule une estimation de la hauteur du bâtiment
        self.compute_z_mean()

        return self.groupe_batiments
   

    def init(self):
        self.groupe_batiments = []
        
        for prediction in tqdm(self.predictions):
            prediction.delete_homol()


    def association(self):
        cs = int(len(self.groupes_pates_maisons)/(10*self.nb_cpus)+1)
        with multiprocessing.Pool(processes=self.nb_cpus) as pool:
            results = list(tqdm(
            pool.imap_unordered(compute_batiment_association, self.groupes_pates_maisons, chunksize=cs), 
            total=len(self.groupes_pates_maisons),
            desc="Calcul des associations de batiments"
        ))        
        self.groupes_pates_maisons = results


    def graphe_connexe(self)->List[GroupeBatiments]:
        """
        On réunit tous les bâtiments qui représentent un même bâtiment dans la réalité
        """
        groupe_batiments = []
        for gpm in self.groupes_pates_maisons:
            for pm in gpm.pates_maisons:
                for bati in pm.batiments:
                    if not bati._marque:
                        batis = [bati]
                        liste = [bati]
                        bati._marque = True

                        while len(liste) > 0:
                            b = liste.pop()
                            for homologue in b.get_homologues():
                                if not homologue._marque:
                                    homologue._marque = True
                                    if homologue not in liste:
                                        batis.append(homologue)
                                        liste.append(homologue)

                        if len(batis)>1:
                            groupe_batiments.append(GroupeBatiments(batis, self.pva_path, self.mnt, self.raf, self.shots, self.pompei))
        
        return groupe_batiments
    
    def get_mnt(self)->MNT:
        return self.predictions[0].mnt
    

    def compute_z_mean(self):
        """
        On calcule le z moyen de chaque groupe de bâtiment, et on met à jour la projection au sol des bâtiments
        """

        cs = int(len(self.groupe_batiments)/(10*self.nb_cpus)+1)
            
        with multiprocessing.Pool(processes=self.nb_cpus) as pool:
            results = list(tqdm(
            pool.imap_unordered(compute_estim_z, self.groupe_batiments, chunksize=cs), 
            total=len(self.groupe_batiments),
            desc="Estimation des hauteurs de bâtiment"
        ))

        self.groupe_batiments = results

        statistiques = {
            "Barycentre":0,
            "Points":0,
            "Samon":0,
            "Echec":0
        }

        for groupe in tqdm(self.groupe_batiments):
            statistiques[groupe.get_methode_estimation_hauteur()] += 1
            
        print("Méthode utilisée pour estimer la hauteur des bâtiments")
        for key, value in statistiques.items():
            print(f"{key} : {value}")

