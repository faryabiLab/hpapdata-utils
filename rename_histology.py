#!/usr/bin/env python3

"""
Copy and re-organize histology data in a new directory, whose structure
is consistent with the filesystem hierarchy required by cloud storage.

This script is based on:
https://github.com/faryabiLab/hpap-apps/blob/master/data_curator_tools/psv_pipelines/psv_histology_upload.py

The original version uses Pandas to parse the Excel file and match image
files. It was an overkill and made the code harder to understand, so
`pandas` was replaced by `openpyxl` when Excel file was read in.
"""

import os
import re
import shutil
import sys
import time

import openpyxl
import pandas as pd # dhu: delete it later

IMG_FILE_EXTENSION = '.ndpi' # extension of image files

unique_dict = dict()

anatomy_dict = {
    'pancreas': {
        'unsure': 'Pancreas - Unsure of orientation',
        'head': 'Head of pancreas',
        'tail': 'Tail of pancreas',
        'body': 'Body of pancreas'
    },
    'duodenum': {
        'unsure': 'Duodenum - Unsure of orientation',
        'distal': 'Duodenum - Distal one third',
        'mid': 'Duodenum - Mid one third',
        'proximal': 'Duodenum - Proximal one third',
        'prox': 'Duodenum - Proximal one third'
    },
    'LN': {
        'SMA': 'Lymph node - SMA',
        'sma': 'Lymph node - SMA',
        'body': 'Lymph node - Body of pancreas',
        'head': 'Lymph node - Head of pancreas',
        'mesentery': 'Lymph node - Mesentery',
        'mesentary': 'Lymph node - Mesentery',
        'mestentery': 'Lymph node - Mesentery',
        'tail': 'Lymph node - Tail of pancreas'
    },
    'spleen': 'Spleen',
    'thymus': 'Thymus',
    'artery': 'Artery'
}


def my_log(message, with_time=True):
    """Print a log message, with a prefix of current time."""

    if with_time:
        message = f"{time.ctime()}: {message}"

    print(message, flush=True)


def get_filename_key(input_filename, rm_extension):
    """
    Return a filename key, which includes only '_' and alphanumric in
    `input_filename`. If `rm_extension` is True, the extension will be
    also removed from the key before it's returned.
    """

    if rm_extension:
       input_filename = input_filename.rsplit('.', 1)[0]

    filename_key = ""
    for c in input_filename:
        if c == '_' or c == '-' or c.isalpha() or c.isdigit():
            filename_key += c

    if len(filename_key) == 0 or not filename_key.startswith('HPAP'):
        my_log("ERROR: invalid filename '{input_filename}'")
        sys.exit(1)

    return filename_key


def get_donor_id(input_str):
    """
    Return the donor ID from input_str.
    (assume thqat `input_str` is in the format of "HPAP xxx_whatever".
    """

    hpap_str = input_str.split('_', 1)[0]
    num_part = hpap_str.split('HPAP')[1]
    donor_id = num_part.zfill(3)

    return donor_id


def check_img_filenames(filenames):
    """
    Check input image filenames.
    If any of them has different HPAP donor ID, print an error and exit
    immediately.
    If everything is good, return the donor_id and a dict (whose key is
    normalized filename key, value is the actual image filename).
    """

    donor_id = None
    fn_map = dict()
    for fn in filenames:
        fn_key = get_filename_key(fn, rm_extension=True)
        current_donor_id = get_donor_id(fn_key)
        if donor_id is None:
            donor_id = current_donor_id
        elif donor_id != current_donor_id:
            print(f"ERROR: inconsistent donor ID in '{fn}'")
            sys.exit(1)

        if fn_key in fn_map:
            print(f"ERROR: duplicate filename key in '{fn}'")
            sys.exit(1)

        fn_map[fn_key] = fn

    return donor_id, fn_map


