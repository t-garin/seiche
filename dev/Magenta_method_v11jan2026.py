import glob
import os
from datetime import datetime
import numpy as np
import rasterio
from skimage.color import rgb2hsv
import matplotlib.pyplot as plt
from skimage.filters import gaussian
#from scipy.ndimage import uniform_filter
from scipy.ndimage import uniform_filter
from scipy.stats import variation
#from scipy.ndimage.filters import uniform_filter
#from scipy.ndimage.measurements import variance
from scipy.ndimage import variance
from numpy import *
import matplotlib.pyplot as plt
from matplotlib import colorbar, colors
import matplotlib
import cv2
from scipy import ndimage
from matplotlib.colors import ListedColormap


def frost_filter(img, damping_factor=2.0, win_size=5):
    img_filtered = np.zeros_like(img)
    N, M = img.shape
    win_offset = win_size // 2
    for i in range(N):
        xleft = max(i - win_offset, 0)
        xright = min(i + win_offset + 1, N)
        for j in range(M):
            yup = max(j - win_offset, 0)
            ydown = min(j + win_offset + 1, M)
            window = img[xleft:xright, yup:ydown]
            window_mean = np.mean(window)
            if window_mean == 0:
                img_filtered[i, j] = window_mean
                continue
            variation_coef = np.var(window)
            sigma_zero = variation_coef / window_mean**2
            factor_A = damping_factor * sigma_zero
            h, w = window.shape
            center_i, center_j = h // 2, w // 2
            weights = np.zeros((h, w))
            for ii in range(h):
                for jj in range(w):
                    dist = np.sqrt((ii - center_i)**2 + (jj - center_j)**2)
                    weights[ii, jj] = np.exp(-factor_A * dist)
            weighted_values = weights * window
            img_filtered[i, j] = np.sum(weighted_values) / np.sum(weights)
    return img_filtered

# Les fichiers SAR a traiter sont dans le rep Data
dir_data="./Data/"

sar_files = glob.glob('./Data/*_vh_*202504*.tif')  # ici une selection pour les tests

file_info = []
for file in sar_files:
    filename = os.path.basename(file)
    parts = filename.split('_')
    if len(parts) != 6:
        continue
    mission, tuile, polar, orbiteS, orbiteN, date_part = parts
    date_str = date_part.split('t')[0]
    file_info.append({
        'file': file,
        'date_str': date_str,
        'mission': mission,
        'tuile': tuile,
        'polar': polar,
        'orbiteS': orbiteS,
        'orbiteN': orbiteN
    })
    print(f"File: {file}")
    print(f"Date: {date_str}")
    print(f"mission: {mission}, tuile: {tuile}, polar: {polar}, orbiteS: {orbiteS}, orbiteN: {orbiteN}")

# Organiser par dates
file_info = sorted(file_info, key=lambda x: x['date_str'])


# taille de l'image, la même pour toutes les tuiles
nn=10980
nbb=nn*nn

# Seuils pour la détection des nuances magenta
# meilleur seuil:
lower_magenta = np.array([120,60,20])
upper_magenta = np.array([155,255,255])

#   anciens seuils
#lower_magenta = np.array([125,90,50])
#upper_magenta = np.array([160,255,255])

# fonction pour le filtrage Lee
def lee_filter(img, size):
    img_mean = uniform_filter(img, (size, size))
    img_sqr_mean = uniform_filter(img**2, (size, size))
    img_variance = img_sqr_mean - img_mean**2
    overall_variance = variance(img)
    img_weights = img_variance / (img_variance + overall_variance)
    img_output = img_mean + img_weights * (img - img_mean)
    return img_output


# fonction pour créer une image composite rgb
def color_composite(red, green, blue):
    green = matplotlib.colors.Normalize(-30, 0, clip=True)(green)
    blue = matplotlib.colors.Normalize(-30, 0, clip=True)(blue)
    red = matplotlib.colors.Normalize(-30, 0, clip=True)(red)
    rgb=np.concatenate((red[:,:,None], green[:,:,None], blue[:,:,None]), axis=2)
    rgb2 = ((np.clip(rgb.copy(),0,1))*255).astype('uint8')
    return rgb2


for idx, info in enumerate(file_info):
    # Date à choisir pour les figures (ici la première, changez l'index si besoin)
    chosen_idx = 0  # 0 = première date, -1 = dernière, etc.
    chosen_info = file_info[chosen_idx]
    chosen_date_str = chosen_info['date_str']
    # choisir le bon fichier de reference
    ref_file = './Ref/'+info['tuile']+'_'+info['orbiteN']+'_'+info['polar']+'.tif'
    print(ref_file)
    with rasterio.open(ref_file) as src:
        ref = src.read(1)
        profile = src.profile
    #
    ref = np.nan_to_num(ref, nan=999)
    ref_db = 10 * np.log10(ref + 1e-10)
    ref_db = np.clip(ref_db, -30, 0)
    ref_norm = (ref_db + 30) / 30  # Normalize to 0-1
    #
    with rasterio.open(info['file']) as src:
        sar = src.read(1)
    #
    sar = np.nan_to_num(sar, nan=999)
    vsar=lee_filter(sar,3)
    sar_db = 10 * np.log10(vsar + 1e-10)
    #
    rgb=color_composite(ref_db, sar_db,ref_db)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)
    neige = reshape(reshape(cv2.inRange(hsv, lower_magenta, upper_magenta), nbb), (nn,nn))
    out_file = f"neige_{info['date_str']}.tif"
    profile.update(dtype='uint8', count=1)
    with rasterio.open(out_file, 'w', **profile) as dst:
        dst.write(neige, 1)
    #
    # Filtrage morphologique pour réduire les pixels isolés ===
    # Ouverture (érosion puis dilatation) 
    mask = (neige[:,:] == 255)
    cleaned_mask =  ndimage.binary_opening(mask, structure=np.ones((3,3)))
    cleaned_mask =  ndimage.binary_closing(cleaned_mask, structure=np.ones((3,3)))
    neige_fil = cleaned_mask.astype(np.uint8) * 255
    # plot d'une date
    if chosen_idx == 0:  # index/date a chosir pour les plots
        print(f"\nGénération de figures pour {chosen_date_str}...")

        fig, axs = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)

        # VH en dB
        im1 = axs[0, 0].imshow(sar_db, cmap='gray', vmin=-30, vmax=0)
        axs[0, 0].set_title(f'Backscatters (dB) {chosen_date_str}')
        axs[0, 0].axis('off')
        fig.colorbar(im1, ax=axs[0, 0], shrink=0.7, label='dB')

        # Composite RGB
        axs[0, 1].imshow(rgb)
        axs[0, 1].set_title('Composite RGB des backscatters')
        axs[0, 1].axis('off')

        # Detection Magenta sans filtrage
        axs[1, 0].imshow(sar_db, cmap='gray', vmin=-30, vmax=0)
        axs[1, 0].imshow(neige, cmap=ListedColormap(['none', 'cyan']), alpha=0.6)
        axs[1, 0].set_title(f'Neige humide {chosen_date_str}')
        axs[1, 0].axis('off')

        # Detection magenta avec filtrage morpho
        axs[1, 1].imshow(sar_db, cmap='gray', vmin=-30, vmax=0)
        axs[1, 1].imshow(neige_fil, cmap=ListedColormap(['none', 'cyan']), alpha=0.7)
        axs[1, 1].set_title(f'Neige humide filtrée {chosen_date_str}')
        axs[1, 1].axis('off')

        plt.savefig(f'Exemple_detection_{chosen_date_str}.png', dpi=300, bbox_inches='tight')
        plt.show()
    