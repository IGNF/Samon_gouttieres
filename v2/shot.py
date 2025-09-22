import numpy as np
import pyproj
from scipy.spatial.transform import Rotation as R
from osgeo import gdal
from scipy import ndimage
from shapely import Polygon, Point
from lxml import etree
import os
from typing import List
from scipy.interpolate import LinearNDInterpolator


class Shot:

    def __init__(self):
        self.x_central = None
        self.y_central = None
        self.z_central = None

        self.rot_to_euclidean_local = None

        self.proj = {"auth": "IGNF:RGF93LAMB93", "ta": "Lambert93", "MatchAT": "RGF93\ /\ Lambert-93", "PMS3D": "L-93 :",
                    "epsg_geoc": 4964, "epsg_geog": 7084, "geoid": "RAF20"}
        self.crs = pyproj.CRS.from_string(self.proj["auth"])
        self.crs_geoc = pyproj.CRS.from_epsg(self.proj["epsg_geoc"])
        self.crs_geog = pyproj.CRS.from_epsg(self.proj["epsg_geog"])
        self.carto_to_geoc = pyproj.Transformer.from_crs(self.crs, self.crs_geoc).transform
        self.geoc_to_carto = pyproj.Transformer.from_crs(self.crs_geoc, self.crs).transform
        self.carto_to_geog = pyproj.Transformer.from_crs(self.crs, self.crs_geog).transform


    def world_to_euclidean(self, x, y, z):
        """
        Transform a point from the world coordinate reference system into the Euclidean coordinate reference system
        :param x: x coordinate of the point
        :param y: y coordinate of the point
        :param z: z coordinate of the point
        :return: x, y, z in the Euclidean coordinate reference system
        """
        x_geoc, y_geoc, z_geoc = self.carto_to_geoc(np.array(x), np.array(y), np.array(z))
        x_central_geoc, y_central_geoc, z_central_geoc = self.carto_to_geoc(self.x_central, self.y_central, self.z_central)
        dr = np.vstack([x_geoc-x_central_geoc, y_geoc-y_central_geoc, z_geoc-z_central_geoc])
        point_eucli = (self.rot_to_euclidean_local @ dr) + np.array([self.x_central, self.y_central, self.z_central]).reshape(-1, 1)
        return np.squeeze(point_eucli[0]), np.squeeze(point_eucli[1]), np.squeeze(point_eucli[2])
    

    def euclidean_to_world(self, x_eucli, y_eucli, z_eucli):
        """
        Transform a point from the Euclidean coordinate reference system into the world coordinate reference system.

        :param x_eucli: x coordinate of the point
        :param y_eucli: y coordinate of the point
        :param z_eucli: y coordinate of the point

        :return: x, y, z in the world coordinate reference system
        """
        x_eucli, y_eucli, z_eucli = np.array(x_eucli), np.array(y_eucli), np.array(z_eucli)
        x_central_geoc, y_central_geoc, z_central_geoc = self.carto_to_geoc(np.array([self.x_central]),
                                                                                        np.array([self.y_central]),
                                                                                        np.array([self.z_central]))

        dr = np.vstack([x_eucli - self.x_central, y_eucli - self.y_central, z_eucli - self.z_central])
        point_geoc = (self.rot_to_euclidean_local.T @ dr) + \
                     np.array([x_central_geoc, y_central_geoc, z_central_geoc]).reshape(-1, 1)
        return self.geoc_to_carto(point_geoc[0], point_geoc[1], point_geoc[2])
    

    def image_z_to_local(self, c, l, z):
        x_local_0, y_local_0, z_local_0, x_local_1, y_local_1, z_local_1 = self.image_to_local_vec(c, l)
        lamb = (z - z_local_0) / (z_local_1 - z_local_0)
        x_local = x_local_0 + (x_local_1 - x_local_0) * lamb
        y_local = y_local_0 + (y_local_1 - y_local_0) * lamb
        return x_local, y_local, z
    

    def image_to_local_vec(self, c, l):
        # on calcule le faisceau perspectif
        x_bundle_0, y_bundle_0, z_bundle_0 = 0, 0, 0
        x_bundle_1, y_bundle_1, z_bundle_1 = self.shot_to_bundle(*self.image_to_shot(c, l))

        # on passe le faisceau dans le repere local extrinseque
        x_local_0, y_local_0, z_local_0 = self.bundle_to_local(x_bundle_0, y_bundle_0, z_bundle_0)
        x_local_1, y_local_1, z_local_1 = self.bundle_to_local(x_bundle_1, y_bundle_1, z_bundle_1)

        return x_local_0, y_local_0, z_local_0, x_local_1, y_local_1, z_local_1
    
    def shot_to_bundle(self, x_shot, y_shot, z_shot):
        # Repere cliche -> repere faisceau
        x_bundle = x_shot / self.focal * z_shot
        y_bundle = y_shot / self.focal * z_shot
        z_bundle = z_shot
        return x_bundle, y_bundle, z_bundle

    def image_to_shot(self, c, l):
        # Repere image -> repere cliche
        x_shot = c - self.x_ppa
        y_shot = l - self.y_ppa
        z_shot = np.full_like(x_shot, self.focal)
        return x_shot, y_shot, z_shot
    


    def bundle_to_local(self, x_bundle, y_bundle, z_bundle):
        # Repere faisceau -> repere local
        point_local = self.mat_eucli.T @ np.vstack([x_bundle, y_bundle, z_bundle]) + np.array(
            [self.x_pos_eucli, self.y_pos_eucli, self.z_pos_eucli]).reshape(-1, 1)
        return point_local[0], point_local[1], point_local[2]
    

        
    def convertback(self, data_type: type, *args: np.ndarray):
        # if inputs were lists, tuples or floats, convert back to original type.
        output = []
        for val in args:
            if data_type == list:
                output.append(val.tolist())
            elif data_type == np.ndarray:
                output.append(val)
            # elif data_type == pd.core.series.Series:
            #     output.append(val)
            else:
                output.append(val.item())
        if len(output) > 1:
            return *output,
        else:
            return output[0]
        

    
    
    def local_to_bundle(self, x_local, y_local, z_local):
        # Repere local euclidien -> repere faisceau
        point_bundle = self.mat_eucli @ np.vstack([x_local - self.x_pos_eucli, y_local - self.y_pos_eucli, z_local - self.z_pos_eucli])
        return point_bundle[0], point_bundle[1], point_bundle[2]
    

    def bundle_to_shot(self, x_bundle, y_bundle, z_bundle):
        # Repere faisceau -> repere cliche
        x_shot = x_bundle * self.focal / z_bundle
        y_shot = y_bundle * self.focal / z_bundle
        z_shot = z_bundle
        return x_shot, y_shot, z_shot

    def shot_to_image(self, x_shot, y_shot, _):
        # Repere cliche -> repere image
        c = x_shot + self.x_ppa
        l = y_shot + self.y_ppa
        return c, l
    
    def topaero_matrix(self, x: float, y:float) -> np.array:
        """
        Compute the transition matrix between the world system and the Euclidean system centred on a point.

        :param x: x coordinate of the central point of the Euclidean system
        :param y: y coordinate of the central point of the Euclidean system

        :return: transition matrix
        """
        lon, lat = self.carto_to_geog(x, y)
        gamma = self.get_meridian_convergence(x, y)

        # Matrice de passage en coordonnees cartesiennes locales
        sl = np.sin(lon * np.pi/180)
        sp = np.sin(lat * np.pi/180)
        sg = np.sin(gamma * np.pi/180)
        cl = np.cos(lon * np.pi/180)
        cp = np.cos(lat * np.pi/180)
        cg = np.cos(gamma * np.pi/180)
        rot_to_euclidean_local = np.zeros((3, 3))
        rot_to_euclidean_local[0, 0] = -cg * sl - sg * sp * cl
        rot_to_euclidean_local[0, 1] = cg * cl - sg * sp * sl
        rot_to_euclidean_local[0, 2] = sg * cp
        rot_to_euclidean_local[1, 0] = sg * sl - cg * sp * cl
        rot_to_euclidean_local[1, 1] = -sg * cl - cg * sp * sl
        rot_to_euclidean_local[1, 2] = cg * cp
        rot_to_euclidean_local[2, 0] = cp * cl
        rot_to_euclidean_local[2, 1] = cp * sl
        rot_to_euclidean_local[2, 2] = sp
        return rot_to_euclidean_local
    

    def get_sommet(self):
        return Point(self.x_pos, self.y_pos, self.z_pos[0])
    

    def get_meridian_convergence(self, x_carto, y_carto):
        """
            Compute meridian convergence.
            Values are extracted from pyproj.

            :param x_carto: x cartographic coordinates
            :param y_carto: y cartographic coordinates

            :return: meridian convergence in degree
        """
        x_geog, y_geog = self.carto_to_geog(x_carto, y_carto)
        proj = pyproj.Proj(self.crs)
        return -np.array(proj.get_factors(x_geog, y_geog).meridian_convergence)


