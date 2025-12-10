import geopandas
from shapely.geometry import  Point
from osgeo import ogr
from osgeo import osr
import os
import requests
import argparse

import logging
import time



def download_data_BDTopo(bbox, layer):

    type_data = "BD_Topo"
    wfs_url = "https://data.geopf.fr/wfs/ows"

   

    #Le service WFS de l'IGN ne fournit pas plus de 1000 objets, donc il est nécessaire de diviser la surface en dalles, ici de 1 km de côté. Il manquera peut-être quelques bâtiments dans des zones très denses en bati, mais cela devrait permettre d'en récupérer assez
    #Pour voir les contraintes sur les requêtes wfs :
    #https://wxs.ign.fr/ortho/geoportail/r/wfs?SERVICE=WMS&REQUEST=GetCapabilities
    emin, nmin, emax, nmax = bbox

    #Les positions des sommets de prises de vue sont approximatives, donc il faut ajouter une marge
    emin -= 500
    nmin -= 500
    emax += 500
    nmax += 500

    liste_e = [e for e in range(int(emin), int(emax), 1000)]
    liste_e.append(emax)

    liste_n = [n for n in range(int(nmin), int(nmax), 1000)]
    liste_n.append(nmax)

    for i in range(len(liste_e) - 1):
        e_min_dalle = liste_e[i]
        e_max_dalle = liste_e[i+1]
        for j in range(len(liste_n) - 1):
            n_min_dalle = liste_n[j]
            n_max_dalle = liste_n[j+1]

            #Curieusement, il semble qu'il n'y ait pas moyen de récupérer les coordonnées en 2154, mais on peut quand même définir la bounding box en 2154
            bbox_string = "{},{},{},{},EPSG:{}".format(e_min_dalle, n_min_dalle, e_max_dalle, n_max_dalle, EPSG).strip()
            
            
            r = None
            try:
                r = requests.get(wfs_url, params={
                    'service': 'WFS',
                    'version': '2.0.0',
                    'request': 'GetFeature',
                    'resultType': 'results',
                    'typename': layer,
                    'bbox': bbox_string,
                    'outputFormat': 'application/json'
                })
            
            except requests.exceptions.RequestException as e:
                time.sleep(10)
                try:
                    r = requests.get(wfs_url, params={
                        'service': 'WFS',
                        'version': '2.0.0',
                        'request': 'GetFeature',
                        'resultType': 'results',
                        'typename': layer,
                        'bbox': bbox_string,
                        'outputFormat': 'application/json'
                    })
                except:
                    pass



            if r is not None and r.status_code==200:
                #On sauvegarde dans un fichier json les dalles
                chemin4326 = os.path.join('{}_dalle_{}_{}.GeoJSON'.format(type_data, i, j))
                with open(chemin4326, 'wb') as f:
                    f.write(bytes(r.content))

EPSG = 2154
layer = 'BDTOPO_V3:batiment'
bbox = [429500,6678000, 462900, 6706700]
download_data_BDTopo(bbox, layer)