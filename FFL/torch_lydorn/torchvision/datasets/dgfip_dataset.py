import os
import pathlib
import json
import torch
import skimage
import shapely
import random
from functools import partial

from fnmatch import filter

import rasterio
import numpy as np
import multiprocessing

from tqdm import tqdm
from typing import Any
from torch.utils.data import Dataset
from lydorn_utils import python_utils
from lydorn_utils import python_utils

from lydorn_utils import run_utils, image_utils, polygon_utils, geo_utils


def load_json(filepath: str) -> Any:
    """Load JSON file."""
    if not os.path.exists(filepath):
        raise ValueError(f'{filepath} does not exist.')
    try:
        with open(filepath) as f:
            data = json.loads(f.read())
    except json.decoder.JSONDecodeError as e:
        print(f'ERROR in load_json(filepath): {e} from JSON at {filepath}')
        exit()
    return data

IMAGE_DIRNAME = 'images'
LABEL_DIRNAME = 'gt_dirname'
IMAGE_NAME_FORMAT = '{name}{part}'
IMAGE_FILENAME_FORMAT = IMAGE_NAME_FORMAT + '.jp2'

METADATA_DICT = { 'mean': np.array([0.40921639, 0.43360005, 0.4007581 ]),
                  'std': np.array( [0.17288009, 0.1491856, 0.14488205]) }