class ShotOriente(Shot):
    def __init__(self):
        super().__init__()


    @staticmethod
    def createShot(cliche, focale, raf, centre_rep_local):
        shot = Shot()
        model = cliche.find(".//model")
        pt3d = model.find(".//pt3d")
        x = float(pt3d.find(".//x").text)
        y = float(pt3d.find(".//y").text)
        z = float(pt3d.find(".//z").text)
        shot.x_pos = x
        shot.y_pos = y
        shot.z_pos = z-raf.get(x, y)
        shot.sommet = [shot.x_pos, shot.y_pos, shot.z_pos]
        
        shot.x_central = centre_rep_local[0]
        shot.y_central = centre_rep_local[1]
        shot.z_central = 0

        

        nadir = cliche.find(".//nadir")
        pt3d = nadir.find(".//pt3d")
        x = float(pt3d.find(".//x").text)
        y = float(pt3d.find(".//y").text)
        z = float(pt3d.find(".//z").text)
        shot.x_nadir = x
        shot.y_nadir = y
        shot.z_nadir = z-raf.get(x, y)
        shot.rot_to_euclidean_local = shot.topaero_matrix(shot.x_central, shot.y_central)

        shot.image = cliche.find(".//image").text.strip()
        
        shot.x_ppa = focale[0]
        shot.y_ppa = focale[1]
        shot.focal = focale[2]

        shot.x_pos_eucli, shot.y_pos_eucli, shot.z_pos_eucli = shot.world_to_euclidean(shot.x_pos, shot.y_pos, shot.z_pos)

        

        quaternion = model.find(".//quaternion")
        x_q = float(quaternion.find(".//x").text)
        y_q = float(quaternion.find(".//y").text)
        z_q = float(quaternion.find(".//z").text)
        w_q = float(quaternion.find(".//w").text)
        q = np.array([x_q, y_q, z_q, w_q])
        shot.mat_eucli = shot.quaternion_to_mat_eucli(q)


        polygon2d = cliche.find(".//polygon2d")
        points_emprise_x = polygon2d.findall(".//x")
        points_emprise_y = polygon2d.findall(".//y")
        points = []
        for i in range(len(points_emprise_x)):
            points.append([float(points_emprise_x[i].text), float(points_emprise_y[i].text)])
        shot.emprise = Polygon(points)
        return shot

    def world_to_image(self, x_world, y_world, z_world):
            """
            Compute the image coordinates of a world point.
            This algorithm is slower but more accurate than :func:`world_to_image_approx`.

            :param x_world: x_world coordinates of the point
            :param y_world: y_world coordinates of the point
            :param z_world: z_world coordinates of the point

            :return: c, l Image coordinates
            """
            type_input = type(x_world)
            x_eucli, y_eucli, z_eucli = self.world_to_euclidean(x_world, y_world, z_world)
            x_bundle, y_bundle, z_bundle = self.local_to_bundle(x_eucli, y_eucli, z_eucli)
            x_shot, y_shot, z_shot = self.bundle_to_shot(x_bundle, y_bundle, z_bundle)
            c, l = self.shot_to_image(x_shot, y_shot, z_shot)
            return self.convertback(type_input, c, l)

    
    def image_to_world(self, c, l, dem, prec=0.1, iter_max=3, estim_z=0):
        """
        Compute the world coordinates of (a) image point(s).
        A Dem must be used.

        :param c: column coordinates of image point(s)
        :param l: line coordinates of image point(s)
        :param dem: Dem of the area or constant value
        :param prec: accuracy
        :param iter_max: maximum number of iterations

        Attention, la distorsion n'est pas corrigée ici !!! 

        :return: x, y, z World coordinates
        """
        # initialisation
        # passage en local en faisant l'approximation z "local" a partir du z "world"
        # La fonction calcule le x et y euclidien correspondant à une coordonnées image et un Z local
        
        type_input = type(c)

        z_world = dem.get(self.x_pos, self.y_pos) + estim_z
        
        z_world = np.full_like(c, z_world)
        x_local, y_local, z_local = self.image_z_to_local(c, l, z_world)
        # On a les coordonnées locales approchées (car z non local) on passe en world
        x_world, y_world, _ = self.euclidean_to_world(x_local, y_local, z_local)
        precision_reached = False
        nbr_iter = 0

        while not precision_reached and nbr_iter < iter_max:
            z_world = dem.get(x_world, y_world) + estim_z
            # On repasse en euclidien avec le bon Zworld , l'approximation plani ayant un impact minime
            x_local, y_local, z_local = self.world_to_euclidean(x_world, y_world, z_world)

            # nouvelle transfo avec un zLocal plus precis
            x_local, y_local, z_local = self.image_z_to_local(c, l, z_local)

            # passage en terrain (normalement le zw obtenu devrait être quasiment identique au Z initial)
            x_world_new, y_world_new, z_world_new = self.euclidean_to_world(x_local, y_local, z_local)

            dist = ((x_world_new - x_world) ** 2 + (y_world_new - y_world) ** 2 + (z_world_new - z_world) ** 2) ** 0.5
            if np.any(dist < prec):
                precision_reached = True
            x_world, y_world, z_world = x_world_new, y_world_new, z_world_new
            nbr_iter += 1

        return self.convertback(type_input, x_world, y_world, z_world)

    
    def quaternion_to_mat_eucli(self, q) -> np.array:
        """
        Transform quaternions into a rotation matrix (TOPAERO convention)

        :param q: quaternion
        :type q: np.array, list

        :return: rotation matrix
        :rtype: np.array
        """
        mat = R.from_quat(q).as_matrix()
        # passage en convention TOPAERO
        # axe Z dans l'autre sens donc *-1 sur la dernière colonne
        mat = mat*np.array([1, 1, -1])
        # Inversion des deux premières colonnes + transposition
        mat = mat[:, [1, 0, 2]].T
        return mat