def check_src(src_dir):
    """Ensure that source data directory is in good shape."""

    src_dir = src_dir.replace("\\", "/").replace('"', '')
    if src_dir.endswith('/'):  # remove trailing '/'
        src_dir = src_dir[:-1]

    img_files = list()
    excel_files = list()
    for x in os.listdir(src_dir):
        if x.endswith(IMG_FILE_EXTENSION):
            img_files.append(x)
        elif x.endswith('.xlsx'):
            excel_files.append(x)

    # Make sure that one and only one Excel file is found in `src_dir`:
    if len(excel_files) == 0:
        my_log(f"ERROR: Excel file not found in {src_dir}")
        sys.exit(1)

    if len(excel_files) != 1:
        my_log(f"ERROR: multiple Excel files found in {src_dir}")
        sys.exit(1)

    num_img = len(img_files)
    if num_img == 0:
        my_log(f"ERROR: no image file found in '{src_dir}'")
        sys.exit(1)

    # Ensure that image filenames have identical donor IDs
    donor_id, fn_map = check_img_filenames(img_files)

    print(f"{num_img} image file(s) found in '{src_dir}'")
    excel_filename = f"{src_dir}/{excel_files[0]}"

    return donor_id, fn_map, excel_filename


def check_dest(dest_dir):
    """
    Ensure that destination directory either does not exist, or
    is an empty directory.
    """

    if not os.path.exists(dest_dir):
        return

    if not os.path.isdir(dest_dir):
        print(f"ERROR: '{dest_dir}' exists but is not a directory")
        sys.exit(3)

    if len(os.listdir(dest_dir)):
        print(f"ERROR: '{dest_dir}' is not an empty directory")
        sys.exit(4)


def check_excel_filenames(rows, excel_filename):
    """
    Ensure that each row in Excel includes same donor ID. If it does,
    return this donor ID.
    """

    donor_id = None
    for r, v in rows.items():
        current_donor_id = get_donor_id(r)
        if donor_id is None:
            donor_id = current_donor_id
        elif donor_id != current_donor_id:
            excel_val = v['filename_stem']
            print("ERROR: inconsistent donor ID in '{excel_val}' of '{excel_filename}'")
            sys.exit(1)

    return donor_id


def map_excel_columns(sheet_obj):
    """
    Read the first data row (not the one with column names) of input
    Excel sheet object and return a map between column number in Excel
    sheet and proper column name (which is NOT related to the column
    name in Excel).
    """

    max_col = sheet_obj.max_column
    col_num2name = dict()

    for c in range(1, max_col + 1):
        cell_obj = sheet_obj.cell(row=2, column=c)
        cell_val = cell_obj.value

        # If a column's value is empty or not a string, skip it.
        if cell_val is None or not isinstance(cell_val, str):
            continue

        cell_val = cell_val.strip()
        lower_val = cell_val.lower()

        # Skip columns that includes whitespace characters only
        if len(lower_val) == 0:
            continue

        if 'HPAP' in cell_val:
            col_num2name[c] = 'filename_stem'
            continue

        if 'oct' in lower_val or 'ffpe' in lower_val or 'vand' in lower_val:
            col_num2name[c] = 'stain'
            continue

    return col_num2name