class DgfipDataset(Dataset):
    def __init__(self, root, fold, pre_process, patch_size, pre_transform, transform, pool_size, patch_stride, raw_dirname: str = "raw",
                 processed_dirname: str = "processed"):
        """
        @param root:
        @param fold:
        @param pre_process: If True, the dataset will be pre-processed first, saving training patches on disk. If False, data will be serve on-the-fly without any patching.
        @param patch_size:
        @param pre_transform:
        @param transform:
        @param pool_size:
        @param processed_dirname:
        """
        self.root = root
        self.fold = fold
        self.pre_process = pre_process
        self.patch_size = patch_size
        self.patch_stride = patch_stride
        self.pre_transform = pre_transform
        self.transform = transform
        self.pool_size = pool_size
        self.raw_dirname = raw_dirname
        self.gt_dirname: str = 'gt_polygons',

        if self.pre_process:
            # Setup of pre-process
            self.processed_dirpath = os.path.join(self.root, processed_dirname, self.fold)
            stats_filepath = os.path.join(self.processed_dirpath, "stats.pt")
            processed_relative_paths_filepath = os.path.join(self.processed_dirpath, "processed_paths.json")

            tile_info_list = self.get_tile_info_list()
            print(tile_info_list)

            self.process(tile_info_list, stats_filepath)

            # Save processed_relative_paths
            self.processed_relative_paths = [tile_info["processed_relative_filepath"] for tile_info in tile_info_list]
            python_utils.save_json(processed_relative_paths_filepath, self.processed_relative_paths)
        else:
            # Setup data sample list
            self.tile_info_list = self.get_tile_info_list()


    def get_tile_info_list(self):
        tile_info_list = []
        fold_dirpath = os.path.join(self.root, self.raw_dirname, self.fold)
        images_dirpath = os.path.join(fold_dirpath, IMAGE_DIRNAME)
        image_filenames = os.listdir(images_dirpath)
        image_filenames = sorted(image_filenames)
        for image_filename in image_filenames:
            name_split = image_filename.split("_")
            name = name_split[0]
            part = int(name_split[1].split(".")[0])
            tile_info = {
                "name": name,
                "part": part,
                "image_filepath": os.path.join(fold_dirpath, IMAGE_DIRNAME, f"{name}_{part:02d}.tif"),
                "label_filepath": os.path.join(fold_dirpath, LABEL_DIRNAME, f"{name}_{part:02d}.geojson"), # ne marchera pas pour les json avec plusieurs parties
                "processed_relative_filepath": os.path.join(name, f"{part:08d}.pt")
            }
            tile_info_list.append(tile_info)
        return tile_info_list
    

    def load_raw_data(self, tile_info):
        raw_data: dict[str, Any] = {}

        # Image:
        raw_data['image_filepath'] = tile_info["image_filepath"]
        raw_data['image'] = rasterio.open(raw_data['image_filepath']).read()[:3, :, :]
        raw_data['image'] = np.moveaxis(raw_data['image'], 0, -1)

        if len(raw_data['image'].shape) != 3 or raw_data['image'].shape[2] != 3:
            raise ValueError(f'image should have shape (H, W, 3), not {raw_data["image"].shape}...')

        # Annotations
        gt_filepath = tile_info["label_filepath"]
        if not os.path.exists(gt_filepath):
            raw_data['gt_polygons'] = []
            return raw_data
        else:
            geojson = load_json(gt_filepath)
            try:
                raw_data['gt_polygons'] = list(shapely.geometry.shape(geojson))
            except Exception:
                raw_data['gt_polygons'] = [
                    shapely.geometry.shape(feature['geometry']) for feature in geojson['features']
                ]
            
        return raw_data
    


    def _process_one(self, tile_info):
        process_id = int(multiprocessing.current_process().name[-1])

        # --- Init
        tile_name = IMAGE_NAME_FORMAT.format(name=tile_info["name"], part=tile_info["part"])
        processed_tile_relative_dirpath = os.path.join(tile_info['name'])#, f"{tile_info['part']:02d}")
        processed_tile_dirpath = os.path.join(self.processed_dirpath, processed_tile_relative_dirpath)
        processed_flag_filepath = os.path.join(processed_tile_dirpath, "processed_flag")
        stats_filepath = os.path.join(processed_tile_dirpath, "stats.pt")
        os.makedirs(processed_tile_dirpath, exist_ok=True)
        stats = {}

        # --- Check if tile has been processed already
        if os.path.exists(processed_flag_filepath):
            stats = torch.load(stats_filepath)
            return stats

        # --- Read data:
        raw_data = self.load_raw_data(tile_info)


        # --- Patch tiles

        patch_stride = self.patch_stride if self.patch_stride is not None else self.patch_size
        patch_boundingboxes = image_utils.compute_patch_boundingboxes(raw_data["image"].shape[0:2],
                                                                        stride=patch_stride,
                                                                        patch_res=self.patch_size)
    
        for i, bbox in enumerate(tqdm(patch_boundingboxes, desc=f"Patching {tile_name}", leave=False, position=process_id)):
            sample = {
                "image_filepath": raw_data["image_filepath"],
                "name": f"{tile_name}.rowmin_{bbox[0]}_colmin_{bbox[1]}_rowmax_{bbox[2]}_colmax_{bbox[3]}",
                "bbox": bbox,
                "part": tile_info["part"],
            }

            patch_gt_polygons = polygon_utils.patch_polygons(raw_data["gt_polygons"], minx=bbox[1], miny=bbox[0],
                                                                maxx=bbox[3], maxy=bbox[2])
            sample["gt_polygons"] = patch_gt_polygons

            sample["image"] = raw_data["image"][bbox[0]:bbox[2], bbox[1]:bbox[3], :]

            sample = self.pre_transform(sample)  # Needs "image" to infer shape even if mask_only is True
            
            # TODO: BESOIN DE CLASS FREQ ICI
            #comment avoir les classes à partir de patch_gt_polygons ? pour obtenir class_freq  
            relative_filepath = os.path.join(processed_tile_relative_dirpath, "{:08d}.pt".format(i))
            filepath = os.path.join(self.processed_dirpath, relative_filepath)
            torch.save(sample, filepath)

        return "a"


    def process(self, tile_info_list, stats_filepath):


        with multiprocessing.Pool(self.pool_size) as p:
            sample_stats_list = list(tqdm(p.imap(self._process_one, tile_info_list), total=len(tile_info_list)))


    def __getitem__(self, idx):

        if self.pre_process:
            filepath = os.path.join(self.processed_dirpath, self.processed_relative_paths[idx])
            data = torch.load(filepath)
            # data["image_mean"] = self.stats["mean"][data["name"]]
            # data["image_std"] = self.stats["std"][data["name"]]
            # data["class_freq"] = self.stats["class_freq"]
        else:
            tile_info = self.tile_info_list[idx]
            # Load raw data
            data = self.load_raw_data(tile_info)
            raise NotImplementedError("Need to implement mean and std computation")

        # --- Crop to path_size
        height, width, _ = data["image"].shape
        pre_crop_image_norm = data["image"].shape[0] + data["image"].shape[1]
        crop_i = random.randint(0, height - self.patch_size)
        crop_j = random.randint(0, width - self.patch_size)
        data["image"] = data["image"][crop_i:crop_i + self.patch_size, crop_j:crop_j + self.patch_size]
        data["gt_polygons_image"] = data["gt_polygons_image"][crop_i:crop_i + self.patch_size, crop_j:crop_j + self.patch_size]
        data["gt_crossfield_angle"] = data["gt_crossfield_angle"][crop_i:crop_i + self.patch_size, crop_j:crop_j + self.patch_size]
        data["distances"] = data["distances"][crop_i:crop_i + self.patch_size, crop_j:crop_j + self.patch_size]
        data["sizes"] = data["sizes"][crop_i:crop_i + self.patch_size, crop_j:crop_j + self.patch_size]
        post_crop_image_norm = data["image"].shape[0] + data["image"].shape[1]
        # Sizes and distances are affected by cropping because they are relative to the image's norm (height + width).
        # All non-one pixels have to be renormalized:
        size_ratio = pre_crop_image_norm / post_crop_image_norm
        data["distances"][data["distances"] != 1] *= size_ratio
        data["sizes"][data["sizes"] != 1] *= size_ratio
        data["image_mean"] = METADATA_DICT['mean']
        data["image_std"] = METADATA_DICT['std']
        # ---

        print(data.keys())

        data = self.transform(data) # la on a besoin de stats
        return data
    

    def __len__(self):
        if self.pre_process:
            return len(self.processed_relative_paths)
        else:
            return len(self.tile_info_list)