class MNT:

    def __init__(self, path:str) -> None:
        self.dem = gdal.Open(path)
        self.gt = self.dem.GetGeoTransform()
        self.rb = self.dem.GetRasterBand(1)


    def world_to_image(self, x, y):
        """
            Compute image coordinates from world coordinates

            :param x: x world coordinate
            :param y: y world coordinate
            :return: image coordinates
        """
        c = (np.array(x) - self.gt[0])/self.gt[1]
        l = (np.array(y) - self.gt[3])/self.gt[5]
        return c, l

    def image_to_world(self, c, l):
        """
            Compute world coordinates from image coordinates

            :param c: column coordinates
            :param l: line coordinates
            :return: x, y world coordinates
        """
        x = np.array(c) * self.gt[1] + self.gt[0]
        y = np.array(l) * self.gt[5] + self.gt[3]
        return x, y


    def get(self, x, y):
        """
            Extract value in the Dem

            :param x: x world coordinate
            :param y: y world coordinate
            :return: z value.
        """
        try:
            xmin, ymin = np.min(x), np.min(y)
            xmax, ymax = np.max(x), np.max(y)
            imin, jmin = np.floor(self.world_to_image(xmin, ymax))
            imax, jmax = np.ceil(self.world_to_image(xmax, ymin))
            imin = int(min(max(imin, 0), self.dem.RasterXSize))
            imax = int(min(max(imax, 0), self.dem.RasterXSize - 1))
            jmin = int(min(max(jmin, 0), self.dem.RasterYSize))
            jmax = int(min(max(jmax, 0), self.dem.RasterYSize - 1))
            array = self.rb.ReadAsArray(imin, jmin, imax - imin + 1, jmax - jmin + 1)
            array = np.where(array==-99999.00, 0, array)
            xmin, ymax = self.image_to_world(imin, jmin)
            c = (x - xmin)/self.gt[1]
            l = (y - ymax)/self.gt[5]
            # Les points images sont en col lig mais les np.array sont en lig col
            z = ndimage.map_coordinates(array, np.vstack([l, c]), order=1, mode="constant")
            return z
        except:
            return None
        

