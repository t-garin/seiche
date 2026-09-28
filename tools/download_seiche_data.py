"""
Quality of life script to download data from https://mercure.cerfacs.fr/seiche.
"""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "tqdm>=4.67.3",
# ]
# ///
import argparse
import os
import sys
import urllib.request
import zipfile
import ssl

from tqdm import tqdm

ssl._create_default_https_context = ssl._create_unverified_context

SERVER = "https://mercure.cerfacs.fr/seiche"

ARCHIVES = {
    "opentelemac": f"{SERVER}/opentelemac_python3_20240430.zip",
    "marmande": [
        f"{SERVER}/marmande_2019_inp.zip",
        f"{SERVER}/marmande_2021_inp.zip",
        f"{SERVER}/marmande_2022_inp.zip",
        f"{SERVER}/marmande_2026_inp.zip",
    ],
    "marmande_2019": [
        f"{SERVER}/marmande_2019_inp.zip",
    ],
    "marmande_2021": [
        f"{SERVER}/marmande_2021_inp.zip",
    ],
    "marmande_2022": [
        f"{SERVER}/marmande_2022_inp.zip",
    ],
    "marmande_2026": [
        f"{SERVER}/marmande_2026_inp.zip",
    ],
    "stomer": [
        f"{SERVER}/stomer_inp.zip",
    ],
    "ohio": [
        f"{SERVER}/ohio_2018_inp.zip",
        f"{SERVER}/ohio_2025_inp.zip",
    ],
    "ohio_2018": [
        f"{SERVER}/ohio_2018_inp.zip",
    ],
    "ohio_2025": [
        f"{SERVER}/ohio_2025_inp.zip",
    ],
    "chinon": [
        f"{SERVER}/chinon_inp.zip",
    ],
}


def download_file(url, filename, dest_folder=".", max_name_length=0):
    """
    Download file from a given url to dest_folder, and display nicely using tqdm.
    """
    try:
        os.makedirs(dest_folder, exist_ok=True)
        filepath = os.path.join(dest_folder, filename)

        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get("content-length", 0))

        if total_size == 0:
            print(f"⚠ Warning: Could not determine file size for {filename}")

        with tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            miniters=1,
            desc=f"dwnld {filename.ljust(max_name_length, '.')}...",
            bar_format="{desc} {percentage:>6.2f}%|{bar:50}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        ) as progressbar:

            def reporthook(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if downloaded > total_size and total_size > 0:
                    progressbar.update(total_size - progressbar.n)
                else:
                    progressbar.update(downloaded - progressbar.n)

            urllib.request.urlretrieve(url, filepath, reporthook=reporthook)
        return True
    except Exception as e:
        print(f"✗ Failed to download {filename}: {e}", file=sys.stderr)
        return False


def unzip_file(filename, dest_folder=".", max_name_length=0):
    """
    Unzips a .zip file and display nicely using tqdm.
    """
    try:
        filepath = os.path.join(dest_folder, filename)
        with zipfile.ZipFile(filepath, "r") as zip_ref:
            members = zip_ref.namelist()
            for member in tqdm(
                members,
                desc=f"unzip {filename.ljust(max_name_length, '.')}...",
                bar_format="{desc} {percentage:>6.2f}%|{bar:50}| {n}/{total} [{elapsed}<{remaining}, {rate_fmt}]",
            ):
                zip_ref.extract(member, dest_folder)
        return True
    except Exception as e:
        print(f"✗ Failed to unzip {filename}: {e}", file=sys.stderr)
        return False


def main():
    """
    Main function for the CLI tool.
    """
    parser = argparse.ArgumentParser(
        description="Download and unzip archives from a remote server."
    )

    for archive_name in ARCHIVES.keys():
        parser.add_argument(
            f"--{archive_name}",
            action="store_true",
            help=f"Download {archive_name} archive",
        )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available archives",
    )

    parser.add_argument(
        "--unzip", action="store_true", help="Unzip downloaded archives"
    )

    parser.add_argument(
        "dest",
        nargs="?",
        default=".",
        help="Destination folder (default: current working directory)",
    )

    args = parser.parse_args()

    if args.all:
        to_download = list(ARCHIVES.keys())
    else:
        to_download = [name for name in ARCHIVES.keys() if getattr(args, name)]

    if not to_download:
        parser.print_help()
        return

    urls_to_download = []
    for archive_name in to_download:
        archive_urls = ARCHIVES[archive_name]
        if isinstance(archive_urls, str):
            urls_to_download.append(archive_urls)
        else:
            urls_to_download.extend(archive_urls)

    max_name_length = max(len(url.split("/")[-1]) for url in urls_to_download)

    downloaded_files = []
    for url in urls_to_download:
        filename = url.split("/")[-1]

        if download_file(url, filename, args.dest, max_name_length):
            downloaded_files.append(filename)

    if args.unzip:
        for filename in downloaded_files:
            unzip_file(filename, args.dest, max_name_length)


if __name__ == "__main__":
    main()
