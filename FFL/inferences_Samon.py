""" .
"""
import os
import json
import time
import argparse
import fiona
import numpy as np
import rasterio
import torch
import shapely

from itertools import pairwise, compress, chain
from tqdm import tqdm
from jsmin import jsmin
from rasterio import windows
from shapely import geometry
from affine import Affine

from typing import List
from backbone import get_backbone
from frame_field_learning import data_transforms
from frame_field_learning.model import FrameFieldModel
from frame_field_learning import inference, polygonize
from frame_field_learning import local_utils
from torch_lydorn import torchvision
from shapely import Polygon

import geopandas as gpd
from pathlib import Path



def split_img_tiles_save(height, width, tile_size, overlap):
    """ docstring"""
    offset = tile_size - overlap

    tiles_windows_list = []
    nb = 1
    offsets_h = []
    polygons = []
    for offset_height in range(0, height - tile_size + offset - 1, offset):
        offsets_w = []
        for offset_width in range(0, width - tile_size + offset - 1, offset):
            if offset_width > width - tile_size:
                offset_width = width - tile_size
            if offset_height > height - tile_size:
                offset_height = height - tile_size
            polygons.append(Polygon.from_bounds(offset_width, -(offset_height+tile_size), offset_width+tile_size, -offset_height))
            window = windows.Window(offset_width, offset_height, tile_size, tile_size)
            tiles_windows_list.append(window)
            nb += 1
            offsets_w.append(offset_width)
        offsets_h.append(offset_height)

    return tiles_windows_list, offsets_w, offsets_h, polygons



def split_img_tiles(height, width, emprises:List[Polygon]):
    """ docstring"""

    tiles_windows_list = []
    for emprise in emprises:
        minx, min_y, maxx, max_y = emprise.bounds
        miny = -max_y
        maxy = -min_y
        delta_x_max = width-minx
        delta_y_max = height-miny
        tiles_windows_list.append(windows.Window(max(0,minx), max(0,miny), min(delta_x_max, maxx-minx), min(delta_y_max, maxy-miny)))
    return tiles_windows_list


def load_model(run_dirpath, backbone, config):
    """ docstring"""
    # --- Online transform performed on the device (GPU):
    eval_online_cuda_transform = data_transforms.get_eval_online_cuda_transform(config)
    # load model
    print("Loading model...")
    model = FrameFieldModel(config, backbone=backbone, eval_transform=eval_online_cuda_transform)
    model.to(config["device"])
    checkpoints_dirpath = os.path.join(run_dirpath, "checkpoints")
    model = inference.load_checkpoint(model, checkpoints_dirpath, config["device"])
    model.eval()
    return model


def inf_unet_tile(image, model, config, window):
    """ docstring"""
    image_float = image / 255
    mean = np.mean(image_float.reshape(-1, image_float.shape[-1]), axis=0)
    std = np.std(image_float.reshape(-1, image_float.shape[-1]), axis=0)
    sample = {
        "image": torchvision.transforms.functional.to_tensor(image)[None, ...],
        "image_mean": torch.from_numpy(mean)[None, ...],
        "image_std": torch.from_numpy(std)[None, ...],
        "image_filepath": "a",
    }
    if config["eval_params"]["patch_size"] is not None:
        # Cut image into patches for inference
        inference.inference_with_patching(config, model, sample)
    else:
        # Feed images as-is to the model
        inference.inference_no_patching(config, model, sample)

    # Polygonize:
    crossfield = sample["crossfield"] if "crossfield" in sample else None
    polygons_batch, probs_batch = polygonize.polygonize(config["polygonize_params"], sample["seg"], crossfield_batch=crossfield,
                                        pool=None)
    tile_data = {}
    tile_data["polygons"] = polygons_batch
    tile_data["polygon_probs"] = probs_batch
    if tile_data["polygons"][0]["asm"]:
        polygons = []
        for polygon in tile_data["polygons"][0]["asm"]["tol_1"]:
            #polygons.append(polygon)
            polygons.append(shapely.affinity.translate(polygon, window.col_off, window.row_off))
    else:
        polygons = tile_data["polygons"][0]["asm"]
    return polygons


def get_zones_filtrage(width_tile_bounds, height_tile_bounds, overlap, dalle_width, dalle_height):
    """ docstring"""
    width_tile_bounds.append(dalle_width)
    height_tile_bounds.append(dalle_height)
    width_tile_bounds = list(pairwise(width_tile_bounds))
    height_tile_bounds = list(pairwise(height_tile_bounds))

    width_filtrage_bounds = []
    for i, _ in enumerate(width_tile_bounds):
        inf = int(width_tile_bounds[i][0] + overlap / 2)
        sup = int(width_tile_bounds[i][1] + overlap / 2)
        width_filtrage_bounds.append([inf, sup])
    width_filtrage_bounds[0][0] = 0
    width_filtrage_bounds[-1][1] = dalle_width
    height_filtrage_bounds = []
    for i, _ in enumerate(height_tile_bounds):
        inf = int(height_tile_bounds[i][0] + overlap / 2)
        sup = int(height_tile_bounds[i][1] + overlap / 2)
        height_filtrage_bounds.append([inf, sup])
    height_filtrage_bounds[0][0] = 0
    height_filtrage_bounds[-1][1] = dalle_height

    polygons = []
    for px in height_filtrage_bounds:
        for py in width_filtrage_bounds:
            window = windows.Window(py[0], px[0], py[1] - py[0], px[1] - px[0])
            bbox = (
                window.col_off,
                window.row_off,
                window.col_off + window.width,
                window.row_off + window.height
            )
            polygons.append(geometry.box(*bbox, ccw=True))
    return polygons