class RAF:

    def __init__(self, path) -> None:
        self.raf = gdal.Open(path)
        self.gt = self.raf.GetGeoTransform()
        self.rb = self.raf.GetRasterBand(1)

    def get(self, x, y):
        array = self.raf.ReadAsArray()
        c = (x - self.gt[0]) / self.gt[1]
        l = (y - self.gt[3]) / self.gt[5]
        z = array[int(l), int(c)]
        return z
    


class Calibration:
    def __init__(self) -> None:
        pass

    
    @staticmethod
    def createCalibration(path):
        tree = etree.parse(path)
        root = tree.getroot()
        calibration = Calibration()
        calibration.setPP(root)
        calibration.setFocale(root)
        calibration.setSizeImage(root)
        calibration.setDistorsionCoeff(root)
        calibration.setDecentric(root)
        calibration.setAffine(root)
        return calibration

    def setPP(self, root):
        PP = root.find(".//PP").text
        self.PPX = float(PP.split()[0])
        self.PPY = float(PP.split()[1])

    def setFocale(self, root):
        focale = root.find(".//F").text
        self.focale = float(focale)

    def setSizeImage(self, root):
        sizeImage = root.find(".//SzIm").text
        self.sizeX = int(sizeImage.split()[0])
        self.sizeY = int(sizeImage.split()[1])

    def setDistorsionCoeff(self, root):
        distorsionCoefficient = []
        for coeffDist in root.getiterator("CoeffDist"):
            distorsionCoefficient.append(float(coeffDist.text))
        self.distorsionCoefficient = distorsionCoefficient

    def setDecentric(self, root):
        self.decentric_P1 = float(root.find(".//P1").text)
        self.decentric_P2 = float(root.find(".//P2").text)

    def setAffine(self, root):
        self.affine_b1 = float(root.find(".//b1").text)
        self.affine_b2 = float(root.find(".//b2").text)


