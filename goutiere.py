import numpy as np
from shapely import LineString, Point


class Goutiere:

    def __init__(self, path, id) -> None:
        """
        shot : objet Shot de PySocle contenant la pva associée à la goutière
        path : chemin du fichier shapefile contenant la goutière
        dem : modèle numérique de terrain
        id : identifiant de la goutière dans le fichier shapefile

        image_line : coordonnées de la goutière dans le repère image

        """
        
        self.path:str = path
        
        self.id = id
        self.id_goutiere = []
        self.id_chantier = None
        self.id_bati = None
        self.id_unique = None
        self.voisin_1 = None
        self.voisin_2 = None

        self.homologue_1 = []
        self.homologue_2 = []

        self.marque = False

        self.world_line:np.array = None
        

    def append_homologue_1(self, segment):
        if segment not in self.homologue_1:
            self.homologue_1.append(segment)


    def append_homologue_2(self, segment):
        if segment not in self.homologue_2:
            self.homologue_2.append(segment)
        



    def u_directeur_world(self):
        u = self.world_line[0,:2] - self.world_line[1,:2]
        return u / np.linalg.norm(u)
        
    def barycentre_world(self):
        return (self.world_line[0,:2] + self.world_line[1,:2]) / 2

    
    def get_projection(self):
        return LineString([[self.world_line[0,0], self.world_line[0,1], self.world_line[0,2]], [self.world_line[1,0], self.world_line[1,1], self.world_line[1,2]]])

    def get_longueur(self):
        return np.sqrt(np.sum((self.world_line[0,:]-self.world_line[1,:])**2))


    def P0_sol(self):
        return Point(self.world_line[0,0], self.world_line[0, 1])

    def P1_sol(self):
        return Point(self.world_line[1,0], self.world_line[1, 1])


    def P0(self):
        return Point(self.world_line[0,0], self.world_line[0, 1], self.world_line[0, 2])

    def P1(self):
        return Point(self.world_line[1,0], self.world_line[1, 1], self.world_line[1, 2])

    
    def distance_point(self, p1, p2):
        return np.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)


    def p_proches(self, s2):
        """
        Renvoie deux couples de points.
        Le premier couple est constitué des points de self et de s2 qui sont les plus proches
        Le deuxième sont les deux autres points
        """
        minimum = 1e10
        
        d11 = self.distance_point(self.P0(), s2.P0())
        minimum = min(d11, minimum)
        d12 = self.distance_point(self.P0(), s2.P1())
        minimum = min(d12, minimum)
        d21 = self.distance_point(self.P1(), s2.P0())
        minimum = min(d21, minimum)
        d22 = self.distance_point(self.P1(), s2.P1())
        minimum = min(d22, minimum)
        if d11 == minimum:
            return (self.P0(), s2.P0()), (self.P1(), s2.P1())
        if d12 == minimum:
            return (self.P0(), s2.P1()), (self.P1(), s2.P0())
        if d21 == minimum:
            return (self.P1(), s2.P0()), (self.P0(), s2.P1())
        if d22 == minimum:
            return (self.P1(), s2.P1()), (self.P0(), s2.P0())


