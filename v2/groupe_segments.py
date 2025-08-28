from __future__ import annotations
from v2.segments import Segment
from typing import List, Dict
import numpy as np
from shapely import LineString, Point

class GroupeSegments:

    identifiant_global = 0


    def __init__(self, segments:List[Segment]):
        self.segments = segments
        self.identifiant:int = GroupeSegments.identifiant_global
        GroupeSegments.identifiant_global += 1

        for segment in self.segments:
            segment.groupe_segments = self


        self.X0:np.array = None # Point origine de la droite
        self.u:np.array = None # Vecteur directeur de la droite
        self.residu_moyen:float = None # Résidu moyen du moindre carré
        self.d_mean:float = None # Distance moyenne entre les plans et la droite finale
        self.longueur:float = None # Longueur de la ligne

        self.geometry:LineString = None
        self.p1:Point = None # Les deux extrémités de la droite sous forme de point 
        self.p2:Point = None

        self.voisins:List[GroupeSegments] = [] # Liste des groupes voisins

        self._supprime:bool = False # marqueur qui indique si le groupe de segments est considéré comme inutilisé

        self.u_plani:np.array = None # Vecteur directeur de la droite en projection plani

        self.a = None #Paramètres de la droite projetée
        self.b = None

        self.intersections:List[Dict[Point, GroupeSegments]] = []

    
    @classmethod
    def from_p1_p2(cls, segments:List[Segment], p1:Point, p2:Point)->GroupeSegments:
        new_group_segment = cls(segments)
        new_group_segment.p1 = p1
        new_group_segment.p2 = p2
        new_group_segment.geometry = LineString([p1, p2])
        return new_group_segment
    
    @classmethod
    def from_one_segment(cls, segment:Segment):
        """
        Crée un objet GroupeSegment à partir d'un seul segment pour lequel on a déjà la géométrie terrain
        Sert pour la deuxième tentative de fermeture
        """
        new_group_segment = cls([segment])
        linestring = segment.geometrie_terrain
        new_group_segment.p1 = Point(linestring.coords[0])
        new_group_segment.p2 = Point(linestring.coords[1])
        new_group_segment.geometry = segment.geometrie_terrain
        new_group_segment.calcule_a_b()
        return new_group_segment



    def get_geometrie(self) -> LineString:
        return self.geometry
    
    def get_residu_moyen(self) -> float:
        if self.residu_moyen is None:
            return None
        return self.residu_moyen[0,0]
    
    def get_d_mean(self) -> float:
        return self.d_mean
    
    def get_nb_segments(self) -> int:
        return len(self.segments)

    def get_identifiant(self)->int:
        return self.identifiant
    

    def compute_equations_plans(self)->None:
        for segment in self.segments:
            segment.compute_equation_plan()


    def check_configurations(self):
        """
        Si toutes les images appartiennent au même axe de vol et que le bord de toit est dans l'axe de vol de l'avion, 
        alors tous les plans passant par le sommet de prise de vue et le bord de toit seront pratiquement identiques.
        Dans ce cas, on ne calcule pas l'image. En effet, le moindre décalage de prédiction du FFL aura d'énorme conséquences sur le z du résultat du calcul.

        pour le détecter, on prend un plan.
        Puis pour tous les autres bords de toit, on regarde la distance du sommet de prise de vue au premier plan.
        Si toutes les distances sont inférieures à 200 mètres, alors on ne calcule pas et on utilisera la projection sur les autres segments
        """
        distance_max = 0
        if len(self.segments)>1:
            segment_0 = self.segments[0]
            distance_max = 0
            for i_s in range(1, len(self.segments)):
                segment = self.segments[i_s]
                sommet = segment.get_sommet_prise_de_vue_shapely()
                distance_max = max(distance_max, segment_0.distance_point_plan(sommet))
            if distance_max < 200:
                self._supprime = True

    def x_mean(self)->np.array:
        """
        Renvoie le barycentre des extrémités des segments projetées sur MNT dans le repère du monde
        """
        somme = 0
        for segment in self.segments:
            somme += segment.world_line[0,0]
            somme += segment.world_line[1,0]
        return somme / (len(self.segments)*2)
    

    def build_A_B(self):
        """
        Construction des matrices pour le calcul des moindres carrés

        L'équation est : ax + by + cz + d = 0
        Avec a, b, c, d les paramètres du plan
        L'équation de la droite est (x0, y0, z0) + lambda * (dx, dy, dz) pour tout lambda réel

        Pour limiter les ambiguïtés d'échelle, on fixe x0 et dx
        On fixe x0 au barycentre des points projetés au sol des goutières
        On fixe dx à 1
        Le vecteur X est (Y0, dy, Z0, dz)

        Pour chaque goutière un plan a été calculé

        Pour chaque plan, on cherche les trois points de la droite qui appartiennent à la fois à la droite et au plan. 
        Les points sont ceux correspondants à lambda = 0, lambda = 1e5 et lambda = -1e5

        On fixe une pondération sur la longueur du segment. Plus le segment est long, plus il est considéré comme important. 
        Cependant, cela n'apporte pas grand chose        
        """



        n = len(self.segments)

        A = np.zeros((3*n+1, 4))
        B = np.zeros((3*n+1, 1))
        P = np.zeros((3*n+1, 3*n+1))

        X0 = self.x_mean()
        
        lambda1 = 1e5
        lambda2 = -1e5

        for i in range(len(self.segments)):
            segment = self.segments[i]
            param = segment.param_plan
            A[3*i,:] = np.array([param[0,1], 0, param[0,2], 0])
            A[3*i+1,:] = np.array([param[0,1], lambda1*param[0,1], param[0,2], lambda1*param[0,2]])
            A[3*i+2,:] = np.array([param[0,1], lambda2*param[0,1], param[0,2], lambda2*param[0,2]])
            B[3*i, :] = -param[0, 3] - param[0, 0] * X0
            B[3*i+1, :] = -param[0, 3] - param[0, 0] * X0 - param[0, 0] * lambda1
            B[3*i+2, :] = -param[0, 3] - param[0, 0] * X0 - param[0, 0] * lambda2
            poids = 1
            P[3*i,3*i] = poids
            P[3*i+1,3*i+1] = poids
            P[3*i+2,3*i+2] = poids
        A[3*n, 3] = 1
        B[3*n, :] = 0
        P[3*n,3*n] = 10
        return A, B, P, X0
    


    def moindres_carres(self)->None:
        segment_supprime = True
        while segment_supprime and len(self.segments) > 1:
            segment_supprime = False

            # On construit les matrices pour les moindres carrés
            A, B, P, X0 = self.build_A_B()
            #Calcul des paramètres de la droite avec les moindres carrés
            #x_chap, res, _, _ = np.linalg.lstsq(A, B, rcond=None)
            N = A.T @ P @ A
            K = A.T @ P @ B
            try:
                x_chap = np.linalg.inv(N) @ K
            except:
                self.segments = []
                continue

            #Distance au plan
            
            # On met sous une forme un peu plus jolie X0 l'origine de la droite et u le vecteur directeur
            X0 = np.array([[X0], [x_chap[0,0]], [x_chap[2,0]]])
            u = np.array([[1], [x_chap[1,0]], [x_chap[3,0]]])

            V = B - A @ x_chap
            n = A.shape[0]
            m = A.shape[1]
            sigma_0 = V.T @ P @  V / (n - m)
            var_V = sigma_0 * (np.linalg.inv(P) - A @ np.linalg.inv(A.T @ P @ A) @ A.T)
            V_norm = np.abs(V.squeeze()/np.sqrt(np.diag(var_V)))

            # On exclut la dernière équation (gouttière horizontale) lors de la recherche du plus haut résidu
            V_norm = V_norm[:-1]

            V_norm_max = np.max(V_norm)
            V_norm_argmax = np.argmax(V_norm)
            residu_moyen = np.sqrt(V.T @ V) / len(self.segments)
            if V_norm_max > 2:
                segment_faux = self.segments[V_norm_argmax//3]
                self.segments.remove(segment_faux)
                segment_supprime = True
            elif np.isnan(V_norm_max):
                self.segments = []

                
        self.X0 = X0
        self.u = u
        self.residu_moyen = residu_moyen

        u_plani = u[:2,:]
        self.u_plani = u_plani/np.linalg.norm(u_plani)




        
    
    def distance_moyenne(self):
        """
        Récupère la distance moyenne entre la droite (sommet de prise de vue, extrémité d'un segment sur pva) et la droite (goutiere)
        Renvoie également les points qui délimitent la goutière sur la droite (goutiere)
        """
        points1 = []
        points2 = []
        somme_distance = 0

        if len(self.segments)==0:
            self.longueur = 1e15
            return None
        
        # On parcourt toutes les pvas
        for segment in self.segments:
            # On récupère les points les plus proches et les distances correspondantes entre la droite (sommet de prise de vue, extrémité 1 d'un segment sur pva) et la droite (goutiere)
            # et entre la droite (sommet de prise de vue, extrémité 2 d'un segment sur pva) et la droite (goutiere)
            
            p1, p2, d1, d2 = segment.points_plus_proche(self.X0, self.u)

            # On ajoute les distances à l'accumulateur
            somme_distance += d1
            somme_distance += d2

            # Rien n'assure que le point 1 d'une pva corresponde à la même extrémité du segment sur une autre pva
            # On regroupe les points par extrémité de segments
            if len(points1) == 0:
                points1.append(p1)
                points2.append(p2)
            
            else:
                # On mesure la distance entre le point 1 avec chacun des deux points de la première pva
                d_p1_points1 = self.distance(p1, points1[0])
                d_p1_points2 = self.distance(p1, points2[0])
                # On met le point avec celui qui est le plus proche
                if d_p1_points1 < d_p1_points2:
                    points1.append(p1)
                    points2.append(p2)
                else:
                    points1.append(p2)
                    points2.append(p1)


        
        # On prend les coordonnées des extrémités de la goutière la plus petite
        indice_max = 0
        distance_max = 0
        for i, segment in enumerate(self.segments):
            distance = segment.get_longueur()
            if distance > distance_max:
                distance_max = distance
                indice_max = i

        p1 = self.get_point_from_x(self.X0, self.u, points1[indice_max][0,0])
        p2 = self.get_point_from_x(self.X0, self.u, points2[indice_max][0,0])
        self.p1 = Point(p1[0,0], p1[1,0], p1[2,0])
        self.p2 = Point(p2[0,0], p2[1,0], p2[2,0])
        self.geometry = LineString([self.p1, self.p2])
        self.d_mean = somme_distance / (2*len(self.segments))
        
        u = p2 - p1
        self.longueur = np.linalg.norm(u)


        if u[0,0] == 0:
            self.a = 0
            self.b = p1[1,0]
        else:
            self.a = u[1,0] / u[0,0]
            self.b = p1[1,0] - p1[0,0] / u[0,0] * u[1,0]

    
    def verifier_resultat_valide(self):
        """
        Mettre ici toutes les conditions pour lesquelles un résultat d'intersection soit accepté
        """
        # S'il n'y a pas assez de segments qui ont été utilisés pour le calcul
        if len(self.segments)<2:
            self._supprime = True
        if self.longueur is None or self.longueur > 1000:
            self._supprime = True
        if self.d_mean is None or self.d_mean > 1:
            self._supprime = True

        # On vérifie que la hauteur du bord de toit reste cohérent par rapport au MNT : entre -10 mètres et +150 mètres
        altitude_moyenne = self.altitude_moyenne()
        if altitude_moyenne is None:
            self._supprime = True
            return True
        if altitude_moyenne < -10 or altitude_moyenne > 150:
            self._supprime = True
        return True

        


    def distance(self, p1:np.array, p2:np.array)->float:
        """
        Retouren la distance entre les points p1 et p2
        """
        return np.sqrt(np.sum((p1 - p2)**2))
    

    def get_point_from_x(self, X0:np.array, u:np.array, x:float)->np.array:
        """
        Retourne le point appartenant à la droite (X0, u) ayant pour abscisse x
        """

        l = (x - X0[0,0]) / u[0,0]
        p = X0 + l * u
        return p
    

    def is_valid(self)->bool:
        return not self._supprime
    
    def add_groupe_voisin(self, voisin:GroupeSegments)->None:
        if voisin not in self.voisins:
            self.voisins.append(voisin)
    

    def update_voisins(self):
        """
        On récupère la liste des groupes de segments voisins
        """
        voisins:List[GroupeSegments] = []

        # On parcourt toutes les goutières du bati (celles qui sont restées après le calcul)
        for segment in self.segments:
            voisin_1 = segment.voisin_1
            
            groupe_voisin:GroupeSegments = voisin_1.get_groupe_segments()
            if groupe_voisin is not None and groupe_voisin not in voisins and groupe_voisin!=self and groupe_voisin.is_valid():
                voisins.append(groupe_voisin)
            
            voisin_2 = segment.voisin_2
            groupe_voisin:GroupeSegments = voisin_2.get_groupe_segments()
            if groupe_voisin is not None and groupe_voisin not in voisins and groupe_voisin!=self and groupe_voisin.is_valid():
                voisins.append(groupe_voisin)
            
            
        self.voisins = voisins

        for groupe_voisin in voisins:
            groupe_voisin.add_groupe_voisin(self)


    def compute_produit_scalaire(self, groupe_segment_2:GroupeSegments)->float:
        return np.abs(np.sum(self.u_plani*groupe_segment_2.u_plani))
    

    def update_voisins_ps(self, seuil_ps:float):
        """
        On ne conserve que les voisins avec lequel le produit scalaire est supérieur à un certain seuil
        """

        voisins:List[GroupeSegments] = []

        for voisin in self.voisins:
            if voisin.is_valid():
                ps = self.compute_produit_scalaire(voisin)
                if ps < seuil_ps:
                    voisins.append(voisin)
        self.voisins = voisins

    def intersection(self, s2:GroupeSegments):
        x = -(s2.b - self.b) / (s2.a - self.a)
        y = self.a * x + self.b
        return x, y
    
    def calcul_z(self, x):
        l = (x-self.p1.x) / self.u[0,0]
        z = self.p1.z + l * self.u[2,0]
        return z
    

    def ajouter_intersection(self, intersection:Point, groupe_segments:GroupeSegments):
        """
        Ajoute intersection à self.intersections si l'intersection n'y est pas déjà.

        Suite à des erreurs d'arrondis, on vérifie que l'intersection n'est pas déjà présente via un calcul de distance
        """
        ajout = True
        epsilon = 0.1
        for i in self.intersections:
            if self.distance_point(i["point"], intersection) < epsilon:
                ajout = False
        if ajout:
            self.intersections.append({"point":intersection, "groupe_segments":groupe_segments})


    def distance_point(self, p1:Point, p2:Point):
        return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)
    

    def calcule_a_b(self):
        ux0 = self.p2.x - self.p1.x
        uy0 = self.p2.y - self.p1.y
        uz0 = self.p2.z - self.p1.z

        u = np.array([[ux0], [uy0], [uz0]])
        self.u = u / np.linalg.norm(u)
        self.longueur = np.linalg.norm(u)

        u_plani = np.array([[ux0], [uy0]])
        self.u_plani = u_plani / np.linalg.norm(u_plani)

        if ux0 == 0:
            self.a = 0
            self.b = self.p1.y
        else:
            self.a = uy0 / ux0
            self.b = self.p1.y - self.p1.x / ux0 * uy0


    def p_proches_points(self, p1:Point, p2:Point):
        """
        Renvoie deux couples de points en réunissant les plus proches.
        Le premier couple est constitué du point self.p1
        Le deuxième sont les deux autres points
        """
        minimum = 1e10
        
        d11 = self.distance_point(self.p1, p1)
        minimum = min(d11, minimum)
        d12 = self.distance_point(self.p1, p2)
        minimum = min(d12, minimum)
        d21 = self.distance_point(self.p2, p1)
        minimum = min(d21, minimum)
        d22 = self.distance_point(self.p2, p2)
        minimum = min(d22, minimum)
        if d11 == minimum:
            return (self.p1, p1), (self.p2, p2)
        if d12 == minimum:
            return (self.p1, p2), (self.p2, p1)
        if d21 == minimum:
            return (self.p1, p2), (self.p2, p1)
        if d22 == minimum:
            return (self.p1, p1), (self.p2, p2)
        

    def sort_by_intersection(self):
        """
        On trie les intersections pour qu'elles soient un ordre
        """
        intersection_ref = self.intersections[0]
        intersections_dict = [{"intersection":intersection_ref, "lamb":0}]
        for i in range(1, len(self.intersections)):
            intersection_cur = self.intersections[i]
            lamb = (intersection_cur["point"].x - intersection_ref["point"].x)/self.u[0,0]
            intersections_dict.append({"intersection":intersection_cur, "lamb":lamb})

        intersections_dict_sorted = sorted(intersections_dict, key=lambda d: d['lamb'])
        return intersections_dict_sorted
    
    def set_p1(self, p1:Point):
        self.p1 = p1
        self.update_geometrie()

    def set_p2(self, p2:Point):
        self.p2 = p2
        self.update_geometrie()
    
    def update_geometrie(self):
        self.geometry = LineString([self.p1, self.p2])


    def altitude_moyenne(self)->float:
        if self.p1 is None or self.p2 is None:
            return None
        x_mean = (self.p1.x + self.p2.x) / 2
        y_mean = (self.p1.y + self.p2.y) / 2
        z_mean = (self.p1.z + self.p2.z) / 2
        z_sol = self.segments[0].mnt.get(x_mean, y_mean)
        return z_mean - z_sol