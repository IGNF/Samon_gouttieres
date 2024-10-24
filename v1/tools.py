import os
import shapely
from lxml import etree
from shot import Shot

def get_mnt(repertoire):
    fichier = [i for i in os.listdir(repertoire) if i[-4:]==".vrt"]
    return os.path.join(repertoire, fichier[0])

def get_raf(repertoire):
    fichier = [i for i in os.listdir(repertoire) if i[-4:]==".tif"]
    return os.path.join(repertoire, fichier[0])

def get_ta_xml(repertoire):
    fichier = [i for i in os.listdir(repertoire) if i[-4:]==".XML"]
    return os.path.join(repertoire, fichier[0])



def make_valid(polygon):
    polygon = shapely.make_valid(polygon)
    if isinstance(polygon, shapely.MultiPolygon):
        polygones = []
        for p in list(polygon.geoms):
            polygones.append(p)
    elif isinstance(polygon, shapely.Polygon):
        polygones = [polygon]
    elif isinstance(polygon, shapely.LineString):
        polygones = []
    elif isinstance(polygon, shapely.GeometryCollection):
        polygones = []
        for p in list(polygon.geoms):
            if isinstance(p, shapely.Polygon):
                polygones.append(p)
    else:
        print("cas non traité : ", polygon)
        polygones = []
    return polygones


def getFocale(root):
    focal = root.find(".//focal")
    focale_x = float(focal.find(".//x").text)
    focale_y = float(focal.find(".//y").text)
    focale_z = float(focal.find(".//z").text)
    return [focale_x, focale_y, focale_z]


def get_centre_rep_local(root):
    centre_rep_local = root.find(".//centre_rep_local")
    centre_rep_local_x = float(centre_rep_local.find(".//x").text)
    centre_rep_local_y = float(centre_rep_local.find(".//y").text)
    return [centre_rep_local_x, centre_rep_local_y]


def get_shots(ta_xml, pvas_dir, raf):
    tree = etree.parse(ta_xml)
    root = tree.getroot()
    centre_rep_local = get_centre_rep_local(root)
    pvas = [i.split(".")[0] for i in os.listdir(pvas_dir)]
    shots = []
    for vol in root.getiterator("vol"):
        focale = getFocale(vol)
        for cliche in vol.getiterator("cliche"):
            image = cliche.find("image").text.strip()
            if image in pvas:
                shot = Shot.createShot(cliche, focale, raf, centre_rep_local)
                shots.append(shot)
    return shots