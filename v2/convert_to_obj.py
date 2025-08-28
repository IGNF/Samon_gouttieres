import geopandas as gpd
from shot import MNT
from tqdm import tqdm
import argparse
import os



parser = argparse.ArgumentParser(description="Convertit le résultat de l'algorithme en fichier obj")
parser.add_argument('--input', help='Répertoire du chantier')
args = parser.parse_args()


input_gpkg = os.path.join(args.input, "gouttieres/batiments_fermes/batiments_fermes.gpkg")
mnt_path = os.path.join(args.input, "mnt/mnt.vrt")


class Point:

    identifiant = 1

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.identifiant = Point.identifiant
        Point.identifiant += 1

    def __str__(self):
        return f"({self.x}, {self.y}, {self.z})"


class Face:

    def __init__(self, points):
        self.points = points


def get_or_create(liste_points, x, y, z):
    for p in liste_points:
        if p.x==x and p.y==y and p.z==z:
            return liste_points, p
    new_p = Point(x, y, z)
    liste_points.append(new_p)
    return liste_points, new_p


mnt = MNT(mnt_path)
gdf = gpd.read_file(input_gpkg)


liste_points = []
liste_faces = []

for i in tqdm(range(gdf.shape[0])):
    geometry = gdf.iloc[i]["geometry"]
    points = list(geometry.exterior.coords)
    list_z_1 = []
    for j in range(len(points)-1):
        list_z_1.append(points[j][2])
    z_mean_1 = sum(list_z_1)/len(list_z_1)


    list_z_0 = []
    for j in range(len(points)-1):
        list_z_0.append(mnt.get(points[j][0], points[j][1])[0])
    z_mean_0 = sum(list_z_0)/len(list_z_0)


    for j in range(len(points)-1):
        liste_points, p1 = get_or_create(liste_points, points[j][0], points[j][1], z_mean_1)
        liste_points, p2 = get_or_create(liste_points, points[j+1][0], points[j+1][1], z_mean_1)
        liste_points, p3 = get_or_create(liste_points, p1.x, p1.y, z_mean_0)
        liste_points, p4 = get_or_create(liste_points, p2.x, p2.y, z_mean_0)
        liste_faces.append(Face([p1, p2, p4, p3]))

    points_hauts = []
    for j in range(len(points)-1):
        liste_points, p = get_or_create(liste_points, points[j][0], points[j][1], z_mean_1)
        points_hauts.append(p)
    liste_faces.append(Face(points_hauts))




    
    
with open(os.path.join(args.input, "reconstruction_lod_1.1.obj"), "w") as f:
    for p in liste_points:
        f.write(f"v {p.x} {p.y} {p.z}\n")

    for face in liste_faces:
        string = ""
        for point in face.points:
            string += f" {point.identifiant} "
        f.write(f"f {string}\n")
    
print("Fichier créé : ", os.path.join(args.input, "reconstruction_lod_1.1.obj"))
