from shapely.geometry import Point
from v2.samon.chantier import Chantier
from typing import List
import time
from v2.samon.tool import print_log 
from v2.samon.infosResultats import InfosResultats
from v2.shot import Shot, MNT, RAF


class Monoscopie:
    """
    A class for getting x, y, z coordinates from points on BD Ortho
    """

    def __init__(self, pva: str, mnt:MNT, raf:RAF, shots:List[Shot]) -> None:
        self.pva:str = pva
        self.mnt:MNT = mnt
        self.raf:RAF = raf
        self.shots:List[Shot] = shots


        self.points: List[Point] = []
        self.size_orthoLocale = 141
        self.size_bd_ortho = 61
        self.size_small_bd_ortho = 11

        self.seuil_maitresse = 0.9
        self.seuil_ortho_locale = 0.4
        self.type_correlation = "pva"
        
        
        self.log = False
        self.sauvegarde = False
        
        self.chantier = None
        self.infosResultats = None

        self.resultats = "temp"


    def run(self, point:Point, orthoLocaleMaitresse:Shot=None, z_min:float=None, z_max:float=None, meme_bande=False)->InfosResultats:
        """
        Détermine les coordonnées x, y, z des points
        """

        print_log("Point : {}".format(point))

        tic = time.time()
        #On construit pour chaque point la classe Chantier
        self.chantier = Chantier(point, 0.2, self, type_correlation=self.type_correlation, sauvegarde=self.sauvegarde)
        
        #On récupère les pvas dont l'emprise contient le point
        self.chantier.get_pvas(self.shots)
        print_log("get_pvas : {}".format(time.time()-tic))
        #S'il n'y a pas au moins deux pvas, alors on passe au point suivant
        if len(self.chantier.pvas) < 2:
            self.infosResultats = InfosResultats(False)
        #On crée les orthos extraites de la BD Ortho
        
        result = self.chantier.create_bd_ortho(orthoLocaleMaitresse)
        if not result:
            self.infosResultats = InfosResultats(False)
            return self.infosResultats
        
        print_log("get_bd_ortho : {}".format(time.time()-tic))
        self.chantier.create_small_ortho()
        #Pour chaque pva, on crée des orthos locales
        self.chantier.create_orthos_locales()
        print_log("Ortho locales créées : {}".format(time.time()-tic))
        print_log("\nDébut de la méthode par pseudo-intersection")
        #On calcule grossièrement le point de corrélation entre la BD Ortho et les orthos locales
        self.chantier.compute_correlations(self.chantier.bd_ortho, "pi")
        print_log("compute_correlations : {}".format(time.time()-tic))
        #On affine la corrélation pour les pvas dont le score de corrélation est supérieur à self.seuil_maitresse
        success = self.chantier.improve_correlations()
        if not success:
            self.infosResultats = InfosResultats(False)
        else:
            print_log("improve_correlations : {}".format(time.time()-tic))
            #Pour toutes les images qui ne sont pas maitresses, on recherche le point de corrélation sur la droite épipolaire
            self.chantier.compute_correl_epip(z_min, z_max)
            print_log("compute_correl_epip : {}".format(time.time()-tic))

            #Si on est dans le mode meme_bande, alors on récupère
            #toutes les images du même axe de vol que l'image maîtresse
            liste_meme_bande = []
            if meme_bande:
                liste_meme_bande = self.chantier.get_liste_meme_bande()
            #On ne conserve que les orthos locales pour lesquelles le score de corrélation est supérieur à self.seuil_ortho_locale
            self.chantier.filter_ortho_locales(self.seuil_ortho_locale, liste_meme_bande)
            #On calcule la pseudo-intersection
            self.lancer_calcul()
            print_log("Fin : {}".format(time.time()-tic))
        return self.infosResultats
        


    def lancer_calcul(self):
        x_chap, nb_images, residus = self.chantier.compute_pseudo_intersection()
        self.chantier.x_chap = x_chap
        z = self.mnt.get(self.chantier.point.x, self.chantier.point.y)
        print_log("résultat final : {}".format(x_chap))
        if nb_images == 0:
            self.infosResultats = InfosResultats(False)
        else:
            self.infosResultats = InfosResultats(True, self.chantier.id, self.chantier.point, z, x_chap, nb_images, residus)
        
        