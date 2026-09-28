"""
Magenta filter to remove snow from Sentinel-1 tiles.

The method comes from `dev/Magenta_method_v11jan2026.py` (Fatima
KARBOU's script): a false-color composite of the reference and current
backscatter is built, snow pixels are detected in HSV space as the "magenta"
hue, and isolated pixels are removed with a binary opening/closing.

Usage:
    uv run --script tools/filter_s1.py --datadir DIR --ref REF.tif --outdir OUT

For each ``*_vh_*.tif`` in ``--datadir``, the snow mask is written to
``--outdir`` as ``neige_<date>.tif``.
"""

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "matplotlib",
#     "opencv-python",
#     "rioxarray",
#     "scipy",
#     "tqdm",
#     "xarray",
# ]
# ///
import argparse
import glob
import os

import cv2
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import rioxarray as rxr
import xarray as xr
from matplotlib.colors import ListedColormap, Normalize
from scipy.ndimage import (
    binary_closing,
    binary_opening,
    uniform_filter,
    variance,
)
from tqdm import tqdm

matplotlib.use("Agg")

LOWER_MAGENTA = np.array([120, 60, 20])
UPPER_MAGENTA = np.array([155, 255, 255])


def lee_filter(img: np.ndarray, size: int) -> np.ndarray:
    """
    Apply a Lee filter to reduce speckle noise.

    Parameters
    ----------
    img : np.ndarray
        Input SAR backscatter image.
    size : int
        Size of the uniform filter window.

    Returns
    -------
    np.ndarray
        Speckle-filtered image.

    """
    img_mean = uniform_filter(img, (size, size))
    img_sqr_mean = uniform_filter(img**2, (size, size))
    img_variance = img_sqr_mean - img_mean**2
    overall_variance = variance(img)
    img_weights = img_variance / (img_variance + overall_variance)
    return img_mean + img_weights * (img - img_mean)