def read_excel(filename, donor_id):
    """
    Read Excel spreadsheet, parse the data in each cell, and return a
    dict, whose key is a "normalized" filename key, and whose value is
    another dict of other columns.
    """

    # workbook and sheet objects
    wb_obj = openpyxl.load_workbook(filename, read_only=True)
    sheet_obj = wb_obj.active

    col_num2name = map_excel_columns(sheet_obj)

    # If `filename_stem` column is not found, print out an error and exit.
    if 'filename_stem' not in col_num2name.values():
        print(f"ERROR: HPAP column not found in '{filename}'")
        sys.exit(1)

    max_row = sheet_obj.max_row
    max_col = sheet_obj.max_column

    # Read the whole Excel file and create a dict, whose key is the value
    # of `filename_stem`, and whose value is another dict of other columns.
    rows = dict()
    for r in range(2, max_row + 1):
        current_row = dict()
        for c in range(1, max_col + 1):
            if c not in col_num2name:
                continue
            col_name = col_num2name[c]
            cell_val = sheet_obj.cell(row=r, column=c).value.strip()
            current_row[col_name] = cell_val

        filename_stem = current_row.get('filename_stem', '')
        row_key = get_filename_key(filename_stem, rm_extension=False)
        if len(row_key) == 0 or not row_key.startswith('HPAP'):
            print(f"ERROR: invalid HPAP value on row #{r} of '{filename_stem}'")
            sys.exit(1)

        if row_key in rows:
            print(f"ERROR: duplicate HPAP value on row #{r} of '{filename_stem}'")
            sys.exit(1)

        rows[row_key] = current_row

    excel_donor_id = check_excel_filenames(rows, filename)
    if excel_donor_id != donor_id:
        print(
            f"ERROR: donor ID in Excel ({excel_donor_id}) does not match "
            f"the one in image files ({donor_id})"
        )
        sys.exit(1)

    return rows


def match_excel_to_images(excel_dict, img_dict):
    """
    Match the data in Excel with actual image files.
    If everything is good, return a another dict maps each image file to
    a new filename (which will be saved in the destination directory.
    """

    # Ensure that each image file matches one row in Excel spreadsheet.
    for ik, iv in img_dict.items():
        if ik not in excel_dict():
            print(f"ERROR: image file '{iv}' not match any row in Excel")
            sys.exit(1)

    # Ensure that each row in Excel matches one image file
    src2dest = dict()
    dest_key_counter = dict()
    for xk, xv in excel_dict.items():
        if xk not in img_dict():
            cell_v = xv['filename_stem']
            print(f"ERROR: '{cell_v}' not match any image files")
            sys.exit(1)

        anatomy = get_anatomy(xk)
        short_anatomy = get_short_anatomy(anatomy)
        excel_stain = xv['stain']
        new_stain = rename_stain(excel_stain)
        anatomy = anatomy.replace(" ", "-").str.replace("---", "-")
        dest_key = "_".join(
            [
                f"HPAP-{donor_id}",
                "Histology",
                anatomy,
                new_stain,
                "H-and-E",
            ]
        )

        counter = dest_key_counter.get(dest_key, 0)
        uniq_num = counter + 1
        dest_key_counter[dest_key] = uniq_num

        dest_name = f"{dest_key}_{uniq_num}{IMG_FILE_EXTENSION}"
        src_img_filename = img_dict[xk]

        src2dest[src_img_filename] = {
            'dir': short_anatomy,
            'filename': dest_name,
        }

        return src2dest


def get_anatomy(value):
    pan = re.findall("(pancreas)\\s?-?\\s?(\\w+)", value)
    spl = re.findall("(spleen)", value)
    lyn = re.findall("(LN)\\s?-?\\s?(\\w+)?", value)
    duo = re.findall("(duodenum)\\s?-?\\s?(\\w+)?|(duod)\\s?(\\w+)?", value)
    thy = re.findall("(thymus)\\s?\n?", value)
    art = re.findall("(artery)\\s?\n?", value)
    rand = re.findall("(Mesentery opo)", value)

    # Remove empty findall results
    finds = [
        x[0] for x in [pan, spl, lyn, duo, thy, art, rand] if len(x) > 0
    ]

    # Remove empty nested `findall` results
    finds_final = []
    for find in finds:
        if type(find) == tuple:
            for sub_find in find:
                if len(sub_find) > 0:
                    if sub_find == 'duod':
                        sub_find = 'duodenum'
                    finds_final.append(sub_find)
        else:
            finds_final.append(find)

    # Ensure that either one or two keywords are found
    num_keywords = len(finds_final)
    if num_keywords == 0 or num_keywords > 2:
        my_log(f"Number of keys not match in parse_anatomy(): {value}")
        sys.exit(1)

    # Ensure that the first keyword in anatomy_dict
    key1 = finds_final[0]
    if key1 not in anatomy_dict:
        my_log(f"Key #1 not found in anatomy_dict: {key1}")
        sys.exit(1)

    # Only one keyword is found
    if num_keywords == 1:
        if key1 == 'pancreas':
            return 'Pancreas'

        if key1 == 'duodenum':
            return 'Duodenum'

        if key1 == 'LN':
            return 'Lymph node'

        return anatomy_dict[key1]

    # Two keywords are found
    key2 = finds_final[1]
    try:
        return anatomy_dict[key1][key2]
    except KeyError:
        my_log(f"ERROR: key #2 not found in anatomy_dict: {key2}")
        sys.exit(1)


