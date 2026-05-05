from v2.shot import ShotOriente, RAF
import argparse
from lxml import etree
from pyproj import CRS, Transformer
import geopandas as gpd
import requests
import json
from shapely import Point, Polygon
from pathlib import Path
import os
from tqdm import tqdm


def convert_emprise_2d_to_3d(emprise):
    crs_4326 = CRS.from_epsg(4326)
    crs_2154 = CRS.from_epsg(2154)
    transformer = Transformer.from_crs(crs_2154, crs_4326)

    geometries = emprise["geometry"]
    geometries_3d = []
    for geometry in geometries:
        points = []
        exterior_points = list(geometry.exterior.coords)
        for exterior_point in exterior_points:
            lat, lon = transformer.transform(exterior_point[0],exterior_point[1])
            url = f"https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json?lon={lon}&lat={lat}&resource=ign_rge_alti_wld&measures=false&zonly=true"
            response = requests.get(url)
            if response.status_code==200:
                z = float(json.loads(response.text)["elevations"][0])
            else:
                raise ValueError
            points.append(Point(exterior_point[0],exterior_point[1], z))
        geometries_3d.append(Polygon(points))
    return geometries_3d



def run(input_ta, emprise, output_dir, raf_path):

    os.makedirs(output_dir, exist_ok=True)

    emprise = gpd.read_file(emprise)

    emprise = convert_emprise_2d_to_3d(emprise)

    raf = RAF(raf_path)
    tree = etree.parse(input_ta)
    root = tree.getroot()
    centre_rep_local = root.find(".//centre_rep_local")
    centre_rep_local_x = float(centre_rep_local.find(".//x").text)
    centre_rep_local_y = float(centre_rep_local.find(".//y").text)
    centre_rep_local = [centre_rep_local_x, centre_rep_local_y]
    
    for vol in root.getiterator("vol"):
        sensors = vol.findall(".//sensor")
        for cliche in tqdm(vol.getiterator("cliche")):
            shot = ShotOriente.createShot(cliche, raf, centre_rep_local, sensors)
            

            geometries_image = []
            for geometry in emprise:
                geom = shot.polygon_ground_to_image(geometry)
                if geom.intersects(shot.poly_widht_height):
                    geometries_image.append(geom)
            
            if len(geometries_image)>0:
                gdf = gpd.GeoDataFrame({"geometry":geometries_image})
                gdf.to_file(output_dir/f"{shot.image}.gpkg")



if __name__=="__main__":
    parser = argparse.ArgumentParser(description="A partir d'emprises 2D, crée les emprises sur images orientées où appliquer le FFL")
    parser.add_argument('--input_ta', help="Tableau d'assemblage du département")
    parser.add_argument('--raf_path', help="Tableau d'assemblage du département")
    parser.add_argument('--emprise', help='Emprise au sol des zones où il faut reconstruire les bâtiments')
    parser.add_argument('--output_dir', help='Répertoire où sauvegarder les emprises images')
    args = parser.parse_args()

    run(Path(args.input_ta), args.emprise, Path(args.output_dir), args.raf_path)