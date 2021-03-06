# -----------------------------------------------------------
# Position Focused Attention Network (PFAN) implementation based on 
# another network Stacked Cross Attention Network (https://arxiv.org/abs/1803.08024)
# the code of SCAN: https://github.com/kuanghuei/SCAN
# ---------------------------------------------------------------
"""Data provider"""

import torch
import torch.utils.data as data
import torchvision.transforms as transforms
import os
import nltk
from PIL import Image
import numpy as np
import json as jsonmod


class PrecompDataset(data.Dataset):
    """
    Load precomputed captions and image features
    Possible options: f30k_precomp, coco_precomp
    """

    def __init__(self, data_path, data_split, vocab):
        self.vocab = vocab
        loc = data_path + '/'
        self.data_split = data_split
        # Captions
        self.captions = []
        file_name = loc+'%s_caps.txt' % data_split
        if os.path.exists(file_name):
            with open(file_name, 'rb') as f:
                for line in f:
                    self.captions.append(line.strip())

        # Image features
        print("Image path", loc+'%s_ims.npy' % data_split)
        self.images = np.load(loc+'%s_ims.npy' % data_split)
        self.boxes = np.load(loc+'%s_boxes.npy' % data_split)
        self.length = len(self.captions)
        print("Len in captions", self.length)
        self.public_data = True
        # True means len(self.captions) > self.images.shape[0] (public data)
        # False means len(self.captions) <= self.images.shape[0] (Our own data)
        if self._get_data_split(data_split):
            if len(self.captions) > self.images.shape[0]:
                self.length = len(self.captions)
                self.im_div = len(self.captions) / self.images.shape[0]
            else:
                self.length = self.images.shape[0]
                self.im_div = self.images.shape[0] / len(self.captions)
                self.public_data = False
        # rkiros data has redundancy in images, we divide by 5, 10crop doesn't
        print("Image shape in data_loader", self.images.shape, self.length)
        print("Boxes shape in data_loader", self.boxes.shape)
        if not self._get_data_split(data_split):
            if self.images.shape[0] != self.length:
                self.im_div = 5
            else:
                self.im_div = 1
        # the development set for coco is large and so validation would be slow
        #if data_split == 'dev':
        #    self.length = 5000

    def _get_data_split(self, data_split):
        if data_split.startswith("test"):
            return True
        return False

    def __getitem__(self, index):
        # handle the image redundancy
        img_id = index/self.im_div              # division create floating points?
        cap_id = index
        if not self.public_data:
            img_id = index
            cap_id = index/self.im_div

#         print("___", self.data_split, img_id, index, self.im_div)
        
        img_id = int(img_id)                                      # my comment
        image = torch.Tensor(self.images[ img_id])
        box = torch.Tensor(self.boxes[img_id])
        caption = self.captions[cap_id]
        vocab = self.vocab

        # Convert caption (string) to word ids.
#         tokens = nltk.tokenize.word_tokenize(
#             str(caption).lower().decode('utf-8'))
        tokens = nltk.tokenize.word_tokenize(
            str(caption).lower())
        caption = []
        caption.append(vocab('<start>'))
        caption.extend([vocab(token) for token in tokens])
        caption.append(vocab('<end>'))
        #print "Caption id", caption
        target = torch.Tensor(caption)
        return image, box, target, index, img_id

    def __len__(self):
        return self.length


def collate_fn(data):
    """Build mini-batch tensors from a list of (image, box, caption) tuples.
    Args:
        data: list of (image, box, caption) tuple.
            - image: torch tensor of shape (3, 256, 256).
            - box: torch tensor of shape
            - caption: torch tensor of shape (?); variable length.

    Returns:
        images: torch tensor of shape (batch_size, 3, 256, 256).
        targets: torch tensor of shape (batch_size, padded_length).
        lengths: list; valid length for each padded caption.
    """
    # Sort a data list by caption length
    data.sort(key=lambda x: len(x[2]), reverse=True)
    images, boxes, captions, ids, img_ids = zip(*data)

    # Merge images (convert tuple of 3D tensor to 4D tensor)
    images = torch.stack(images, 0)
    boxes = torch.stack(boxes, 0)

    # Merget captions (convert tuple of 1D tensor to 2D tensor)
    lengths = [len(cap) for cap in captions]
    targets = torch.zeros(len(captions), max(lengths)).long()
    for i, cap in enumerate(captions):
        end = lengths[i]
        targets[i, :end] = cap[:end]

    return images, boxes, targets, lengths, ids


def get_precomp_loader(data_path, data_split, vocab, opt, batch_size=100,
                       shuffle=True, num_workers=2):
    """Returns torch.utils.data.DataLoader for custom coco dataset."""
    dset = PrecompDataset(data_path, data_split, vocab)

    data_loader = torch.utils.data.DataLoader(dataset=dset,
                                              batch_size=batch_size,
                                              shuffle=shuffle,
                                              pin_memory=True,
                                              collate_fn=collate_fn)
    return data_loader


def get_loaders(data_name, vocab, batch_size, workers, opt):
    dpath = os.path.join(opt.data_path, data_name)
    train_loader = get_precomp_loader(dpath, 'train', vocab, opt,
                                      batch_size, True, workers)
    val_loader = get_precomp_loader(dpath, 'dev', vocab, opt,
                                    batch_size, False, workers)
    return train_loader, val_loader


def get_test_loader(split_name, data_name, vocab, batch_size,
                    workers, opt):
    dpath = os.path.join(opt.data_path, data_name)
    test_loader = get_precomp_loader(dpath, split_name, vocab, opt,
                                     batch_size, False, workers)
    return test_loader