class DistorsionCorrection:

    def __init__(self, calibration:Calibration) -> None:
        self.calibration = calibration

    def create_cc_ll(self):
        l = np.arange(self.calibration.sizeX)
        c = np.arange(self.calibration.sizeY)
        self.cc, self.ll = np.meshgrid(l, c)
        self.du = self.cc - self.calibration.PPX
        self.dv = self.ll - self.calibration.PPY
        self.rho = self.du**2 + self.dv**2

    def compute(self, c, l):
        self.du = c - self.calibration.PPX
        self.dv = l - self.calibration.PPY
        self.rho = self.du**2 + self.dv**2
        self.compute_Dr()
        self.computeDecentric()
        self.computeAffine()
        self.computeAll()
        return self.DPx, self.DPy
    

    def convertback(self, data_type: type, *args: np.ndarray):
        # if inputs were lists, tuples or floats, convert back to original type.
        output = []
        for val in args:
            if data_type == list:
                output.append(val.tolist())
            elif data_type == np.ndarray:
                output.append(val)
            # elif data_type == pd.core.series.Series:
            #     output.append(val)
            else:
                output.append(val.item())
        if len(output) > 1:
            return *output,
        else:
            return output[0]

    
    def compute_Dr(self):
        intermediaire = (1+self.calibration.distorsionCoefficient[0]*self.rho+self.calibration.distorsionCoefficient[1]*self.rho**2+self.calibration.distorsionCoefficient[2]*self.rho**3+self.calibration.distorsionCoefficient[3]*self.rho**4)
        self.drx = self.calibration.PPX + intermediaire * self.du
        self.dry = self.calibration.PPY + intermediaire * self.dv
        
    def computeDecentric(self):
        P1x = self.calibration.decentric_P1 * (2*self.du**2 + self.rho)
        P1y = self.calibration.decentric_P1 * 2*self.du *self.dv
        P2x = self.calibration.decentric_P2 * 2*self.du *self.dv
        P2y = self.calibration.decentric_P2 * (2*self.dv**2 + self.rho)
        self.decentricx = P1x + P2x
        self.decentricy = P1y + P2y
        
    def computeAffine(self):
        self.affine = self.calibration.affine_b1 * self.du + self.calibration.affine_b2 * self.dv

    def computeAll(self):
        self.DPx = self.drx + self.decentricx + self.affine
        self.DPy = self.dry + self.decentricy

    def compute_reverse(self, c0, l0):
        c = np.arange(np.min(c0)-10, np.max(c0)+10)
        l = np.arange(np.min(l0)-10, np.max(l0)+10)

        cc, ll = np.meshgrid(c, l)
        cc = cc.reshape((-1, 1))
        ll = ll.reshape((-1, 1))
        cc_cor, ll_cor = self.compute(cc, ll)
        points_cor = np.concatenate([cc_cor, ll_cor], axis=1)
        c_grid_data = LinearNDInterpolator(points_cor, cc)
        l_grid_data = LinearNDInterpolator(points_cor, ll)
        c_cor = c_grid_data(c0, l0)
        l_cor = l_grid_data(c0, l0)
        if c_cor.ndim==1:
            return c_cor, l_cor
        return c_cor[:,0], l_cor[:,0]



