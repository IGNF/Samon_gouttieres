
import os
import json
import time
import argparse
import fiona
from jsmin import jsmin
import numpy as np
import rasterio
import torch
import scipy

import shapely

from tqdm import tqdm
from rasterio import windows

#from backbone import get_backbone

from frame_field_learning import data_transforms
from frame_field_learning.model import FrameFieldModel
from frame_field_learning import inference
from frame_field_learning import local_utils
from frame_field_learning import polygonize


from torchvision.models.segmentation._utils import _SimpleSegmentationModel
from frame_field_learning.unet_resnet import UNetResNetBackbone




from torch_lydorn import torchvision


# def load_crossfields(cf_path="outputs/0_test/crossfield/6original.npy"):
#     cf = np.load(cf_path)
#     cf = torch.from_numpy(cf)
#     cf = torch.unsqueeze(cf, 0)
#     return cf


# def load_seg(seg_path = "outputs/0_test/seg/6.npy", eroded=False):
#     seg = np.load(seg_path)

#     if eroded:
#         # erosion ?
#         j = 5
#         cross = np.array([[0,j,0],
#                     [j,j,j],
#                     [0,j,0]])
        
        
#         eroded_seg = seg

#         eroded_seg[0, :, :] = erosion(seg[0, :, :], cross)
#         eroded_seg[1, :, :] = erosion(seg[1, :, :], cross)

#         seg = eroded_seg


#     seg = torch.from_numpy(seg)
#     seg = torch.unsqueeze(seg, 0)
#     return seg

# def save_crossfield():
#     pass

# def save_seg():
#     pass


def split_img_tiles(height, width, tile_size, overlap):
    offset = tile_size - overlap

    tiles_windows_list = []
    nb = 1
    for offset_height in range(0, height - tile_size + 1, offset):
        for offset_width in range(0, width - tile_size + 1, offset):
            window = windows.Window(offset_width, offset_height, tile_size, tile_size)
            tiles_windows_list.append(window)
            nb += 1

    return tiles_windows_list


def load_model(run_dirpath, backbone, config):
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


def inf_unet_tile(image, model, config, window): # image = 1 tile # on calcule toutes les poygonizations et on filtre avec les centroides après coup
    image_float = image / 255
    mean = np.mean(image_float.reshape(-1, image_float.shape[-1]), axis=0)
    std = np.std(image_float.reshape(-1, image_float.shape[-1]), axis=0)
    sample = { # Normalement c'est mean et std sur l'image entière
        "image": torchvision.transforms.functional.to_tensor(image)[None, ...],
        "image_mean": torch.from_numpy(mean)[None, ...],
        "image_std": torch.from_numpy(std)[None, ...],
        "image_filepath": None,
    }
    print("888888888888888888888888888888888888888888888888888888888")
    print(torch.cuda.mem_get_info())
    tile_data = inference.inference(config, model, sample, compute_polygonization=False)
    print(torch.cuda.mem_get_info())

    return tile_data


def merge_segs(predictions, dalle_size, config, windows):
    dalle_height, dalle_width = dalle_size
    weight_map = torch.zeros((1, 1, dalle_height, dalle_width), dtype=torch.float16)#, device=config["device"])

    # Compute patch pixel weights to merge overlapping patches back together smoothly:
    patch_size = windows[0].height
    patch_weights = np.ones((patch_size + 2, patch_size + 2), dtype=np.float16)
    patch_weights[0, :] = 0
    patch_weights[-1, :] = 0
    patch_weights[:, 0] = 0
    patch_weights[:, -1] = 0
    patch_weights = scipy.ndimage.distance_transform_edt(patch_weights)
    patch_weights = patch_weights[1:-1, 1:-1]
    print("PPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPPP")
    print(patch_weights.shape)
    patch_weights = torch.tensor(patch_weights, dtype=torch.float16)#, device=config["device"], dtype=torch.float16)#.float()
    # patch_weights = torch.tensor(patch_weights).float()
    patch_weights = patch_weights[None, None, :, :]  # Adding batch and channels dims


    tile_data = {}
    # seg_channels = config["seg_params"]["compute_interior"] \
    #     + config["seg_params"]["compute_edge"] \
    #     + config["seg_params"]["compute_vertex"]
    seg_channels = 2
    print("88888888888888888888888888888888888888888888888888888888888888888888888888")
    print(seg_channels)
    print('in merge')
    print(torch.cuda.mem_get_info())
    tile_data["seg"] = torch.zeros((1, seg_channels, dalle_height, dalle_width), dtype=torch.float16)#, device=config["device"])
    print(torch.cuda.mem_get_info())
    print("55555555555555555555555555555555555555555555555555555555")
    print(tile_data["seg"].dtype)
    tile_data["crossfield"] = torch.zeros((1, 4, dalle_height, dalle_width), dtype=torch.float16)#, device=config["device"])

    patch_boundingboxes = [np.array([window.row_off, window.col_off, window.row_off + window.height, window.col_off + window.width]) for window in windows]

    # Predict on each patch and save in outputs:
    for bbox, pred in tqdm(zip(patch_boundingboxes, predictions), desc="Running model on patches", leave=False): # zip patch_boundingboxes et predictions
        tile_data["seg"][:, :, bbox[0]:bbox[2], bbox[1]:bbox[3]] += patch_weights * pred["seg"][:, 2, :, :].to("cpu")
        tile_data["crossfield"][:, :, bbox[0]:bbox[2], bbox[1]:bbox[3]] += patch_weights * pred["crossfield"].to("cpu")
        weight_map[:, :, bbox[0]:bbox[2], bbox[1]:bbox[3]] += patch_weights

    # Take care of overlapping parts
    tile_data["seg"] /= weight_map
    tile_data["crossfield"] /= weight_map

    print("6666666666666666666666666")
    print(tile_data["seg"].element_size())
    print(tile_data['seg'].nelement())
    print(tile_data["seg"].element_size() * tile_data['seg'].nelement())
    return tile_data