class Goutiere_image(Goutiere):
    def __init__(self, shot, path, dem, id) -> None:
        """
        world_line : coordonnées de la goutière projetée sur le mnt
        param_plan : paramètres (a, b, c, d) du plan ax+by+cz+d=0 passant par la goutière et le sommetbde prise de vue du cliché
        """
        super().__init__(path, id)

        self.shot = shot # Dans image
        self.dem = dem # dans image
        self.world_line:np.array = None # dans image
        self.param_plan:np.array = None # dans image
        self.image = shot.image

    def get_plan(self):
        """
        Calcule les coordonnées des extrémités de la goutières projetées sur le mnt
        """
        try:
            x, y, z = self.shot.image_to_world(self.image_line[:,0], self.image_line[:,1], self.dem)
            self.world_line = np.array([[x[0], y[0], z[0]], [x[1], y[1], z[1]]])
        except:
            

            z_world = self.dem.get(self.shot.x_pos, self.shot.y_pos)
            z_world = np.full_like(self.image_line[:,1], z_world)
            x_local, y_local, z_local = self.shot.image_z_to_local(self.image_line[:,1], self.image_line[:,0], z_world)
            # On a les coordonnées locales approchées (car z non local) on passe en world
            x_world, y_world, _ = self.shot.system.euclidean_to_world(x_local, y_local, z_local)
            self.world_line = np.zeros((2, 3))

    def equation_plan(self):
        """
        Calcule les paramètres du plan passant par le sommet de prise de vue et par la goutière
        """
        vec1 = self.world_line[0] - self.get_sommet_prise_de_vue()
        vec1 = vec1 / np.linalg.norm(vec1)
        vec2 = self.world_line[1] - self.get_sommet_prise_de_vue()
        vec2 = vec2 / np.linalg.norm(vec2)
        normale = np.cross(vec1, vec2)
        d = -(normale[0,0] * self.world_line[0,0] + normale[0,1] * self.world_line[0,1] + normale[0,2] * self.world_line[0,2])
        self.param_plan = np.concatenate((normale, np.array([[d]])), axis=1)

    

    def set_image_line(self, image_line, compute_equation_plan=False):
        self.image_line = image_line
        self.get_plan()

        if compute_equation_plan:
            self.equation_plan()


    def get_sommet_prise_de_vue(self):
        """
        Retourne les coordonnées du sommet de prise de vue
        """
        image_conical = self.shot
        return np.array([[image_conical.x_pos, image_conical.y_pos, image_conical.z_pos.item()]])

    def get_image(self):
        return self.shot.image


    def points_plus_proche(self, X1, u1, printout=True):
        """
        Renvoie pour chacune des extrémités du segment le point appartenant à la droite calculée le plus proche de la droite (sommet de prise de vue, point au sol)
        """

        point0, d0 = self.point_plus_proche(X1, u1, self.world_line[0].reshape((3,1)), printout)
        point1, d1 = self.point_plus_proche(X1, u1, self.world_line[1].reshape((3,1)), printout)
        return point0, point1, d0, d1
    
    def point_plus_proche(self, X1, u1, X2, printout):
        """
        Renvoie le point de la droite (X1, u1) le plus proche de la droite (sommet de prise de vue, point au sol de l'extrémité du segment sur la pva (X2))
        """

       
        u2 = self.get_sommet_prise_de_vue().reshape((3,1)) - X2
        u2 = u2 / np.linalg.norm(u2)
        u1 = u1 / np.linalg.norm(u1)


        X2X1 = X2 - X1
        u1u2 = np.sum(u1*u2)
        u2u2 = np.sum(u2*u2)
        u1u1 = np.sum(u1*u1)
    
        n1 = u1 - u1u2/u2u2 * u2
        n2 = u2 - u1u2/u1u1 * u1

        l1 = (np.sum(X2X1 * n1))/(np.sum(u1*n1))
        l2 = -(np.sum(X2X1 * n2))/(np.sum(u2*n2))


        p1 = X1 + l1 * u1

        p2 = X2 + l2 * u2

        if printout:
            print("Distance à la droite : ", np.sqrt(np.sum((p1-p2)**2)))

        return X1 + l1 * u1, np.sqrt(np.sum((p1-p2)**2)) 


    def get_image_geometry(self, superpose_pva=False):
        if superpose_pva:
            return LineString([[self.image_line[0,0], -self.image_line[0,1]], [self.image_line[1,0], -self.image_line[1,1]]])
        else:
            return LineString([[self.image_line[0,0], self.image_line[0,1]], [self.image_line[1,0], self.image_line[1,1]]])

    def P0_image(self):
        return Point(self.image_line[0,0], self.image_line[0, 1])

    def P1_image(self):
        return Point(self.image_line[1,0], self.image_line[1, 1])


class Goutiere_proj(Goutiere):
    
    def __init__(self, path, id, image) -> None:
        super().__init__(path, id)

        self.image = image

    def get_image(self):
        return self.image

