#!/usr/bin/env python3

"""
This script is written for the GitHub issue of:
https://github.com/faryabiLab/hpap-hub/issues/116

It copies "HPAP-*.tiff" files from a source directory to a target
directory. Both the target directory's structure and tiff files' names
are "normalized" (based on the information embedded in original tiff
file's name) so that they can be uploaded into Pennsieve by
`psv-upload.bash` command.

The legacy code in original Jupyter Notebook can be found at:
`legacy/upload_imc.py`
"""

import os
import shutil
import sys

if len(sys.argv) != 3:
    print("Usage: rename_imc.py <source_data_dir> <target_data_dir>")
    sys.exit(1)

# Verify data source directory
src_dir_arg = sys.argv[1]
if not os.path.isdir(src_dir_arg):
    print(f"Error: '{src_dir_arg}' does not exist or is not a directory")
    sys.exit(2)

abs_src_dir = os.path.abspath(src_dir_arg) # convert source dir to absolute path

# Destination data directory must be empty
dest_dir_arg = sys.argv[2]
if not os.path.exists(dest_dir_arg):
    os.makedirs(dest_dir_arg)
elif not os.path.isdir(dest_dir_arg):
    print(f"Error: '{dest_dir_arg}' is not a directory")
    sys.exit(3)
elif len(os.listdir(dest_dir_arg)):
    print(f"Error: '{dest_dir_arg}' is not empty")
    sys.exit(4)

# Convert destination dir to absolute path
abs_dest_dir = os.path.abspath(dest_dir_arg)

# Copy source "*.tiff" files to `abs_dest_dir` with a new name
for src_dir, _, files, in os.walk(abs_src_dir):
    for src_name in files:
        # Only process "HPAP-*.tiff" files
        if not src_name.startswith('HPAP-') or not src_name.endswith(".tiff"):
            continue

        tokens = src_name.split('_')
        # If the number of tokens is less than 6, skip this file.
        if len(tokens) < 6:
            print(f"Warning: invalid source filename ('{src_name}'), skipped")
            continue

        donor_id = tokens[0]
        anatomy = tokens[2]
        if anatomy == "Indeterminate-of-pancreas":
            anatomy = "Pancreas-unsure-of-orientation"
        region = tokens[3]
        overlay = tokens[4]
        conjugate = tokens[5].split('.')[0]

        dest_dir = os.path.join(
            abs_dest_dir,
            donor_id,
            "Imaging mass cytometry",
            anatomy.replace("-", " "),
            "FFPE-Stain Panel 1",
            region
        )

        dest_name = "_".join(
            [donor_id, "IMC", anatomy, region, overlay, conjugate]
        ) + ".tiff"

        os.makedirs(dest_dir, exist_ok=True)

        src_path = os.path.join(src_dir, src_name)
        dest_path = os.path.join(dest_dir, dest_name)

        print(f"Copying '{src_name}'")
        shutil.copy(src_path, dest_path)


donors = [x for x in os.listdir(abs_dest_dir) if x.startswith('HPAP-')]
if len(donors) == 0:
    print(f"Valid IMC data not found in '{src_dir_arg}', exit")
    sys.exit(5)

print("\nRun the following command(s) to upload your IMC data:")
print("-----------------------------------------------------\n")
for donor_id in donors:
    donor_path = os.path.join(abs_dest_dir, donor_id)
    print(f"psv-upload.bash '{donor_path}' '{donor_id}'")

print()
