import os
import cv2
import argparse
import torch
import numpy as np
from os import path, makedirs
import pickle
from tqdm import tqdm
from glob import glob
from natsort import natsorted
import yaml
import multiprocessing as mp
from multiprocessing import Process
from functools import partial
from dotmap import DotMap
from torchvision import transforms as tt


from utils.general import parallel_data_prefetch
from data import get_dataset
from data.helper_functions import preprocess_image

h36m_aname2aid = {name: i for i, name in enumerate(["Directions","Discussion","Eating","Greeting","Phoning",
                                                    "Posing","Purchases","Sitting","SittingDown","Smoking",
                                                    "Photo","Waiting","Walking","WalkDog","WalkTogether"])}
h36m_aname2aid.update({"WalkingTogether": h36m_aname2aid["WalkTogether"]})
h36m_aname2aid.update({"WalkingDog": h36m_aname2aid["WalkDog"]})
h36m_aname2aid.update({"TakingPhoto": h36m_aname2aid["Photo"]})


def _do_parallel_data_prefetch(func, Q, data, idx):
    # create dummy dataset instance

    # run prefetching
    res = func(data)
    Q.put([idx, res])
    Q.put("Done")

def get_image(vidcap, frame_number,spatial_size=None):
    vidcap.set(1, frame_number)
    _, img = vidcap.read()
    if spatial_size is not None and spatial_size != img.shape[0]:
        img=cv2.resize(img,(spatial_size,spatial_size),interpolation=cv2.INTER_LINEAR)
    return img


