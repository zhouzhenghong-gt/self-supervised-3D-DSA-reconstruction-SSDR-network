import os
import re
import numpy as np
import SimpleITK as sitk
import cv2
import torch
import random
from torch.utils.data import Dataset

from utils.project import proj_make_3dinput_v2

def threshold_CTA_mask(cta_image, HU_window=np.array([-263.,553.])):
    th_cta_image = (cta_image - HU_window[0])/(HU_window[1] - HU_window[0])
    th_cta_image[th_cta_image < 0] = 0
    th_cta_image[th_cta_image > 1] = 1
    th_cta_image_mask = th_cta_image
    return th_cta_image_mask

class DSAReconDataset(Dataset):
    """ 3D Reconstruction Dataset."""
    def __init__(self, stage, num_views, input_path, last_path = None):
        """
        Args:
            stage (int): the number of stage of reconstruction network.
            num_views (int): the number of views.
            input_path (str): 2d input image and 2d label.
            last_path (str, optional): the path where the output of the previous/last stage of the network is saved.
        """
        self.stage = stage
        self.input_path = input_path
        self.last_path = last_path
        self.num_views = num_views

        dir = os.listdir(input_path)
        for ii, i in enumerate(dir):
            if not i.startswith('traingt'):
                dir.pop(ii)
        self.dir = dir

    def __len__(self):
        return len(self.dir)

    def __getitem__(self, index):

        if self.stage == 1:
            size = [128, 256, 256]
            crop_size = [32, 256, 256]
        elif self.stage == 2:
            size = [395, 512, 512]
            crop_size = [32, 512, 512]

        views = self.num_views
        file_index = int(re.findall('(\d+)',self.dir[index])[-1])

        # get ramdom crop
        start_slice0 = random.randint(0, size[0] - crop_size[0])
        end_slice0 = start_slice0 + crop_size[0]
        start_slice1 = random.randint(0, size[1] - crop_size[1])
        end_slice1 = start_slice1 + crop_size[1]
        start_slice2 = random.randint(0, size[2] - crop_size[2])
        end_slice2 = start_slice2 + crop_size[2]
        start_slice = [start_slice0/size[0], start_slice1/size[1], start_slice2/size[2]]
        crop_slice = [crop_size[0] / size[0], crop_size[1] / size[1], crop_size[2] / size[2]]

        # load 2D projections and unproject to 3D input
        perangle = 180/views
        if self.stage == 1:
            projs = np.zeros((views, crop_size[0], crop_size[1], crop_size[2]), dtype=np.float32)
        elif self.stage > 1:
            projs = np.zeros((views+1, crop_size[0], crop_size[1], crop_size[2]), dtype=np.float32)
        image_array_proj = np.zeros((views, crop_size[0], crop_size[1]), dtype=np.float32)
        for ii in range(views):
            if self.stage == 1:
                proj_temp = cv2.imread(self.input_path + '/traindata/'+str(views)+'view_low/train'+str(file_index)+'_'+str(ii)+'.jpg',0)
            elif self.stage > 1:
                proj_temp = cv2.imread(self.input_path + '/traindata/'+str(views)+'view/train'+str(file_index)+'_'+str(ii)+'.jpg',0)
            proj_temp = proj_temp - np.min(proj_temp)
            proj_temp = proj_temp / np.max(proj_temp)
            projs[ii,:,:,:] = proj_make_3dinput_v2(proj_temp, perangle*ii+perangle, start_slice, crop_slice)
            image_array_proj[ii,:,:] = proj_temp[start_slice0:end_slice0,:]
        
        # use last stage output as input
        if self.stage > 1:
            assert self.last_path!=None
            image_nii = sitk.ReadImage(self.last_path + '/predict'+str(file_index)+'.nii.gz')
            projs[views] = sitk.GetArrayFromImage(image_nii)[start_slice0:end_slice0, start_slice1:end_slice1, start_slice2:end_slice2] 

        image_array_proj = torch.from_numpy(image_array_proj).float()
        projs = torch.from_numpy(projs).float()
        return (projs, image_array_proj)