def rename_stain(input_str):
    input_str = input_str.strip().upper()

    if input_str == "OCT":
        return 'OCT-flash-frozen'

    if 'VAN' in input_str:
        return 'OCT-lightly-fixed'

    return input_str


def match_img_path(df_data, file_paths):
    df_copy = df_data.copy()

    # Find each image file's stem (w/o extension and trailing whitespace chars)
    filename_keys = [
        get_filename_key(os.path.basename(fp).rsplit('.', 1)[0])
        for fp in file_paths
    ]

    file_pairs = list(zip(filename_keys, file_paths))

    if (df_copy['img_id'] == 'NA').all():
        # New Excel format: all values in 'Image ID' column are blank
        merge_col = 'filename_key'
    else:
        # OLD Excel format: values in 'Image ID' column are image files' name
        # (without extension)
        merge_col = 'img_id'

    file_pairs_df = pd.DataFrame(file_pairs, columns=[merge_col, 'filepath'])
    return df_copy.merge(file_pairs_df, on=merge_col)


def get_short_anatomy(input_str):
    anatomy_lower = input_str.lower()

    if "artery" in anatomy_lower:
        return "Artery"

    if 'bone marrow' in anatomy_lower:
        return "Bone Marrow"

    if 'duodenum' in anatomy_lower:
        return "Duodenum"

    if 'lymph node' in anatomy_lower:
        return "Lymph node"

    if 'pancreas' in anatomy_lower:
        return "Pancreas"

    if 'spleen' in anatomy_lower:
        return "Spleen"

    if 'thymus' in anatomy_lower:
        return "Thymus"

    my_log(f"get_short_anatomy_name(): no match for '{input_str}'")
    sys.exit(1)


def get_unique_num(input_str):
    """Return a unique number identifier."""

    tokens = input_str.split('_')
    donor = tokens[0]
    anatomy = tokens[2]
    stain = tokens[3]

    if donor not in unique_dict.keys():
        unique_dict[donor] = dict()

    if anatomy not in unique_dict[donor].keys():
        unique_dict[donor][anatomy] = dict()

    if stain not in unique_dict[donor][anatomy].keys():
        unique_dict[donor][anatomy][stain] = 1
        return unique_dict[donor][anatomy][stain]

    unique_dict[donor][anatomy][stain] += 1

    return unique_dict[donor][anatomy][stain]