# def process_images(d_name,semaphore, args):
#     from utils.flownet_loader import FlownetPipeline
#     from utils.general import get_gpu_id_with_lowest_memory, get_logger
#     target_gpus = None if len(args.target_gpus) == 0 else args.target_gpus
#     gpu_index = get_gpu_id_with_lowest_memory(target_gpus=target_gpus)
#     logger = get_logger(f"{d_name}-{gpu_index}")
#     img_list = natsorted([n for n in glob(path.join(d_name, f"*.{args.image_format}")) if n.split("/")[-1].startswith(args.image_prefix)])
#
#     #basedir_name = args.raw_dir.split("*", 1)[0] if "*" in args.raw_dir else "/" + "/".join(args.raw_dir.split("/")[:-1])
#     basedir_name = "/".join(args.raw_dir.split("/")[:-1])
#
#
#
#
#     torch.cuda.set_device(gpu_index)
#
#     extract_device = torch.device("cuda", gpu_index.index if isinstance(gpu_index, torch.device) else gpu_index)
#
#     # load flownet
#     pipeline = FlownetPipeline()
#     flownet = pipeline.load_flownet(args, extract_device)
#
#     # get images
#
#
#
#     subdir_name = d_name.split(basedir_name)[-1]
#     if subdir_name.startswith("/"):
#         subdir_name =subdir_name[1:]
#     # path for saving the images
#     base_path = path.join(args.processed_dir, subdir_name)
#
#     makedirs(base_path, exist_ok=True)
#     logger.info(f"Basepath is {base_path}")
#
#     delta = args.flow_delta
#     diff = args.flow_max
#
#
#
#     number_frames = len(img_list)
#
#     # only required for splitting the images, as split throws error when separator is empty string
#     split_prefix = args.image_prefix if args.image_prefix != "" else "_"
#
#     if args.continuous:
#         for img_p in img_list[::args.frames_discr]:
#             actual_id = img_p.split(split_prefix)[-1].split(f".{args.image_format}")[0]
#             n_digits = len(actual_id)
#             first_id = int(actual_id)
#             second_id = first_id + diff
#             # resave images, if intended
#             # img = None
#             # if args.resave_imgs:
#             #     img_target_file = path.join(base_path, f"frame_{actual_id}.png")
#             #     if not path.exists(img_target_file):
#             #         img = cv2.imread(img_p)
#             #         if args.spatial_size is not None and args.spatial_size != img.shape[0]:
#             #             img_resized = cv2.resize(img, (args.spatial_size, args.spatial_size), interpolation=cv2.INTER_LINEAR)
#             #         else:
#             #             img_resized = img
#             #
#             #         # save resized image but use original image as input to the flownet later
#             #         success = cv2.imwrite(img_target_file, img_resized)
#             #
#             #         if success:
#             #             logger.info(f'wrote img with shape {img_resized.shape} to "{img_target_file}".')
#
#             # FLOW
#             for d in range(0, diff, delta):
#                 if second_id - d < number_frames:
#                     flow_target_file = path.join(
#                         base_path, f"prediction_{first_id}_{second_id - d}"
#                     )
#                     if not os.path.exists(flow_target_file + ".npy"):
#                         # predict and write flow prediction
#                         img_p2 = path.join(d_name, f"{args.image_prefix}{str(second_id - d).zfill(n_digits)}.{args.image_format}")
#
#                         img = cv2.imread(img_p)
#                         img2 = cv2.imread(img_p2)
#
#                         sample = pipeline.preprocess_image(img, img2, "BGR", spatial_size=args.input_size).to(
#                             extract_device
#                         )
#                         prediction = (
#                             pipeline.predict(flownet, sample[None], spatial_size=args.spatial_size)
#                                 .cpu()
#                                 .detach()
#                                 .numpy()
#                         )
#                         np.save(flow_target_file, prediction)
#
#                         logger.info(
#                             f'wrote flow map with shape {prediction.shape} to "{flow_target_file}".')
#     else:
#         for img_count,img_p in enumerate(img_list):
#             actual_id = img_p.split(split_prefix)[-1].split(f".{args.image_format}")[0]
#             # n_digits = len(actual_id)
#             # first_id = int(actual_id)
#
#             # img = None
#             # if args.resave_imgs:
#             #     img_target_file = path.join(base_path, f"frame_{img_count}.png")
#             #     if not path.exists(img_target_file):
#             #         img = cv2.imread(img_p)
#             #         if args.spatial_size is not None and args.spatial_size != img.shape[0]:
#             #             img_resized = cv2.resize(img, (args.spatial_size, args.spatial_size), interpolation=cv2.INTER_LINEAR)
#             #         else:
#             #             img_resized = img
#             #
#             #         # save resized image but use original image as input to the flownet later
#             #         success = cv2.imwrite(img_target_file, img_resized)
#             #
#             #         if success:
#             #             logger.info(f'wrote img with shape {img_resized.shape} to "{img_target_file}".')
#
#             # FLOW
#             if img_count < len(img_list) - diff - 1:
#                 target_imgs = img_list[img_count+delta:img_count+diff+1:delta]
#                 for t_c,t_img in enumerate(target_imgs):
#                     flow_target_file = path.join(
#                         base_path, f"prediction_{img_count}_{img_count + (t_c+1) * delta}"
#                     )
#                     if not os.path.exists(flow_target_file + ".npy"):
#                         # predict and write flow prediction
#                         img_p2 = path.join(d_name, t_img)
#                         img = cv2.imread(img_p)
#                         img2 = cv2.imread(img_p2)
#
#                         sample = pipeline.preprocess_image(img, img2, "BGR", spatial_size=args.input_size).to(
#                             extract_device
#                         )
#                         prediction = (
#                             pipeline.predict(flownet, sample[None], spatial_size=args.spatial_size)
#                                 .cpu()
#                                 .detach()
#                                 .numpy()
#                         )
#                         np.save(flow_target_file, prediction)
#
#                         logger.info(
#                             f'wrote flow map with shape {prediction.shape} to "{flow_target_file}".')
#
#
#
#
#     semaphore.release()


