from typing import List, Dict
from v2.groupe_batiments import GroupeBatiments
from v2.batiment import Batiment
from tqdm import tqdm
import numpy as np
from v2.segments import Segment
import statistics
from v2.groupe_segments import GroupeSegments
from shapely import Point

class AssociationSegmentsEngine:

    seuil_ps:float = 0.98
    seuil_distance_droite_1:float = 1.5
    seuil_distance_droite_2:float = 1

    def __init__(self, groupes_batiments:List[GroupeBatiments]):
        self.groupes_batiments:List[GroupeBatiments] = groupes_batiments
        self.groupes_segments:List[GroupeSegments] = []


    def run(self):
        print("Création des segments pour chaque batiment")
        # pour chaque bâtiment, on crée un objet Segment pour chaque côté du polygone
        for groupe_batiment in tqdm(self.groupes_batiments):
            groupe_batiment.create_segments()

        print("On associe les segments qui représentent le même bord de toit")
        self.association()
        return self.groupes_segments


    def association(self):
        """
        Effectue l'association entre les segments appartenant à un même groupe de bâtiments
        """
        # On parcourt les groupes de bâtiments
        for groupe_batiment in tqdm(self.groupes_batiments):
            batiments = groupe_batiment.get_batiments()
            # Il faut au moins deux bâtiments dans le groupe de bâtiments
            if len(batiments) >= 2:
                # on parcourt les paires de bâtiments
                for bati_1 in batiments:
                    for bati_2 in batiments:
                        # Il faut que la projection au sol des deux bâtiments se recouvre suffisamment (IoU > 0.5)
                        if bati_1.get_image()!=bati_2.get_image() and bati_1.compute_iou(bati_2)>0.5:
                            
                            # On effectue un premier appariement grossier
                            self.premier_appariement(bati_1, bati_2)
                            self.premier_appariement(bati_2, bati_1)
                            # On recherche les composantes connexes
                            composantes_connexes = self.composante_connexe(bati_1)

                            # On calcule la translation médiane entre les deux bâtiments
                            dx, dy = self.calculer_translation(composantes_connexes)

                            self.demarque_goutieres(bati_1)
                            self.demarque_goutieres(bati_2)

                            # On effectue un deuxième appariement plus fin, en tenant compte de la translation
                            self.deuxieme_appariement(bati_1, bati_2, dx, dy)
                            self.deuxieme_appariement(bati_2, bati_1, dx, dy)

                            self.demarque_goutieres(bati_1)
                            self.demarque_goutieres(bati_2)
                # On récupère les composantes connexes pour tous les segments du groupe
                self.composante_connexe_bati(groupe_batiment)


    def premier_appariement(self, b1:Batiment, b2:Batiment):
        """
        Premier appariement grossier
        """
        for segment in b1.get_segments():
            u1 = segment.u_directeur_world().reshape((1, 2))
            barycentre_1 = segment.barycentre_world().reshape((1, 2))
            
            # On calcule le produit scalaire
            u = b2.u
            ps = np.abs(np.sum(u1* u, axis=1))

            # On calcule la distance du barycentre à la droite
            equation_droite = b2.equation_droite
            d_droite = np.abs(equation_droite[:,0]*barycentre_1[0,0] + equation_droite[:,1]*barycentre_1[0,1] + equation_droite[:,2]) / equation_droite[:,3]

            # Calcule de la distance entre les deux barycentres 
            barycentre = b2.barycentre
            d_max = b2.d_max
            distance = np.sqrt(np.sum((barycentre - barycentre_1)**2, axis=1))

            condition = np.where(np.logical_and(np.logical_and(ps > AssociationSegmentsEngine.seuil_ps, d_droite <AssociationSegmentsEngine.seuil_distance_droite_1), distance < d_max))
                    
            if condition[0].shape[0] != 0:

                # Parmi les goutières qui restent, on prend celle pour laquelle la distance entre les deux barycentres est la plus petite
                barycentre_filtre_ps = barycentre[condition, :].squeeze()
                distance = np.sqrt(np.sum((barycentre_filtre_ps - barycentre_1)**2, axis=1))
                segment_homologue = b2.get_segment_i(condition[0][np.argmin(distance)])

                segment_homologue.add_homologue_1(segment)
                segment.add_homologue_1(segment_homologue)

    
    def deuxieme_appariement(self, b1:Batiment, b2:Batiment, dx:float, dy:float):
        """
        Deuxième appariement plus fin
        """
        b2.create_numpy_array(dx=dx, dy=dy)
        
        for segment in b1.get_segments():
            u1 = segment.u_directeur_world().reshape((1, 2))
            barycentre_1 = segment.barycentre_world().reshape((1, 2))
            
            # On calcule le produit scalaire
            u = b2.u
            ps = np.abs(np.sum(u1* u, axis=1))

            # On calcule la distance du barycentre à la droite
            equation_droite = b2.equation_droite
            d_droite = np.abs(equation_droite[:,0]*barycentre_1[0,0] + equation_droite[:,1]*barycentre_1[0,1] + equation_droite[:,2]) / equation_droite[:,3]

            # Calcule de la distance entre les deux barycentres 
            barycentre = b2.barycentre
            d_max = b2.d_max
            distance = np.sqrt(np.sum((barycentre - barycentre_1)**2, axis=1))

            condition = np.where(np.logical_and(np.logical_and(ps > AssociationSegmentsEngine.seuil_ps, d_droite <AssociationSegmentsEngine.seuil_distance_droite_2), distance < d_max))
                    
            if condition[0].shape[0] != 0:

                # Parmi les goutières qui restent, on prend celle pour laquelle la distance entre les deux barycentres est la plus petite
                barycentre_filtre_ps = barycentre[condition, :].squeeze()
                distance = np.sqrt(np.sum((barycentre_filtre_ps - barycentre_1)**2, axis=1))
                segment_homologue = b2.get_segment_i(condition[0][np.argmin(distance)])

                segment_homologue.add_homologue_2(segment)
                segment.add_homologue_2(segment_homologue)

    
    
    def composante_connexe(self, b1:Batiment)->List[List[Segment]]:
        """
        On récupère les composantes connexes pour chaque segment sur la relation : le segment est homologue avec cet autre segment
        """
        composantes_connexes:List[List[Segment]] = []
        for segment in b1.get_segments():
            if not segment._marque:
                liste_connexe = [segment]
                liste:List[Segment] = [segment]
                segment._marque = True
                while len(liste) > 0:
                    g = liste.pop()

                    
                    l = g.segments_homologues_1
                    for homologue in l:
                        if not homologue._marque:
                            homologue._marque = True
                            if homologue not in liste:
                                liste.append(homologue)
                            if homologue not in liste_connexe:
                                liste_connexe.append(homologue)
                
                if len(liste_connexe) >= 2:
                    composantes_connexes.append(liste_connexe)
        
        return composantes_connexes
    

    def segments_meme_taille(self, composante_connexe:List[Segment])->List[Segment]:
        """
        On récupère les deux segments qui ont la taille la plus proche 
        """
        dictionnaire:Dict[str,List[Segment]] = {}
        for segment in composante_connexe:
            if segment.get_image() not in dictionnaire.keys():
                dictionnaire[segment.get_image()] = [segment]
            else:
                dictionnaire[segment.get_image()].append(segment)
            
        if len(dictionnaire.keys()) != 2:
            print("Erreur dictionnaire : ", dictionnaire)
            return None   
        distance_minimale = 2
        couple_minimal = None
        for b in list(dictionnaire.values())[1]:
            for g in list(dictionnaire.values())[0]:
                difference = abs(b.get_longueur() - g.get_longueur())
                if difference < distance_minimale:
                    distance_minimale = difference
                    couple_minimal = [g, b]
        return couple_minimal
    
    def distance(self, P0:Point, P1:Point):
        return np.sqrt((P0.x - P1.x)**2 + (P0.y - P1.y)**2)
    

    def calculer_translation(self, composantes_connexes:List[List[Segment]]):
        """
        Calcule une translation à appliquer entre deux bâtiments à partir des segments appariés
        """
        liste_dx = []
        liste_dy = []
        for composante_connexe in composantes_connexes:
            # Si on a au moins trois segments, alors on prend les deux segments qui ont la taille plus proche
            # On modifie alors la composante connexe pour avoir exactement deux segments
            if len(composante_connexe) >= 3:
                composante_connexe_temp = self.segments_meme_taille(composante_connexe)
                if composante_connexe_temp is not None:
                    composante_connexe = composante_connexe_temp
            # Si on n'a que deux segments, alors on prend ces deux segments 
            if len(composante_connexe) == 2:
                g0 = composante_connexe[0]
                g1 = composante_connexe[1]
                # S'ils ont presque la même longueur (+/- 2 mètres)
                if abs(g0.get_longueur()-g1.get_longueur()) < 2:
                    P0 = g0.P0_sol()
                    P1 = g0.P1_sol()

                    # On calcule la distance dx, dy entre ces deux segments
                    if self.distance(P0, g1.P0_sol()) < self.distance(P0, g1.P1_sol()):
                        liste_dx.append(g1.P0_sol().x - P0.x)
                        liste_dx.append(g1.P1_sol().x - P1.x)
                        liste_dy.append(g1.P0_sol().y - P0.y)
                        liste_dy.append(g1.P1_sol().y - P1.y)
                    else:
                        liste_dx.append(g1.P0_sol().x - P1.x)
                        liste_dx.append(g1.P1_sol().x - P0.x)
                        liste_dy.append(g1.P0_sol().y - P1.y)
                        liste_dy.append(g1.P1_sol().y - P0.y)

        if len(liste_dx) == 0:
            dx = 0
            dy = 0
        else:
            # On prend la médiane des (dx,dy) pour être moins sensible au bruit
            dx = statistics.median(liste_dx)
            dy = statistics.median(liste_dy)
        return dx, dy
    

    def demarque_goutieres(self, bati:Batiment):
        for segment in bati.get_segments():
            segment._marque = False
            segment.segments_homologues_1 = []


    def composante_connexe_bati(self, groupe_batiment:GroupeBatiments):
        """
        Calcule les composantes connexes au niveau du bati
        """
        for batiment in groupe_batiment.get_batiments():
            for segment in batiment.get_segments():
                if not segment._marque:
                    liste_connexe = [segment]
                    liste = [segment]
                    segment._marque = True
                    while len(liste) > 0:
                        g = liste.pop()
                        for homologue in g.segments_homologues_2:
                            if not homologue._marque:
                                homologue._marque = True
                                if homologue not in liste:
                                    liste.append(homologue)
                                if homologue not in liste_connexe:
                                    liste_connexe.append(homologue)
                    
                    if len(liste_connexe) >= 2:
                        groupe_segments = GroupeSegments(liste_connexe)
                        self.groupes_segments.append(groupe_segments)