def color_composite(red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """
    Build a false-color RGB composite, normalizing each band to [-30, 0] dB.

    Parameters
    ----------
    red : np.ndarray
        Red channel, dB backscatter clipped to [-30, 0].
    green : np.ndarray
        Green channel, dB backscatter.
    blue : np.ndarray
        Blue channel, dB backscatter clipped to [-30, 0].

    Returns
    -------
    np.ndarray
        uint8 RGB image.

    """
    green = Normalize(-30, 0, clip=True)(green)
    blue = Normalize(-30, 0, clip=True)(blue)
    red = Normalize(-30, 0, clip=True)(red)
    rgb = np.concatenate(
        (red[:, :, None], green[:, :, None], blue[:, :, None]), axis=2
    )
    return ((np.clip(rgb.copy(), 0, 1)) * 255).astype("uint8")


def to_db(x: xr.DataArray) -> xr.DataArray:
    """
    Convert backscatter to decibels.

    Parameters
    ----------
    x : xr.DataArray
        Backscatter values.

    Returns
    -------
    xr.DataArray
        Values in dB.

    """
    return 10 * np.log10(x + 1e-10)


def clip_db(x: xr.DataArray) -> xr.DataArray:
    """
    Clip dB values to the [-30, 0] range used by the composite.

    Parameters
    ----------
    x : xr.DataArray
        dB values.

    Returns
    -------
    xr.DataArray
        Clipped dB values.

    """
    return np.clip(x, -30, 0)


def plot(
    suffix: str,
    sar: np.ndarray,
    rgb: np.ndarray,
    neige: np.ndarray,
    neige_fil: np.ndarray,
    plotdir: str,
) -> None:
    """
    Plot the raw S1 image, the RGB composite and the snow filtering.

    Parameters
    ----------
    suffix : str
        Date string used in titles and the output filename.
    sar : np.ndarray
        SAR backscatter in dB.
    rgb : np.ndarray
        False-color RGB composite.
    neige : np.ndarray
        Raw snow detection mask.
    neige_fil : np.ndarray
        Morphologically filtered snow mask.
    plotdir : str
        Directory where the figure is saved.

    """
    fig, axs = plt.subplots(2, 2, figsize=(12, 10), constrained_layout=True)

    im1 = axs[0, 0].imshow(sar, cmap="gray", vmin=-30, vmax=0)
    axs[0, 0].set_title(f"Backscatters (dB) {suffix}")
    axs[0, 0].axis("off")
    fig.colorbar(im1, ax=axs[0, 0], shrink=0.7, label="dB")

    axs[0, 1].imshow(rgb)
    axs[0, 1].set_title("Composite RGB des backscatters")
    axs[0, 1].axis("off")

    axs[1, 0].imshow(sar, cmap="gray", vmin=-30, vmax=0)
    axs[1, 0].imshow(neige, cmap=ListedColormap(["none", "cyan"]), alpha=0.6)
    axs[1, 0].set_title(f"Neige humide {suffix}")
    axs[1, 0].axis("off")

    axs[1, 1].imshow(sar, cmap="gray", vmin=-30, vmax=0)
    axs[1, 1].imshow(neige_fil, cmap=ListedColormap(["none", "cyan"]), alpha=0.7)
    axs[1, 1].set_title(f"Neige humide filtrée {suffix}")
    axs[1, 1].axis("off")

    plt.savefig(
        f"{plotdir}/Exemple_detection_{suffix}.png",
        dpi=300,
        bbox_inches="tight",
    )
    plt.close()


def parse_args() -> argparse.Namespace:
    """
    Parse the command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.

    """
    parser = argparse.ArgumentParser(
        prog="filter_s1.py",
        description="Remove snow from Sentinel-1 tiles with the magenta filter.",
    )
    parser.add_argument(
        "--datadir", required=True, help="directory containing the *vh*.tif files"
    )
    parser.add_argument(
        "--ref", required=True, help="reference backscatter tile (clipped to [-30, 0] dB)"
    )
    parser.add_argument(
        "--outdir", required=True, help="directory where neige_<date>.tif masks are written"
    )
    parser.add_argument(
        "--plotdir",
        default=None,
        help="directory where the detection figure is saved (requires --plot)",
    )
    parser.add_argument(
        "--glob",
        default="*_vh_*.tif",
        help="glob pattern for the SAR files in --datadir (default: *_vh_*.tif)",
    )
    parser.add_argument(
        "--coarsen",
        type=int,
        default=1,
        help="coarsening factor to reduce spatial resolution (default: 1)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="save a detection figure for the first date",
    )
    return parser.parse_args()


def main() -> None:
    """
    Apply the magenta filter to every SAR tile and save the snow masks.
    """
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    if args.plot:
        os.makedirs(args.plotdir, exist_ok=True)

    ref = rxr.open_rasterio(args.ref)
    if args.coarsen > 1:
        ref = ref.coarsen(x=args.coarsen, y=args.coarsen).mean()

    ref = ref.where(ref.notnull(), other=999)
    ref = xr.apply_ufunc(to_db, ref)
    ref = xr.apply_ufunc(clip_db, ref)

    sar_paths = sorted(glob.glob(os.path.join(args.datadir, args.glob)))
    for index, sar_path in enumerate(tqdm(sar_paths, desc="Applying magenta filter")):
        _, _, _, _, _, date = os.path.basename(sar_path).split("_")
        sar = rxr.open_rasterio(sar_path)
        if args.coarsen > 1:
            sar = sar.coarsen(x=args.coarsen, y=args.coarsen).mean()

        sar = sar.where(sar.notnull(), other=999)
        vsar = sar.copy(data=[lee_filter(sar.sel(band=1).values, 3)])
        sar_db = xr.apply_ufunc(to_db, vsar)

        rgb = color_composite(
            red=ref.sel(band=1).values,
            green=sar_db.sel(band=1).values,
            blue=ref.sel(band=1).values,
        )
        hsv = cv2.cvtColor(rgb, cv2.COLOR_BGR2HSV)
        neige = cv2.inRange(hsv, LOWER_MAGENTA, UPPER_MAGENTA)

        mask = neige == 255
        cleaned_mask = binary_opening(mask, structure=np.ones((3, 3)))
        cleaned_mask = binary_closing(cleaned_mask, structure=np.ones((3, 3)))
        neige_fil = cleaned_mask.astype(np.uint8) * 255

        out_path = os.path.join(args.outdir, f"neige_{date}.tif")
        sar.sel(band=1).copy(data=neige).rio.to_raster(out_path)

        if args.plot and index == 0:
            plot(
                suffix=date,
                sar=sar_db.sel(band=1).values,
                rgb=rgb,
                neige=neige,
                neige_fil=neige_fil,
                plotdir=args.plotdir,
            )


if __name__ == "__main__":
    main()
