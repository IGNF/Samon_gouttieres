from typing import List
from v2.prediction import Prediction
from tqdm import tqdm
import geopandas as gpd
from v2.groupe_pate_maisons import GroupePatesMaisons
from v2.parallelisation import compute_pate_maison_ground_geometrie
from v2.pateMaison import PateMaison
import multiprocessing

class AssociationPateMaisonEngine:

    """
    Algorithme pour associer les bâtiments entre eux
    """

    def __init__(self, predictions:List[Prediction], emprise:gpd.GeoDataFrame, nb_cpus:int):
        self.predictions:List[Prediction] = predictions
        self.groupe_pates_maisons:List[GroupePatesMaisons] = None
        self.emprise = emprise
        self.nb_cpus = nb_cpus




    def run(self)->List[GroupePatesMaisons]:

        cs = int(len(self.predictions)/(10*self.nb_cpus)+1)
            
        with multiprocessing.Pool(processes=self.nb_cpus) as pool:
            results = list(tqdm(
            pool.imap_unordered(compute_pate_maison_ground_geometrie, self.predictions, chunksize=cs), 
            total=len(self.predictions),
            desc="Calcul des géométries terrain"
        ))        
        self.predictions = results

        if self.emprise is not None:
            for prediction in tqdm(self.predictions, desc="Filtrage des pâtés de maisons par emprise terrain"):
                prediction.check_in_emprise_pate_maisons(self.emprise)

        
        # Pour chaque prédictions du FFL, on crée des tableaux numpy qui permettront d'accélérer le calcul pour associer des bâtiments
        for prediction in tqdm(self.predictions, desc="Calcul des géoséries"):
            prediction.create_geodataframe_pates_maisons()

        # Pour chaque bâtiment, on cherche sur les autres prédictions le bâtiment avec lequel il se superpose le plus
        self.association()
        pms = [None for i in range(PateMaison.identifiant_global+1)]
        for prediction in self.predictions:
            for pm in prediction.pates_maisons:
                if pms[pm.identifiant] is None:
                    pms[pm.identifiant] = pm
                else:
                    pm0 = pms[pm.identifiant]
                    for homologue_id in pm.get_homologues():
                        if homologue_id not in pm0.get_homologues():
                            pm0.add_homologue(homologue_id)
        
        for pm in pms:
            if pm is None:
                continue
            new_homologues = []
            for homologue_id in pm.get_homologues():
                new_homologues.append(pms[homologue_id])
            pm.homologues = new_homologues

        for prediction in self.predictions:
            new_pm = []
            for pm in prediction.pates_maisons:
                new_pm.append(pms[pm.identifiant])
            prediction.pates_maisons = new_pm
            


        # On crée le graphe connexe qui regroupe tous les bâtiments qui ont été associés
        self.groupes_pates_maisons = self.graphe_connexe()

        for gpm in self.groupes_pates_maisons:
            for pm in gpm.pates_maisons:
                pm.homologues = []

        return self.groupes_pates_maisons, self.predictions
   

    def init(self):
        self.groupe_batiments = []
        for prediction in tqdm(self.predictions):
            prediction.delete_homol()



    def association(self):

        for p1 in tqdm(self.predictions, desc="Appariement des pâtés de maisons"):
            for p2 in self.predictions:
                if p1==p2:
                    continue
                if p1.shot.emprise.intersects(p2.shot.emprise):
                    p1.association_pates_maisons(p2)


    def graphe_connexe(self)->List[GroupePatesMaisons]:
        """
        On réunit tous les bâtiments qui représentent un même bâtiment dans la réalité
        """
        groupe_pates_maisons = []
        for prediction in self.predictions:
            for pm in prediction.get_pates_maisons():
                if not pm._marque:
                    pms = [pm]
                    liste = [pm]
                    pm._marque = True

                    while len(liste) > 0:
                        b = liste.pop()
                        for homologue in b.get_homologues():
                            if not homologue._marque:
                                homologue._marque = True
                                if homologue not in liste:
                                    pms.append(homologue)
                                    liste.append(homologue)

                    groupe_pates_maisons.append(GroupePatesMaisons(pms))
        
        return groupe_pates_maisons

