from goutiereCalculee import GoutiereCalculee
from shapely import Point, MultiPoint, concave_hull
from typing import List
from troncon import Troncon
import numpy as np

class Batiment:

    def __init__(self, segments) -> None:
        self.segments:List[GoutiereCalculee] = segments

        self.troncons:List[Troncon] = []

        self.seuil_ps = 0.8


    def composantes_connexes(self):
        """
        On répartit les segments par composantes connexes.

        Cela permet de séparer les bâtiments lorsqu'il y en a deux qui ont le même identifiant
        """
        
        
        composantes_connexes = []
        segments = [s for s in self.segments]
        a_visiter = []
        # Tant que des segments n'ont pas été vus
        while len(segments) > 0:
            # Chaque itération dans cette première boucle while crée une composante connexe

            # On prend le premier élément de segments
            s0 = segments.pop()
            a_visiter.append(s0)
            composante_connexe = []

            # On s'arrête lorsqu'il n'y a plus d'éléments à visiter dans cette composante connexe
            while len(a_visiter) > 0:
                # On récupère le premier élément à visiter
                s1 = a_visiter.pop()
                # Si l'élément n'est pas fictif, on l'ajoute
                if not s1.fictive:
                    composante_connexe.append(s1)
                # On parcourt tous les voisins de l'élément
                for voisin in s1.voisins:
                    # Si le voisin n'a pas déjà été visité, alors on l'ajoute dans les objets à visiter
                    if voisin not in a_visiter and voisin not in composante_connexe and voisin in segments:
                        a_visiter.append(voisin)
                        segments.remove(voisin)
            
            # On ajoute la composante connexe
            composantes_connexes.append(composante_connexe)
        return composantes_connexes


    def methode_concave_hull(self):
        points = []
        for segment in self.segments:
            for voisin in segment.voisins:
                if not voisin.fictive:
                    intersection_x, intersection_y = segment.intersection(voisin)
                    z1 = segment.calcul_z(intersection_x)
                    z2 = voisin.calcul_z(intersection_x)
                    z_mean = (z1+z2)/2
                    intersection = Point(intersection_x, intersection_y, z_mean)
                    if intersection not in points:
                        points.append(intersection)
            
            if len(segment.voisins) == 1:
                voisin = segment.voisins[0]
                _, c2 = segment.p_proches(voisin)
                point = c2[0]
                if point not in points:
                    points.append(point)
            
        if len(points) > 2:
            multipoints = MultiPoint(points)

            polygon = concave_hull(multipoints, ratio=1.0)
            batiments_fermes = []

            for i in polygon.exterior.coords:
                batiments_fermes.append(Point(i[0], i[1], i[2]))
            self.batiments_fermes = [batiments_fermes]


    def point_plus_longue_chaine(self, t0):

        for t in self.troncons:
            t.compte = None
            t.precedents = []

        
        points = []
        if t0 is not None:
            
            # L'objectif est de trouver le chemin le plus long dans le graphe. le problème étant NP-Complet, il s'agit ici d'une bidouille
            # On va faire un parcourt de graphe, en commençant par t0 et en allant dans une seule direction depuis t0
            # compte indique le nombre d'étapes qu'il a fallu pour visiter le tronçon
            # precedents indique les segments par lesquels on est arrivé pour visiter le tronçon
            # L'idée sera de remonter le graphe en sens inverse : pour chaque tronçon, on remontera vers le celui de precedents avec la valeur compte la plus élevée
            t0.compte = 0
            t1 = t0.voisins[0]
            t1.compte = 1
            t1.precedents.append(t0)
            a_visiter = [t1]
            # On visite tous les tronçons
            while len(a_visiter) > 0:

                a_visiter = sorted(a_visiter, key=lambda item: 1000*len(item.voisins)-item.compte)

                t1 = a_visiter.pop(0)

                for voisin in t1.voisins:
                    if voisin not in t1.precedents:
                        if voisin.compte is None:
                            voisin.compte = t1.compte + 1
                            voisin.precedents.append(t1)
                            a_visiter.append(voisin)
                        else:
                            if voisin.compte < t1.compte:
                                voisin.precedents.append(t1)
        

            # On remonte
            segments = [t0]
            t1 = t0.remonter_0()
            t_1 = t0
            while t1 != t0 and t1 not in segments and t1 is not None:
                
                segments.append(t1)
                t2 = t1.remonter(t_1)
                t_1 = t1
                t1 = t2

            # On détermine tous les points qui délimitent le bâtiment
            
            if segments[1].has_point(segments[0].p1):
                points.append(segments[0].p2)
                points.append(segments[0].p1)
            else:
                points.append(segments[0].p1)
                points.append(segments[0].p2)
            for i in range(1, len(segments)):
                s = segments[i]
                p = s.autre_point(points[-1])
                points.append(p)
        return points


    def tentative_plus_longue_chaine(self):
        """
        Ferme le bâtiment en retrouvant la chaîne de segments la plus longue
        """

        # On calcule les points qui sont à toutes les intersections entre voisins 
        for segment in self.segments:
            for voisin in segment.voisins:
                ps = segment.produit_scalaire(voisin)
                if ps < 0.8:
                
                    intersection_x, intersection_y = segment.intersection(voisin)
                    z1 = segment.calcul_z(intersection_x)
                    z2 = voisin.calcul_z(intersection_x)
                    z_mean = (z1+z2)/2
                    intersection = Point(intersection_x, intersection_y, z_mean)

                    # On ajoute le point d'intersection à l'attribut intersections de segment et de voisin
                    segment.ajouter_intersection(intersection)
                    voisin.ajouter_intersection(intersection)

        # Pour chaque segment, on le découpe en tronçons
        for segment in self.segments:
            segment.decouper_troncons()

        # On rassemble tous les tronçons dans une seule liste
        for segment in self.segments:
            for troncon in segment.troncons:
                self.troncons.append(troncon)

        # Pour tous les tronçons, on complète leur attribut voisins
        for t1 in self.troncons:
            for t2 in self.troncons:
                if t1 != t2:
                    if t1.sont_voisins(t2):
                        t1.voisins.append(t2)

        
        # On prend au hasard un tronçon avec exactement deux voisins
        deux_voisins = self.get_troncon_deux_voisins()
        points_max = []
        for t0 in deux_voisins:
            points = self.point_plus_longue_chaine(t0)
            if len(points) > len(points_max):
                points_max = points
        self.batiments_fermes = [points_max]


    def verifier_coherence(self):
        seuil = 150
        incoherent = False
        points = self.batiments_fermes
        for i in range(1, len(points[0])):
            p1 = points[0][i-1]
            p2 = points[0][i]
            if p2 is None:
                incoherent = True
            else:
                d = np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)
                if d > seuil:
                    incoherent = True
        
        if incoherent:
            self.batiments_fermes = [[]]



        



    
    def get_troncon_deux_voisins(self):
        """
        Renvoie un tronçon avec exactement deux voisins
        """
        tab = []
        for t in self.troncons:
            if len(t.voisins) == 2:
                tab.append(t)
        return tab




    def cas_2_paralleles(self):
        """
        Gestion du cas où le bâtiment est constitué de deux segments parallèles.

        Alors on relie les deux extrémités des segments
        """

        # S'il y a uniquement deux segments
        if len(self.segments) == 2:

            # On vérifie que le produit scalaire est supérieur à un seuil (=les deux segments sont à peu près parallèles)
            s1 = self.segments[0]
            s2 = self.segments[1]
            if s1.produit_scalaire(s2) >= self.seuil_ps:
                # On construit deux nouveaux segments
                c1, c2 = s1.p_proches(s2)
                g0 = GoutiereCalculee(c1[0].x, c1[0].y, c1[0].z, c1[1].x, c1[1].y, c1[1].z, s1.id_bati, -1)
                g1 = GoutiereCalculee(c2[0].x, c2[0].y, c2[0].z, c2[1].x, c2[1].y, c2[1].z, s1.id_bati, -2)
                
                # On met à jour les id des voisins pour les segments
                s1.id_voisins = [-1,-2]
                s2.id_voisins = [-1,-2]
                g0.id_voisins = [s1.id_segment, s2.id_segment]
                g1.id_voisins = [s1.id_segment, s2.id_segment]
                
                # On ajoute les segments au batiment
                self.segments.append(g0)
                self.segments.append(g1)

    def get_p_oppose(self, c1, c2):
        """
        Renvoie le point constituant le dernier angle du bâtiment
        """
        x = c2[0].x + c2[1].x - c1[1].x
        y = c2[0].y + c2[1].y - c1[1].y
        z = c2[0].z + c2[1].z - c1[1].z
        return Point(x, y, z)

    def cas_2_perpendiculaires(self):
        """
        Gestion du cas où le bâtiment est constitué de deux segments perpendiculaires.

        Alors on copie un des murs présents sur le côté opposé et on ferme le bâtiment
        """
        
        # S'il y a uniquement deux segments
        if len(self.segments) == 2:

            # On vérifie que le produit scalaire est inférieur à un seuil (=les deux segments sont à peu près perpendiculaires)
            s1 = self.segments[0]
            s2 = self.segments[1]
            if s1.produit_scalaire(s2) <= 0.1:
                # On construit les deux nouveaux segments
                c1, c2 = s1.p_proches(s2)
                p_oppose = self.get_p_oppose(c1, c2)
                g0 = GoutiereCalculee(c2[0].x, c2[0].y, c2[0].z, p_oppose.x, p_oppose.y, p_oppose.z, s1.id_bati, -1)
                g1 = GoutiereCalculee(c2[1].x, c2[1].y, c2[1].z, p_oppose.x, p_oppose.y, p_oppose.z, s1.id_bati, -2)
                
                # On met à jour les id des voisins pour les segments
                s1.id_voisins = [-1, s2.id_segment]
                s2.id_voisins = [s1.id_segment,-2]
                g0.id_voisins = [s1.id_segment, -2]
                g1.id_voisins = [-1, s2.id_segment]
                
                # On ajoute les segments au batiment
                self.segments.append(g0)
                self.segments.append(g1)

    
    def get_segment_with_2_voisins(self, s1, s2, s3):
        """
        Renvoie s_base, s0, s1 avec s_base le segment qui a pour voisin s0 et s1, et qui est à peu près perpendiculaire à s0 et à s1
        """
        if s2.id_segment in s1.id_voisins and s3.id_segment in s1.id_voisins:
            if s2.produit_scalaire(s1) < 0.2 and s3.produit_scalaire(s1) < 0.2:
                return s1, s2, s3
        if s1.id_segment in s2.id_voisins and s3.id_segment in s2.id_voisins:
            if s2.produit_scalaire(s1) < 0.2 and s3.produit_scalaire(s2) < 0.2:
                return s2, s1, s3
        if s2.id_segment in s3.id_voisins and s1.id_segment in s3.id_voisins:
            if s2.produit_scalaire(s3) < 0.2 and s3.produit_scalaire(s1) < 0.2:
                return s3, s2, s1
        return None, None, None


    def cas_3_segments(self):
        """
        Gestion du cas où le bâtiment est constitué de trois segments perpendiculaires les uns par rapport aux autres.
        """
        # S'il y a uniquement trois segments
        if len(self.segments) == 3:
            # On récupère les trois segments
            s1 = self.segments[0]
            s2 = self.segments[1]
            s3 = self.segments[2]

            # On détermine s_base, le segment parmi les trois qui a les deux autres pour voisins
            s_base, s0, s1 = self.get_segment_with_2_voisins(s1, s2, s3)
            if s_base is not None:

                # On construit le nouveau segment
                _, c2 = s_base.p_proches(s0)
                _, c4 = s_base.p_proches(s1)
                g0 = GoutiereCalculee(c2[1].x, c2[1].y, c2[1].z, c4[1].x, c4[1].y, c4[1].z, s1.id_bati, -1)
                
                # On met à jour les id des voisins pour les segments
                g0.id_voisins = [s0.id_segment, s1.id_segment]
                s0.id_voisins = [-1, s_base.id_segment]
                s1.id_voisins = [s_base.id_segment,-1]

                # On ajoute le segment au batiment
                self.segments.append(g0)

           


    def get_id(self):
        return self.segments[0].id_bati


    def completer_voisins(self):
        """
        Pour chaque segment, on ajoute les segments voisins dans son attribut voisins

        On crée des segments fictifs dans le cas où l'objet GoutiereCalculee n'existe pas déjà
        """

        # On parcourt tous les segments
        for goutiereCalculee in self.segments:
            # Si le segment n'a pas le statut supprime
            if not goutiereCalculee.supprime:
                # On parcourt les id des voisins
                for id_voisin in goutiereCalculee.id_voisins:
                    # On récupère l'objet GoutiereCalculee ayant l'id id_voisin
                    voisin = self.get_voisin(id_voisin)
                    
                    
                    if voisin is not None:
                        # On met à jour les voisins
                        if not voisin.supprime:
                            if voisin not in goutiereCalculee.voisins:
                                goutiereCalculee.voisins.append(voisin)
                            if goutiereCalculee not in voisin.voisins:
                                voisin.voisins.append(goutiereCalculee)

                            
    def get_voisin(self, id_voisin):
        """
        Récupère le segment ayant pour id id_voisin
        """
        for goutiere in self.segments:
            if goutiere.id_segment == id_voisin:
                return goutiere
        return None

    
    def supprimer_segment_un_seul_voisin(self):
        """
        Marque comme supprimé tous les segments avec strictement moins de deux voisins
        """
        for segment in self.segments:
            if len(segment.voisins) < 2:    
                segment.supprime = True


    def supprimer_segment_zero_voisin(self):
        """
        Marque comme supprimé tous les segments avec strictement moins de deux voisins
        """
        for segment in self.segments:
            if len(segment.voisins) == 0:    
                segment.supprime = True

    def initialiser_voisins(self):
        """
        Met une liste vide pour l'attribut voisins de tous les segments
        """
        for segment in self.segments:
            segment.voisins = []


    def mise_a_jour_segments_fictifs(self):
        """
        Met à jour les extrémités de tous les segments fictifs
        """
        for segment in self.segments:
            if segment.fictive:
                segment.mettre_a_jour_extremites()


    def supprimer_fictif_doublons(self):
        """
        Si deux segments fictifs sont en doublon (ils ont les mêmes voisins), alors on en supprime un des deux
        """
        for segment_fictif in self.segments:
            if segment_fictif.fictive and not segment_fictif.supprime:
                v1 = segment_fictif.voisins[0]
                v2 = segment_fictif.voisins[1]
                a_supprimer = False
                for s in self.segments:
                    if s != segment_fictif:
                        if v1 in s.voisins and v2 in s.voisins:
                            a_supprimer = True
                if a_supprimer:
                    segment_fictif.supprime = True

    def fermer_batiment(self):
        """
        On essaye de fermer le bâtiment
        Cette méthode ne fonctionne que si tous les segments ont exactement deux voisins 
        """
        batiments_fermes = []
        # On vérifie que tous les segments ont exactement deux voisins
        if self.seulement_2_voisins():

            # On ordonne les segments de façon à avoir une chaîne continue
            segments_ordonnes, erreur_geometrie = self.ordonner_segments_v2()

            # S'il n'ya pas d'erreur de géométrie
            if not erreur_geometrie:
                # On calcule les intersections entre les segments consécutifs
                liste_points = self.calculer_intersection(segments_ordonnes)
                batiments_fermes.append(liste_points)
        self.batiments_fermes = batiments_fermes



    def tentative_relier_extremite(self):
        """
        On se place dans le cas où on considère qu'il y a des segments qui n'ont qu'un seul voisin
        """
        
        # On revoie la politique de suppression des segments
        for segment in self.segments:
            segment.supprime = False

        # On complète les segments 
        self.completer_voisins()


        # On parcourt les segments
        for segment in self.segments:
            # On supprime tous les segments fictifs avec strictement moins de deux voisins
            if segment.fictive and len(segment.voisins) < 2:
                segment.supprime = True
        
        # On recherche les extrémités (les segments avec un seul voisin)
        extremites = []
        for segment in self.segments:
            if not segment.supprime and segment.nb_voisins_non_supprimes() == 1:
                extremites.append(segment)
        
        # Si l'on a exactement deux extrémités
        if len(extremites) == 2:
            s0 = extremites[0]
            s1 = extremites[1]

            # On ajoute la goutière qui relie les deux extrémités
            v0 = s0.get_voisins_non_supprime()
            _, c2 = s0.p_proches(v0)

            v1 = s1.get_voisins_non_supprime()
            _, c4 = s1.p_proches(v1)

            g0 = GoutiereCalculee(c2[0].x, c2[0].y, c2[0].z, c4[0].x, c4[0].y, c4[0].z, s1.id_bati, -1)
            s0.id_voisins.append(-1)
            s1.id_voisins.append(-1)
            g0.id_voisins = [s0.id_segment, s1.id_segment]

            # On essaye de refermer le bâtiment selon la première méthode
            self.fermer_batiment()


    def seulement_2_voisins(self):
        """
        On vérifie que tous les segments non supprimés ont exactement deux voisins
        """
        for segment in self.segments:
            if len(segment.voisins) != 2 and not segment.supprime:
                return False
        return True

    def ordonner_segments_v2(self):
        """
        Ordonne les segments de façon à avoir une chaîne continue

        On est dans le cas où tous les segments ont exactement deux voisins
        """
        
        # On met dans une liste tous les bâtiments non supprimés
        bati_bis = []
        for segment in self.segments:
            if not segment.supprime:
                bati_bis.append(segment)

        # Il faut au moins deux segments
        if len(bati_bis) <= 1:
            return [], True

        # On récupère le premier segment
        s1 = bati_bis.pop()
        liste_ordonnee = [s1]
        v1 = s1.voisins[0]

        # Il y a une erreur de géométrie si les segments ne forment pas une chaîne (ie tous les segments doivent être dans la chaîne qui doit revenir à son point de départ)
        erreur_geometrie = False
        while len(bati_bis) > 0 and not erreur_geometrie:
            # On récupère les autres voisins de v1
            autres_voisins = v1.autre_voisin(s1)
            #v1 devient s1
            s1 = v1
            # Si s1 n'est pas dans la liste des segments restants, alors il y a une erreur de géométrie
            if s1 not in bati_bis:
                return [], True
            # On ajoute s1 à la liste ordonnée
            bati_bis.remove(s1)
            liste_ordonnee.append(s1)

            # v1 est l'autre voisin de s1
            v1 = autres_voisins[0]
        return liste_ordonnee, erreur_geometrie

    
    def calculer_intersection(self, segments_ordonnes):
        """
        Calcule les intersections entre les segments consécutifs
        """
        #On ajoute le premier segment segment à la fin de la liste ordonnée
        segments_ordonnes.append(segments_ordonnes[0])
        liste_points = []

        # On parcourt tous les couples de points
        for i in range(len(segments_ordonnes)-1):
            s1 = segments_ordonnes[i]
            s2 = segments_ordonnes[i+1]
            ps = s1.produit_scalaire(s2)
            # Si le produit scalaire est inférieure à un certain seuil, on calcule l'intersection entre les deux segments
            if ps < self.seuil_ps:
                x_intersec, y_intersec = s1.intersection(s2)
                z1 = s1.calcul_z(x_intersec)
                z2 = s2.calcul_z(x_intersec)
                z_mean = (z1+z2)/2
                liste_points.append(Point(x_intersec, y_intersec, z_mean))
            # S'il est supérieur à un certain seuil, alors il s'agit sans doute de deux murs parallèles et il manque alors un mur
            else:
                p1, p2 = s1.p_proches(s2)[0]
                liste_points.append(p1)
                liste_points.append(p2)
        liste_points.append(liste_points[0])
        return liste_points


    def ajuster_intersection(self):
        for segment in self.segments:
            for voisin in segment.voisins:
                ps = segment.produit_scalaire(voisin)
                if self.get_id()==277:
                    print()
                    print(ps, segment.id_segment, voisin.id_segment)
                    print(np.linalg.norm(segment.u), np.linalg.norm(voisin.u))
                    print("segment.u : ", segment.u)
                    print("voisin.u : ", voisin.u)
                if ps < 0.8:
                    intersection_x, intersection_y = segment.intersection(voisin)
                    z1 = segment.calcul_z(intersection_x)
                    z2 = voisin.calcul_z(intersection_x)
                    z_mean = (z1+z2)/2
                    if not np.isnan(z_mean):
                        intersection = Point(intersection_x, intersection_y, z_mean)
                        # On ajoute le point d'intersection à l'attribut intersections de segment et de voisin
                        segment.ajouter_intersection(intersection)
                        voisin.ajouter_intersection(intersection)

        for segment in self.segments:
            if len(segment.intersections)==1:
                i = segment.intersections[0]
                d1 = segment.distance_point(segment.p1, i)
                d2 = segment.distance_point(segment.p2, i)
                if d1 < d2:
                    segment.p1 = i
                else:
                    segment.p2 = i
                segment.calcule_a_b()
            
            elif len(segment.intersections)==2:
                i1 = segment.intersections[0]
                i2 = segment.intersections[1]

                c1, c2 = segment.p_proches_points(i1, i2)
                segment.p1 = c1[1]
                segment.p2 = c2[1]
                segment.calcule_a_b()

            elif len(segment.intersections)>2:
                couples = [[i, j] for i in range(len(segment.intersections)) for j in range(i, len(segment.intersections)) if i!=j ]
                i1 = segment.intersections[0]
                i2 = segment.intersections[1]

                c1, c2 = segment.p_proches_points(i1, i2)
                segment.p1 = c1[1]
                segment.p2 = c2[1]
                segment.calcule_a_b()

                del(couples[0])

                for couple in couples:
                    p1 = segment.intersections[couple[0]]
                    p2 = segment.intersections[couple[1]]
                    nouvelle_gouttiere = GoutiereCalculee(p1.x, p1.y, p1.z, p2.x, p2.y, p2.z, segment.id_bati, 0)
                    self.segments.append(nouvelle_gouttiere)