def filtrage_ss_dalle(ss_dalle_pred, zone_filtrage):
    """ docstring"""
    centroids = [x.centroid for x in ss_dalle_pred]

    within_ = [x.within(zone_filtrage) for x in centroids]
    within_ = [True for x in centroids]
    ss_dalle_filtered = list(compress(ss_dalle_pred,within_))
    return ss_dalle_filtered


def filtrage_dalle(zones_filtrage, polygons_list):
    """ docstring"""
    print("Filtering polygons...")
    preds_filtered = []
    for polygons, zone_filtrage in zip(polygons_list, zones_filtrage):
        ss_dalle_filtered = filtrage_ss_dalle(polygons, zone_filtrage)
        preds_filtered.append(ss_dalle_filtered)
    return list(chain(*preds_filtered))


def main(config, backbone, run_dirpath, img_path, out_dirpath, emprises_dir):
    """ docstring"""
    t = time.time()
    tile_size = 5000
    overlap = 1000
    model = load_model(run_dirpath, backbone, config)

    emprises = [i for i in os.listdir(emprises_dir) if i[-5:]==".gpkg"]

    for emprise in tqdm(emprises, desc="Prédiction sur chaque image orientée", total=len(emprises)):
        img = img_path/emprise.replace(".gpkg", ".jp2")

        emprise_geom = gpd.read_file(emprises_dir/emprise)

        with rasterio.open(img) as src:
            height, width = src.height, src.width
            #wins, offsets_w, offsets_h, polygons = split_img_tiles(height, width, emprise_geom["geometry"])
            wins = split_img_tiles(height, width, emprise_geom["geometry"])
            
            inf = []
            for window in tqdm(wins, desc="running model on tiles..."):
                tile = src.read([1, 2, 3], window=window).swapaxes(0, 2).swapaxes(0, 1)
                inf.append(inf_unet_tile(tile, model, config, window))

            if src.transform == Affine.identity():  # image non géoréférencée
                raster_proj = lambda x, y: src.transform * (x, -y)
            else:
                raster_proj = lambda x, y: src.transform * (x, y)

        #zones_filtrage = get_zones_filtrage(offsets_w, offsets_h, overlap, width, height)
        #assert len(inf) == len(zones_filtrage)
        #res = filtrage_dalle(zones_filtrage, inf)
        res = []
        for element in inf:
            res+=element
        schema = {
        'geometry': 'Polygon',
        'properties': {'id': 'int'},
        }

        file_name = os.path.basename(img).split(".")[0]
        print("Prédiciton sauvegardée : ", os.path.join(out_dirpath, file_name + ".shp"))
        with fiona.open(
            os.path.join(out_dirpath, file_name + ".shp"),
            'w', driver='ESRI Shapefile',
            schema=schema,
            crs=fiona.crs.from_epsg(2154)
            ) as c:
            for id_, polygon in enumerate(res):
                raster_polygon = shapely.ops.transform(raster_proj, polygon)
                wkt_polygon = shapely.geometry.mapping(raster_polygon)
                c.write({
                    'geometry': wkt_polygon,
                    'properties': {'id': id_},
                })
    print(time.time() - t)


def get_args():
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument(
        '--pvas_filepath',
        type=str,
        required=True,
        help='Répertoire contenant les pvas')

    argparser.add_argument(
        '--out_dirpath',
        type=str,
        required=True,
        help='Path to the output directory of prediction(s).')
    
    argparser.add_argument(
        '--emprises',
        type=str,
        required=True,
        help='Emprises sur les pvas.')

    argparser.add_argument(
        '--run_name',
        type=str,
        required=True,
        help='Name of the run to use.'
             'That name does not include\
                the timestamp of the folder name: <run_name> | <yyyy-mm-dd hh:mm:ss>.')

    return argparser.parse_args()


if __name__ == '__main__':

    args = get_args()

    run_dirpath = local_utils.get_run_dirpath("runs", args.run_name)

    config_filepath = os.path.join(run_dirpath, "config.json")
    with open(config_filepath, 'r', encoding="utf-8") as f:
        minified = jsmin(f.read())
    config = json.loads(minified)

    backbone = get_backbone(config["backbone_params"])

    main(config, backbone, run_dirpath, Path(args.pvas_filepath), args.out_dirpath, Path(args.emprises))