class ShotPompei(Shot):

    def __init__(self):
        super().__init__()


    @staticmethod
    def createShot(path, calibrations:List[Calibration]):
        shot = ShotPompei()
        tree = etree.parse(path)
        root = tree.getroot()

        centre = root.find(".//Centre").text
        x = float(centre.split()[0])
        y = float(centre.split()[1])
        z = float(centre.split()[2])

        shot.x_pos = x
        shot.y_pos = y
        shot.z_pos = np.array([z])
        shot.x_central = x
        shot.y_central = y
        shot.z_central = 0
        shot.rot_to_euclidean_local = shot.topaero_matrix(shot.x_central, shot.y_central)

        name = os.path.basename(path).replace(".tif.xml", "").replace("Orientation-", "")
        shot.image = name

        file_calib = os.path.basename(root.find(".//FileInterne").text)

        calibration = calibrations[file_calib]
        
        shot.calibration = calibration
        shot.x_ppa = calibration.PPX
        shot.y_ppa = calibration.PPY
        shot.focal = calibration.focale

        shot.x_pos_eucli, shot.y_pos_eucli, shot.z_pos_eucli = shot.world_to_euclidean(x, y, z)
        rotMatrice = np.zeros((3,3))
        L1 = root.find(".//L1").text
        rotMatrice[0,0] = float(L1.split()[0])
        rotMatrice[0,1] = float(L1.split()[1])
        rotMatrice[0,2] = float(L1.split()[2])
        L2 = root.find(".//L2").text
        rotMatrice[1,0] = float(L2.split()[0])
        rotMatrice[1,1] = float(L2.split()[1])
        rotMatrice[1,2] = float(L2.split()[2])
        L3 = root.find(".//L3").text
        rotMatrice[2,0] = float(L3.split()[0])
        rotMatrice[2,1] = float(L3.split()[1])
        rotMatrice[2,2] = float(L3.split()[2])
        shot.mat_eucli = rotMatrice.T

        shot.distorsion_correction = DistorsionCorrection(calibration)

        return shot
    
    def compute_emprise(self, mnt):
        limits = np.array([[0, 0], [self.calibration.sizeX, 0], [self.calibration.sizeX, self.calibration.sizeY], [0, self.calibration.sizeY]])
        points = []
        for i in range(limits.shape[0]):
            x, y, z = self.image_to_world(np.array([limits[i,0]]), np.array([limits[i,1]]), mnt)
            points.append([x[0], y[0]])
        self.emprise = Polygon(points)



    def world_to_image(self, x_world, y_world, z_world):
            """
            Compute the image coordinates of a world point.
            This algorithm is slower but more accurate than :func:`world_to_image_approx`.

            :param x_world: x_world coordinates of the point
            :param y_world: y_world coordinates of the point
            :param z_world: z_world coordinates of the point

            :return: c, l Image coordinates
            """
            type_input = type(x_world)
            x_bundle, y_bundle, z_bundle = self.local_to_bundle(x_world, y_world, z_world)
            x_shot, y_shot, z_shot = self.bundle_to_shot(x_bundle, y_bundle, z_bundle)
            c, l = self.shot_to_image(x_shot, y_shot, z_shot)
            c, l = self.distorsion_correction.compute(c, l)
            return self.convertback(type_input, c, l)

    
    def image_to_world(self, c, l, dem, prec=0.1, iter_max=3, estim_z=0):
        """
        Compute the world coordinates of (a) image point(s).
        A Dem must be used.

        :param c: column coordinates of image point(s)
        :param l: line coordinates of image point(s)
        :param dem: Dem of the area or constant value
        :param prec: accuracy
        :param iter_max: maximum number of iterations

        Attention, la distorsion n'est pas corrigée ici !!! 

        :return: x, y, z World coordinates
        """
        # initialisation
        # passage en local en faisant l'approximation z "local" a partir du z "world"
        # La fonction calcule le x et y euclidien correspondant à une coordonnées image et un Z local
        type_input = type(c)

        z_world = dem.get(self.x_pos, self.y_pos) + estim_z
        z_world = np.full_like(c, z_world)

        c, l = self.distorsion_correction.compute_reverse(c, l)

        x_local, y_local, z_local = self.image_z_to_local(c, l, z_world)
        # On a les coordonnées locales approchées (car z non local) on passe en world
        x_world, y_world, _ = self.euclidean_to_world(x_local, y_local, z_local)
        precision_reached = False
        nbr_iter = 0

        while not precision_reached and nbr_iter < iter_max:
            z_world = dem.get(x_world, y_world) + estim_z
            # On repasse en euclidien avec le bon Zworld , l'approximation plani ayant un impact minime
            x_local, y_local, z_local = self.world_to_euclidean(x_world, y_world, z_world)
            # nouvelle transfo avec un zLocal plus precis
            x_local, y_local, z_local = self.image_z_to_local(c, l, z_local)
            # passage en terrain (normalement le zw obtenu devrait être quasiment identique au Z initial)
            x_world_new, y_world_new, z_world_new = self.euclidean_to_world(x_local, y_local, z_local)

            dist = ((x_world_new - x_world) ** 2 + (y_world_new - y_world) ** 2 + (z_world_new - z_world) ** 2) ** 0.5
            if np.any(dist < prec):
                precision_reached = True
            x_world, y_world, z_world = x_world_new, y_world_new, z_world_new
            nbr_iter += 1

        return self.convertback(type_input, x_world, y_world, z_world)