def process_video(f_name, args):
    from utils.flownet_loader import FlownetPipeline
    from utils.general import get_gpu_id_with_lowest_memory, get_logger


    target_gpus = None if len(args.target_gpus) == 0 else args.target_gpus
    gpu_index = get_gpu_id_with_lowest_memory(target_gpus=target_gpus)
    torch.cuda.set_device(gpu_index)

    #f_name = vid_path.split(vid_path)[-1]

    logger = get_logger(f"{gpu_index}")

    extract_device = torch.device("cuda", gpu_index.index if isinstance(gpu_index,torch.device) else gpu_index)

    # load flownet
    pipeline = FlownetPipeline()
    flownet = pipeline.load_flownet(args, extract_device)

    # open video
    base_raw_dir = args.raw_dir.split("*")[0]

    if not isinstance(f_name,list):
        f_name = [f_name]

    logger.info(f"Iterating over {len(f_name)} files...")
    for fn in tqdm(f_name,):
        if fn.startswith('/'):
            fn = fn[1:]
        vid_path = path.join(base_raw_dir, fn)
        # vid_path = f"Code/input/train_data/movies/{fn}"
        vidcap = cv2.VideoCapture()
        vidcap.open(vid_path)
        counter = 0
        while not vidcap.isOpened():
            counter += 1
            time.sleep(1)
            if counter > 10:
                raise Exception("Could not open movie")

        # get some metadata
        number_frames = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
        height = int(vidcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        width = int(vidcap.get(cv2.CAP_PROP_FRAME_WIDTH))
        #upright = height > width

        # create target path if not existent

        base_path = path.join(args.processed_dir, fn.split(".")[0])   #.replace(str,str(args.spatial_size)))
        # base_path = f"Code/input/train_data/images/{f_name.split('.')[0]}/"
        makedirs(base_path, exist_ok=True)

        delta = args.flow_delta
        diff = args.flow_max


        # begin extraction
        for frame_number in range(0, number_frames, args.frames_discr):
            # break if not enough frames to properly extract sequence
            if frame_number >= number_frames - diff * args.frames_discr:
                break
            first_fidx, second_fidx = frame_number, frame_number + diff * args.frames_discr
            image_target_file = path.join(base_path, f"frame_{frame_number}.png")
            # image_target_file = f"{base_path}frame_{frame_number}.png"
            # FRAME
            if not path.exists(image_target_file):
                # write frame itself
                img = get_image(vidcap, frame_number)
                if img is None:
                    continue
                # if upright:
                #     img = cv2.transpose(img)
                try:
                    if args.spatial_size is None:
                        success = cv2.imwrite(image_target_file, img)
                    else:
                        img_res = cv2.resize(img,(args.spatial_size,args.spatial_size), interpolation=cv2.INTER_LINEAR)
                        success = cv2.imwrite(image_target_file,img_res)
                except cv2.error as e:
                    print(e)
                    continue
                except Exception as ex:
                    print(ex)
                    continue

                # if success:
                #     logger.info(f'wrote img with shape {img.shape} to "{image_target_file}".')
            # FLOW
            for d in range(0, diff*args.frames_discr, delta*args.frames_discr):
                if second_fidx - d < number_frames:
                    flow_target_file = path.join(
                        base_path, f"prediction_{first_fidx}_{second_fidx-d}.flow"
                    )
                    if not os.path.exists(flow_target_file + ".npy"):
                        # predict and write flow prediction
                        img, img2 = (
                            get_image(vidcap, first_fidx),
                            get_image(vidcap, second_fidx - d),
                        )
                        # if upright:
                        #     img, img2 = cv2.transpose(img), cv2.transpose(img2)
                        sample = pipeline.preprocess_image(img, img2, "BGR",spatial_size=args.input_size).to(
                            extract_device
                        )
                        prediction = (
                            pipeline.predict(flownet, sample[None],spatial_size=args.spatial_size)
                            .cpu()
                            .detach()
                            .numpy()
                        )
                        np.save(flow_target_file, prediction)

        logger.info(
            f'Finish processing video sequence "{fn}".')

    return "Finish"

def extract(args):


    # if args.process_vids:

    base_dir = args.raw_dir.split("*")[0]
    if not args.raw_dir.endswith('*'):
        args.raw_dir =path.join(args.raw_dir,'*')
    data_names = [p.split(base_dir)[-1] for p in glob(args.raw_dir) if p.endswith(args.video_format)]

    # data_names = [d for d in data_names if d in ['/VID_0_5.mkv','/VID_7_0.mkv']]



    fn_extract = partial(process_video, args=args)

    Q = mp.Queue(1000)
    step = (
        int(len(data_names) / args.num_workers + 1)
        if len(data_names) % args.num_workers != 0
        else int(len(data_names) / args.num_workers)
    )
    arguments = [
        [fn_extract, Q, part, i]
        for i, part in enumerate(
            [data_names[i: i + step] for i in range(0, len(data_names), step)]
        )
    ]
    processes = []
    for i in range(args.num_workers):
        p = Process(target=_do_parallel_data_prefetch, args=arguments[i])
        processes += [p]

    start = time.time()
    gather_res = [[] for _ in range(args.num_workers)]
    try:
        for p in processes:
            p.start()
            time.sleep(20)

        k = 0
        while k < args.num_workers:
            # get result
            res = Q.get()
            if res == "Done":
                k += 1
            else:
                gather_res[res[0]] = res[1]

    except Exception as e:
        print("Exception: ", e)
        for p in processes:
            p.terminate()

        raise e
    finally:
        for p in processes:
            p.join()
        print(f"Prefetching complete. [{time.time() - start} sec.]")

def prepare(args):
    logger = get_logger("dataset_preparation")


    datadict = {
        "img_path": [],
        "flow_paths": [],
        "fid": [],
        "vid": [],
        "img_size": [],
        "flow_size": [],
        "object_id":[],
        "max_fid": []
    }
    if "iPER" in args.processed_dir.split("/") or "human36m" in args.processed_dir.split("/") or \
            "human3.6M" in args.processed_dir.split("/") :
        datadict.update({"action_id": [], "actor_id": []})

    train_test_split = "human3.6M" in args.processed_dir.split("/")  or "taichi" in args.processed_dir.split("/")

    if train_test_split:
        datadict.update({"train": []})
        if "taichi" in args.processed_dir.split("/"):
            oname2oid = {}

    # logger.info(f'Metafile is stored as "{args.meta_file_name}.p".')
    # logger.info(f"args.check_imgs is {args.check_imgs}")
    max_flow_length = int(args.flow_max / args.flow_delta)

    # if args.process_vids:
    if train_test_split:
        videos = [d for d in glob(path.join(args.processed_dir, "*", "*")) if path.isdir(d)]
    else:
        videos = [d for d in glob(path.join(args.processed_dir, "*")) if path.isdir(d)]

    videos = natsorted(videos)

    actual_oid = 0
    for vid, vid_name in enumerate(videos):

        images = glob(path.join(vid_name, "*.png"))
        images = natsorted(images)

        actor_id = action_id = train = None
        if "plants" in args.processed_dir.split("/"):
            object_id = int(vid_name.split("/")[-1].split("_")[1])
        elif "iPER" in args.processed_dir.split("/"):
            object_id = 100 * int(vid_name.split("/")[-1].split("_")[0]) + int(vid_name.split("/")[-1].split("_")[1])
            actor_id = int(vid_name.split("/")[-1].split("_")[0])
            action_id = int(vid_name.split("/")[-1].split("_")[-1])
        elif train_test_split:
            train = "train" == vid_name.split("/")[-2]
            msg = "train" if train else "test"
            print(f"Video in {msg}-split")
            if "taichi" in args.processed_dir.split("/"):
                obj_name = vid_name.split("/")[-1].split("#")[0]
                if obj_name in oname2oid.keys():
                    object_id = oname2oid[obj_name]
                else:
                    object_id = actual_oid
                    oname2oid.update({obj_name: actual_oid})
                    actual_oid += 1
            else:
                uname = vid_name.split("/")[-1].split("_")
                object_id = 10 * int(uname[-1][1:]) + 10000 * (int(uname[-2][-1])) + int(train)
        else:
            raise ValueError("invalid dataset....")

        max_flow_id = [len(images) - flow_step -1 for flow_step in range(args.flow_delta,args.flow_max+1, args.flow_delta)]
        for i, img_path in enumerate(
                tqdm(
                    images,
                    desc=f'Extracting meta information of video "{vid_name.split("/")[-1]}"',
                )
        ):
            fid = int(img_path.split("_")[-1].split(".")[0])
            #search_pattern = f'[{",".join([str(fid + n) for n in range(args.flow_delta,args.flow_max + 1, args.flow_delta)])}]'

            flows = natsorted([s for s in glob(path.join(vid_name, f"prediction_{fid}_*.npy"))
                               if (int(s.split("_")[-1].split(".")[0]) - int(s.split("_")[-2])) % args.flow_delta == 0 and
                               int(s.split("_")[-1].split(".")[0]) - int(s.split("_")[-2]) <= args.flow_max])

            # make relative paths
            img_path_rel = img_path.split(args.processed_dir)[1]
            flows_rel = [f.split(args.processed_dir)[1] for f in flows]
            # filter flows
            flows_rel = [f for f in flows_rel if (int(f.split("/")[-1].split(".")[0].split("_")[-1]) - int(f.split("/")[-1].split(".")[0].split("_")[-2])) <= args.flow_max]

            if len(flows_rel) < max_flow_length:
                diff = max_flow_length-len(flows_rel)
                [flows_rel.insert(len(flows_rel),last_flow_paths[len(flows_rel)]) for _ in range(diff)]

            w_img = args.spatial_size
            h_img = args.spatial_size
            if len(flows) > 0:
                w_f = args.spatial_size
                h_f = args.spatial_size
            else:
                h_f = w_f = None

            assert len(flows_rel) == max_flow_length
            datadict["img_path"].append(img_path_rel)
            datadict["flow_paths"].append(flows_rel)
            datadict["fid"].append(fid)
            datadict["vid"].append(vid)
            # image size compliant with numpy and torch
            datadict["img_size"].append((h_img, w_img))
            datadict["flow_size"].append((h_f, w_f))
            datadict["object_id"].append(object_id)
            datadict["max_fid"].append(max_flow_id)
            if action_id is not None:
                datadict["action_id"].append(action_id)
            if actor_id is not None:
                datadict["actor_id"].append(actor_id)
            if train is not None:
                datadict["train"].append(train)

            last_flow_paths = flows_rel

    logger.info(f'Prepared dataset consists of {len(datadict["img_path"])} samples.')

    # Store data (serialize)
    save_path = path.join(
        args.processed_dir, "test_codeprep_metadata.p"
    )
    with open(save_path, "wb") as handle:
        pickle.dump(datadict, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load_flow(flow_paths):
    norms = []
    for i, flow_path in enumerate(tqdm(flow_paths)):
        # debug, this path seems to be erroneous
        # flow_path = "/export/data/ablattma/Datasets/plants/processed_crops/VID_0_3_1024x1024/prediction_3_28.flow.npy"
        try:
            flow = np.load(flow_path)
        except Exception as e:
            print(e)
            continue
        n = np.linalg.norm(flow,2,0)
        min_norm = np.amin(n)
        max_norm = np.amax(n)
        norms.append(np.stack([max_norm,min_norm]))

    norms = np.stack(norms,0)
    return norms

def norms(cfg_dict):
    cfg_dict['data']['normalize_flows'] = False

    transforms = tt.Compose(
        [tt.ToTensor(), tt.Lambda(lambda x: (x * 2.0) - 1.0)]
    )

    datakeys = ["flow", "images"]

    dataset, _ = get_dataset(config=cfg_dict["data"])
    test_dataset = dataset(transforms, datakeys, cfg_dict["data"], train=True)
    print(test_dataset.__class__.__name__)
    name = test_dataset.__class__.__name__

    save_dir = f"test_data/{name}"
    makedirs(save_dir, exist_ok=True)

    flow_paths = test_dataset.data["flow_paths"]


    stats_dict = {"max_norm": [], "min_norm": [], "percentiles": []}
    for i in range(flow_paths.shape[-1]):
        test_dataset.logger.info(f"Computing mean of flow with lag {(i + 1) * 5}")
        norms = parallel_data_prefetch(load_flow, flow_paths[:, i], cfg_dict['data'][['num_workers']])

        max_n = np.amax(norms[:, 0])
        min_n = np.amin(norms[:, 1])
        percs_at = list(range(10, 100, 10))
        percs = np.percentile(norms[:, 0], percs_at)

        stats_dict["percentiles"].append({pa: p for pa, p in zip(percs_at, percs)})
        stats_dict["max_norm"].append(float(max_n))
        stats_dict["min_norm"].append(float(min_n))

    # save
    if test_dataset.normalize_flows:
        savepath = path.join(test_dataset.datapath, "dataset_stats.p")
    else:
        savepath = path.join(test_dataset.datapath, "dataset_stats_pixels.p")
    with open(savepath, "wb") as handle:
        pickle.dump(stats_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)


def stats(cfg_dict):

    cfg_dict['data']['normalize_flows'] = True

    transforms = tt.Compose(
        [tt.ToTensor(), tt.Lambda(lambda x: (x * 2.0) - 1.0)]
    )

    datakeys = ["flow", "images"]

    dataset, _ = get_dataset(config=cfg_dict["data"])
    test_dataset = dataset(transforms, datakeys, cfg_dict["data"], train=True)
    print(test_dataset.__class__.__name__)
    name = test_dataset.__class__.__name__

    save_dir = f"test_data/{name}"
    makedirs(save_dir, exist_ok=True)

    def process_flows(flow_data):
        out = np.zeros((len(flow_data),3))

        for i,dp in enumerate(tqdm(flow_data)):

            flow = np.load(dp[0])
            #flow = flow - test_dataset.flow_norms["min_norm"][test_dataset.valid_lags[0]]
            flow = flow / test_dataset.flow_norms["max_norm"][test_dataset.valid_lags[0]]

            img = cv2.imread(dp[1])
            # image is read in BGR
            img = preprocess_image(img, swap_channels=True)

            mask = np.zeros(img.shape[:2], np.uint8)
            # rect defines starting background area
            if test_dataset.filter_flow:
                rect = (
                int(img.shape[1] / test_dataset.flow_width_factor), test_dataset.valid_h[0], int((test_dataset.flow_width_factor - 2) / test_dataset.flow_width_factor * img.shape[1]), test_dataset.valid_h[1] - test_dataset.valid_h[0])
                # initialize background and foreground models
                fgm = np.zeros((1, 65), dtype=np.float64)
                bgm = np.zeros((1, 65), dtype=np.float64)
                # apply grab cut algorithm
                mask2, fgm, bgm = cv2.grabCut(img, mask, rect, fgm, bgm, 5, cv2.GC_INIT_WITH_RECT)

            amplitude = np.linalg.norm(flow[:, test_dataset.valid_h[0]:test_dataset.valid_h[1], test_dataset.valid_w[0]:test_dataset.valid_w[1]],2,axis=0)

            if test_dataset.filter_flow:
                # only consider the part of the mask which corresponds to the region considered in flow
                amplitude_filt = np.where(mask2[test_dataset.valid_h[0]:test_dataset.valid_h[1], test_dataset.valid_w[0]:test_dataset.valid_w[1]], amplitude, np.zeros_like(amplitude))
            else:
                amplitude_filt = amplitude

            std = amplitude_filt.std()

            mean = np.mean(amplitude_filt)

            indices = np.argwhere(np.greater(amplitude_filt, mean + (std * 2.0)))
            if indices.shape[0] == 0:
                indices = np.argwhere(np.greater(amplitude_filt, np.mean(amplitude_filt) + amplitude_filt.std()))
                if indices.shape[0] == 0:
                    print("Fallback in Dataloading bacause no values remain after filtering.")
                    # there should be at least one element that is above the mean if flows are not entirely equally distributed
                    indices = np.argwhere(np.greater(amplitude_filt, mean))
                    if indices.shape[0] == 0:
                        print("strange case, cannot occure, skip")
                        out[i, -1] = 1
                        continue

            values = np.asarray([amplitude_filt[idx[0], idx[1]] for idx in indices])
            out[i, 0] = values.min()
            out[i, 1] = values.max()


        return out

    in_data = [(f,i) for f,i in zip(test_dataset.data["flow_paths"][:,test_dataset.valid_lags[0]],test_dataset.data["img_path"])]
    out_data = parallel_data_prefetch(process_flows,in_data, n_proc=80, cpu_intensive=True, target_data_type="list")



    with open(path.join(test_dataset.datapath,f"{test_dataset.metafilename}.p"),"rb") as f:
        datadict = pickle.load(f)


    #assert out_data.shape[0] == len(datadict["img_path"])
    n_error = np.count_nonzero(out_data[:,2])

    print(f"While loading the data, {n_error} errors occurred.")
    key = "flow_range"
    name_key = "frange"

    datadict.update({key: out_data})
    with open(path.join(test_dataset.datapath, f"{test_dataset.metafilename}_{name_key}.p"), "wb") as f:
        pickle.dump(datadict, f, protocol=pickle.HIGHEST_PROTOCOL)


if __name__ == "__main__":

    import time
    from utils.general import get_logger



    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--config',type=str,required=True,help='Config file containing all parameters.')
    config_args = parser.parse_args()

    fpath = path.dirname(path.realpath(__file__))
    configfile = path.abspath(path.join(fpath,f'../{config_args.config}'))

    with open(configfile,'r') as f:
        args = yaml.load(f,Loader=yaml.FullLoader)
        cfg_dict = args

    args = DotMap(args)


    cfg_dict['data']['datapath'] = args.processed_dir



    if args.raw_dir == '':
        raise ValueError(f'The data holding directory is currently not defined. please define the field "raw_dir" in  "{config_args.config}"')

    if args.processed_dir == '':
        raise ValueError(f'The target directory for the extracted image frames and flow maps is currently undefined. Please define the field "processed_dir" in  "{config_args.config}"')

    pool = []
    torch.multiprocessing.set_start_method("spawn")

    if args.mode == "extract":
        extract(args)
    elif args.mode == "prepare":  # in this case, it is prepare
        prepare(args)
    else:
        extract(args)
        prepare(args)
        norms(cfg_dict)