def polygonization(tile_data, out_dirpath, in_file_path, raster_proj, config): # après coups
        print("000000000000000000000000000000000000000000000000000000000000000000000000000")
        print(torch.cuda.mem_get_info())
        torch.cuda.empty_cache()
        print(torch.cuda.mem_get_info())

        print(tile_data["seg"].shape)
        print(tile_data["seg"].dtype)
        print(tile_data["seg"].element_size())
        print(tile_data["seg"].element_size() * tile_data['seg'].nelement())
        print()

        print(tile_data["crossfield"].shape)
        print(tile_data["crossfield"].dtype)
        print(tile_data["crossfield"].element_size())
        print(tile_data["crossfield"].element_size() * tile_data['crossfield'].nelement())
        # print(tile_data["seg"])

        polygons_batch, probs_batch = polygonize.polygonize(config["polygonize_params"], tile_data["seg"], tile_data["crossfield"], pool=None)

        with rasterio.open(in_file_path) as img :
            image = img.read([1, 2, 3]).swapaxes(0, 2).swapaxes(0, 1)

        tile_data = {}
        tile_data["image"] = torchvision.transforms.functional.to_tensor(image)[None, ...]
        tile_data["polygons"] = polygons_batch
        tile_data["polygon_probs"] = probs_batch


        tile_data = local_utils.batch_to_cpu(tile_data)

        # Remove batch dim:
        tile_data = local_utils.split_batch(tile_data)[0]

        # --- Saving outputs --- #

        # Figuring out_base_filepath out:
        base_filename = os.path.splitext(os.path.basename(in_file_path))[0]
        out_base_filepath = (out_dirpath, base_filename)

   
        schema = {
        'geometry': 'Polygon',
        'properties': {'id': 'int'},
        }

        # file_name = os.path.basename(img_path).split(".")[0]
        with fiona.open(
            os.path.join(out_dirpath),
            'w', driver='ESRI Shapefile',
            schema=schema,
            crs=fiona.crs.from_epsg(2154)
            ) as c:
            for id_, polygon in enumerate(tile_data["polygons"][0]["asm"]["tol_1"] ):
                raster_polygon = shapely.ops.transform(raster_proj, polygon)
                wkt_polygon = shapely.geometry.mapping(raster_polygon)
                c.write({
                    'geometry': wkt_polygon,
                    'properties': {'id': id_},
                })
 

def main(config, backbone, run_dirpath, img_path, out_dirpath):
    t = time.time()
    print("9999999999999999999999999999999999999999999999999999")
    print(torch.cuda.mem_get_info())
    model = load_model(run_dirpath, backbone, config)
    print(torch.cuda.mem_get_info())
    print("Open image ...")
    img_path = img_path[0] # une seule image à la fois
    with rasterio.open(img_path) as src:
        raster_proj = lambda x, y: src.transform * (x, y)
        height, width = src.height, src.width
        print("Get windows ...")
        wins = split_img_tiles(height, width, tile_size=750, overlap=500)
        inf = []
        print("Get all inf ...")
        for window in wins[0:3]:
            tile = src.read([1, 2, 3], window=window).swapaxes(0, 2).swapaxes(0, 1)
            inf.append(inf_unet_tile(tile, model, config, window))
    print(torch.cuda.mem_get_info())
    print("del model ?")
    print(torch.cuda.mem_get_info())
    ##########################################
    # free memory
    del model  #deleting the model 
    # model will still be on cache until its place is taken by other objects so also execute the below lines
    import gc         # garbage collect library
    gc.collect()
    torch.cuda.empty_cache()
    print(torch.cuda.mem_get_info())
    ##########################################

    ##########################################
    print("merge")
    tile_data = merge_segs(inf, (25000, 25000), config, wins)
    print("after merge")
    print(torch.cuda.mem_get_info())
    file_name = os.path.basename(img_path).split(".")[0]
    polygonization(tile_data, os.path.join(out_dirpath, file_name + ".shp"), img_path, raster_proj, config)






    print("Save file .....")
    schema = {
    'geometry': 'Polygon',
    'properties': {'id': 'int'},
    }

    # file_name = os.path.basename(img_path).split(".")[0]
    # with fiona.open(
    #     os.path.join(out_dirpath, file_name + ".shp"),
    #     'w', driver='ESRI Shapefile',
    #     schema=schema,
    #     crs=fiona.crs.from_epsg(2154)
    #     ) as c:
    #     for id_, polygon in enumerate(res):
    #         raster_polygon = shapely.ops.transform(raster_proj, polygon)
    #         wkt_polygon = shapely.geometry.mapping(raster_polygon)
    #         c.write({
    #             'geometry': wkt_polygon,
    #             'properties': {'id': id_},
    #         })
    print(time.time() - t)


def get_args():
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument(
        '--in_filepath',
        type=str,
        nargs='*',
        required=True,
        help='For launching prediction on image(s), use this argument to specify their paths.')

    argparser.add_argument(
        '--out_dirpath',
        type=str,
        required=True,
        help='Path to the output directory of prediction(s).')

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

    backbone = UNetResNetBackbone(config['backbone_params']["encoder_depth"], num_filters=config['backbone_params']["num_filters"],
                                    dropout_2d=config['backbone_params']["dropout_2d"],
                                    pretrained=config['backbone_params']["pretrained"],
                                    is_deconv=config['backbone_params']["is_deconv"])
    backbone = _SimpleSegmentationModel(backbone, classifier=torch.nn.Identity())

    main(config, backbone, run_dirpath, args.in_filepath, args.out_dirpath)