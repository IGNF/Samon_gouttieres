from goutiere import Goutiere_image
from typing import List
import numpy as np
import logging

logging.basicConfig(filename='Moindres_carres.log', level=logging.INFO, format='%(asctime)s : %(levelname)s : %(module)s : %(message)s')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)
logger = logging.getLogger(__name__)


class GoutiereChantier:

    def __init__(self, id, shapefileDir, goutieres, seuil = 0.2, methode="grand", maitresse_petite=True):
        """
        id : id de la goutière
        ta : chemin vers le tableau d'assemblage
        shapefileDir : répertoire contenant les shapefiles par pvas avec les goutières sur chaque pva
        goutieres : liste des goutières
        seuil : seuil pour les moindres carrés au-delà duquel on supprime les images.
        """
        self.id = id
        self.shapefileDir = shapefileDir
        self.goutieres:List[Goutiere_image] = goutieres
        self.seuil = seuil
        self.methode = methode
        self.maitresse_petite = maitresse_petite
        
        self.goutiere_maitresse_retiree = False
        self.plus_petite_goutiere = None
        self.goutiere_maitresse = None

        self.get_goutiere_maitresse()


    def get_goutiere_maitresse(self):
        if self.maitresse_petite:
            self.goutiere_maitresse = self.get_plus_petite_goutiere()
        else:
            self.goutiere_maitresse = self.get_plus_grande_goutiere()

    def get_plus_petite_goutiere(self):
        goutiere_min = self.goutieres[0]
        distance_min = 1e10
        for goutiere in self.goutieres:
            distance = goutiere.get_longueur()
            if distance < distance_min:
                distance_min = distance
                goutiere_min = goutiere
        return goutiere_min


    def get_plus_grande_goutiere(self):
        goutiere_max = self.goutieres[0]
        distance_max = 0
        for goutiere in self.goutieres:
            distance = goutiere.get_longueur()
            if distance > distance_max:
                distance_max = distance
                goutiere_max = goutiere
        return goutiere_max


    
    def distance_moyenne(self):
        """
        Récupère la distance moyenne entre la droite (sommet de prise de vue, extrémité d'un segment sur pva) et la droite (goutiere)
        Renvoie également les points qui délimitent la goutière sur la droite (goutiere)
        """
        points1 = []
        points2 = []
        somme_distance = 0
        # On parcourt toutes les pvas
        for goutiere in self.goutieres:
            # On récupère les points les plus proches et les distances correspondantes entre la droite (sommet de prise de vue, extrémité 1 d'un segment sur pva) et la droite (goutiere)
            # et entre la droite (sommet de prise de vue, extrémité 2 d'un segment sur pva) et la droite (goutiere)
            
            p1, p2, d1, d2 = goutiere.points_plus_proche(self.X0, self.u)
            logger.info(f"Goutière id unique {goutiere.id_unique} : d1 :  {d1}, d2 : {d2}")

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
        
        
        if self.methode == "barycentre":
            # On calcule le barycentre en x pour chacune des deux extrémités
            x1 = 0
            for p in points1:
                x1 += p[0,0]
            x2 = 0
            for p in points2:
                x2 += p[0,0]

            # On récupère le point sur la droite d'abscisse x1 et x2 pour chacune des deux extrémités
            self.p1 = self.get_point_from_x(self.X0, self.u, x1/len(self.goutieres))
            self.p2 = self.get_point_from_x(self.X0, self.u, x2/len(self.goutieres))

        elif self.methode == "petit":
            # On prend les coordonnées des extrémités de la goutière la plus petite
            indice_min = 0
            distance_min = 1e10
            for i, goutiere in enumerate(self.goutieres):
                distance = goutiere.get_longueur()
                if distance < distance_min:
                    distance_min = distance
                    indice_min = i

            self.p1 = self.get_point_from_x(self.X0, self.u, points1[indice_min][0,0])
            self.p2 = self.get_point_from_x(self.X0, self.u, points2[indice_min][0,0])

        elif self.methode == "grand":
            # On prend les coordonnées des extrémités de la goutière la plus petite
            indice_max = 0
            distance_max = 0
            for i, goutiere in enumerate(self.goutieres):
                distance = goutiere.get_longueur()
                if distance > distance_max:
                    distance_max = distance
                    indice_max = i

            self.p1 = self.get_point_from_x(self.X0, self.u, points1[indice_max][0,0])
            self.p2 = self.get_point_from_x(self.X0, self.u, points2[indice_max][0,0])
        self.d_mean = somme_distance / (2*len(self.goutieres))
        logger.info(f"Distance moyenne : {self.d_mean}")


    def distance(self, p1, p2):
        """
        Retouren la distance entre les points p1 et p2
        """
        return np.sqrt(np.sum((p1 - p2)**2))


    def moindres_carres(self):
        """
        Résout le système par moindres carrés
        """
        d_max = self.seuil + 1

        gouttiere_supprimee = True
        logger.info(f"Chantier : {self.goutieres[0].id}")
        logger.info(f"Nombre de goutières : {len(self.goutieres)}")
        while gouttiere_supprimee and len(self.goutieres) > 1:
            gouttiere_supprimee = False

            # On construit les matrices pour les moindres carrés
            A, B, P, X0 = self.build_A_B()

            #Calcul des paramètres de la droite avec les moindres carrés
            #x_chap, res, _, _ = np.linalg.lstsq(A, B, rcond=None)
            N = A.T @ P @ A
            K = A.T @ P @ B
            x_chap = np.linalg.inv(N) @ K

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
            logger.info(f"résidu moyen : {V.T @ V / len(self.goutieres)}")
            logger.info(f"V_norm_max : {V_norm_max}")
            if V_norm_max > 2:
                goutieres_fausse = self.goutieres[V_norm_argmax//3]
                logger.info(f"On supprime : {goutieres_fausse.id_unique}")
                self.goutieres.remove(goutieres_fausse)
                gouttiere_supprimee = True

                
        logger.info(f"X0 : {X0}")
        logger.info(f"u : {u}")
        self.X0 = X0
        self.u = u


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

        longueur_total = 0
        for gouttiere in self.goutieres:
            longueur_total += gouttiere.get_longueur()


        n = len(self.goutieres)

        A = np.zeros((3*n+1, 4))
        B = np.zeros((3*n+1, 1))
        P = np.zeros((3*n+1, 3*n+1))

        X0 = self.x_mean()
        
        lambda1 = 1e5
        lambda2 = -1e5

        for i in range(len(self.goutieres)):
            goutiere = self.goutieres[i]
            param = goutiere.param_plan
            A[3*i,:] = np.array([param[0,1], 0, param[0,2], 0])
            A[3*i+1,:] = np.array([param[0,1], lambda1*param[0,1], param[0,2], lambda1*param[0,2]])
            A[3*i+2,:] = np.array([param[0,1], lambda2*param[0,1], param[0,2], lambda2*param[0,2]])
            B[3*i, :] = -param[0, 3] - param[0, 0] * X0
            B[3*i+1, :] = -param[0, 3] - param[0, 0] * X0 - param[0, 0] * lambda1
            B[3*i+2, :] = -param[0, 3] - param[0, 0] * X0 - param[0, 0] * lambda2
            poids = goutiere.get_longueur() / longueur_total
            P[3*i,3*i] = poids
            P[3*i+1,3*i+1] = poids
            P[3*i+2,3*i+2] = poids
        A[3*n, 3] = 1
        B[3*n, :] = 0
        P[3*n,3*n] = 10
        return A, B, P, X0


    def get_distance_max(self, X0, u):
        """
        Renvoie la goutière (et la distance associée) qui est la plus éloignée de la droite d'origine X0 et de vecteur directeur u
        
        """
        d_max = None
        g_max = None
        # On parcourt toutes les goutières
        for goutiere in self.goutieres:
            # Pour chaque goutière, on calcule la distance entre les deux extrémités de la goutière et la droite (X0, u) 
            _, _, d1, d2 = goutiere.points_plus_proche(X0, u, printout=False)
            # On conserve la distance maximale entre les deux extrémités
            d = max(d1, d2)
            # On récupère la distance maximale sur l'ensemble des goutières
            if d_max is None:
                d_max = d
                g_max = goutiere
            else:
                if d > d_max:
                    d_max = d
                    g_max = goutiere
        return d_max, g_max


    def get_point_from_x(self, X0, u, x):
        """
        Retourne le point appartenant à la droite (X0, u) ayant pour abscisse x
        """

        l = (x - X0[0,0]) / u[0,0]
        p = X0 + l * u
        return p



    
    def x_mean(self):
        """
        Renvoie le barycentre des extrémités des goutières projetées sur MNT dans le repère du monde
        """
        somme = 0
        for goutiere in self.goutieres:
            somme += goutiere.world_line[0,0]
            somme += goutiere.world_line[1,0]
        return somme / (len(self.goutieres)*2)


    def save_points_cloud(self, path, resolution = 0.2):
        """
        Sauvegarde la droite (p1, p2) (c'est-à-dire la goutière calculée) sous forme d'un nuage de points dans un fichier xyz.
        resolution : distance entre deux points
        """
        u = self.p2 - self.p1
        norm_u = np.linalg.norm(u)
        u_norm = u / norm_u
        nb_points = int(norm_u / resolution)

        
        with open(path, "a") as f:
            for i in range(nb_points):
                p = self.p1 + i * resolution * u_norm
                f.write("{} {} {} {}\n".format(p[0, 0], p[1, 0], p[2, 0], len(self.goutieres)))



    def get_voisins(self, liste_id_unique):
        voisins = []

        # On parcourt toutes les goutières du bati (celles qui sont restées après le calcul)
        for g in self.goutieres:
            # On récupère le voisin 1
            if g.voisin_1 < len(liste_id_unique):
                v1 = liste_id_unique[g.voisin_1]
                # S'il existe :
                if len(v1) >= 1:
                    # On récupère l'identifiant du chantier
                    id_chantier_1 = v1[0].id
                    #Si l'identifiant du chantier n'a pas déjà été ajouté et qu'il est différent de l'id du chantier, on l'ajoute
                    if id_chantier_1 not in voisins and int(id_chantier_1) != int(g.id) :
                        voisins.append(int(id_chantier_1))

            # On récupère le voisin 2
            if g.voisin_2 < len(liste_id_unique):
                v2 = liste_id_unique[g.voisin_2]
                # S'il existe :
                if len(v2) >= 1:
                    # On récupère l'identifiant du chantier
                    id_chantier_2 = v2[0].id
                    #Si l'identifiant du chantier n'a pas déjà été ajouté et qu'il est différent de l'id du chantier, on l'ajoute
                    if id_chantier_2 not in voisins and int(id_chantier_2) != int(g.id):
                        voisins.append(int(id_chantier_2))
        
        return voisins




    