def map_src_to_dest(src_dir, img_files, excel_filename):
    """
    Map each source image file to a new filename that will be uploaded
    to the cloud storage.
    """

    # Read Excel file
    excel_data = read_excel(excel_filename)

    # Add new columns to match each row in Excel with an image file:
    clean_histology['filename_key'] = clean_histology['raw_info'].apply(
        get_filename_key
    )

    clean_histology['polished_info'] = clean_histology['raw_info'].apply(
        get_polished_info
    )

    clean_histology['donor'] = clean_histology['polished_info'].apply(parse_donor)
    # dhu: ensure that all donor IDs are identical

    clean_histology['anatomy'] = clean_histology['polished_info'].apply(parse_anatomy)
    clean_histology.drop('polished_info', axis=1, inplace=True)
    clean_histology['renamed_stain'] = clean_histology['stain'].apply(rename_stain)

    my_log("Map image filenames ...")

    img_paths = [
        os.path.abspath(src_dir + "/" + x) for x in img_files
    ]
    clean_histology = match_img_path(clean_histology, img_paths)

    # Ensure that there's at least one row in `clean_histology` table:
    if clean_histology.shape[0] == 0:
        my_log("ERROR: matched image files not found")
        sys.exit(1)

    # Ensure that each image file in `src_dir` matches ONE AND ONLY ONE
    # row in Excel:
    img_set = set(img_files)
    excel_set = {os.path.basename(f) for f in clean_histology['filepath']}
    if img_set > excel_set:
        unmatched = sorted(img_set - excel_set)
        my_log(
            f"ERROR: {len(unmatched)} image file(s) in '{src_dir}' can not be "
            f"matched with '{excel_files[0]}':"
        )
        for idx, f in enumerate(unmatched, start=1):
            my_log(f"  ({idx}) '{f}'", with_time=False)
        sys.exit(1)

    # Create a new column for short anatomy name
    clean_histology['short_anatomy'] = clean_histology['anatomy'].apply(
        get_short_anatomy
    )

    clean_histology['dest_name'] = (
        clean_histology['donor'].astype(str) + "_Histology_" +
        clean_histology['anatomy'].str.replace(" ", "-").str.replace("---", "-") +
        "_" + clean_histology["renamed_stain"] + "_H-and-E"
    )

    clean_histology.sort_values(
        ['anatomy', 'renamed_stain', 'img_id'], inplace=True
    )

    clean_histology['unique_num'] = clean_histology['dest_name'].apply(
        get_unique_num
    ).astype(str)

    clean_histology['dest_name'] = (
        clean_histology['dest_name'] + '_' + clean_histology['unique_num'] +
        IMG_FILE_EXTENSION
    )

    src2dest = clean_histology[
        ['filepath', 'short_anatomy', 'dest_name']
    ].sort_values(['filepath']).to_dict('list')

    return src2dest


def copy_src_to_dest(src2dest, dest_dir):
    """Copy source image files to the destination directory."""

    os.makedirs(dest_dir, exist_ok=True)

    src_paths = src2dest['filepath']
    anatomies = src2dest['short_anatomy']
    dest_names = src2dest['dest_name']

    for idx, src in enumerate(src_paths):
        dest_basename = dest_names[idx]
        parent_dir = os.path.join(dest_dir, anatomies[idx])
        os.makedirs(parent_dir, exist_ok=True)
        dest_path = os.path.join(parent_dir, dest_basename)

        my_log(f"Copying '{src}' ...")
        shutil.copy(src, dest_path)


# ============================ Main program ==================================

if __name__ == "__main__":
    args = sys.argv

    if len(args) != 3:
        print("Usage: rename_histology.py <source_data_dir> <target_data_dir>")
        sys.exit(1)

    # Parse arguments
    src_dir = args[1]
    dest_dir = args[2]

    # Make sure that source directory is good
    donor_id, fn_map, excel_filename = check_src(src_dir)

    rows = read_excel(excel_filename, donor_id)

    #import json; print(json.dumps(rows, indent=2)); sys.exit(0)  # dhu test
    for x in fn_map:
        if x not in rows:
            print(x)

    for x in rows:
        if x not in fn_map:
            print(x)

    sys.exit(0)

    # Make sure that destination directory is good:
    check_dest(dest_dir)

    # Create a map between source image file and destination image file
    src2dest = map_src_to_dest(src_dir, img_files, excel_filename)

    # Copy image files from source to destination
    copy_src_to_dest(src2dest, dest_dir)

    my_log("Done!")


### TO-DO:
# 1. Create "dest/HPAP-xxx/Histology/" structure
# 2. Modify a few source files, then copy them, and confirm that the dest files are identical.
