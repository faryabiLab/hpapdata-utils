#!/usr/bin/env python3

"""
Copy and re-organize histology data in a new directory, whose structure
is consistent with the filesystem hierarchy required by cloud storage.
"""

import datetime
import os
import pandas as pd
import re
import shutil
import sys
import time

IMG_FILE_EXTENSION = '.ndpi' # extension of image files

pd.options.mode.chained_assignment = None
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

    my_log(f"{num_img} image file(s) found in '{src_dir}'")

    excel_filename = f"{src_dir}/{excel_files[0]}"
    return img_files, excel_filename


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


def is_date_str(input_str):
    if re.findall('\\d{2,4}-\\d{1,2}-\\d{1,2}', input_str):
        return True

    if re.findall('\\d{1,2}/\\d{1,2}/\\d{2,4}', input_str):
        return True

    return False

def format_histology_df(df):
    df_clone = df.copy()

    # If the first row is header line, skip it.
    if 'prep' in [str(x).lower() for x in df_clone.iloc[0, :].values.tolist()]:
        df_clone = df_clone.iloc[1:, :]

    # A map whose key is Excel column name, and value is new column name
    col_dict = dict()

    for col in df_clone.columns:
        col_vals = df_clone[col].values.astype(str).tolist()
        first_val = col_vals[0]
        first_lower = first_val.lower()
        if 'HPAP' in first_val:
            col_dict[col] = 'raw_info'
        elif 'oct' in first_lower or 'ffpe' in first_lower or 'vand' in first_lower:
            col_dict[col] = 'stain'
        elif first_val == '6489':
            df_clone.drop(col, axis=1, inplace=True)
        elif is_date_str(first_val):
            # Skip date columns (such as "Captured Date" and "Upload Date")
            df_clone.drop(col, axis=1, inplace=True)
        elif 'nan' not in first_val:
            int_first = int(float(first_val))
            if int_first > 10000:
                col_dict[col] = 'img_id'
                if 'no tissue' in df_clone[col].values:
                    drop_idx = df_clone.index[df_clone[col] == 'no tissue'].tolist()
                    df_clone.drop(drop_idx, axis=0, inplace=True)
            elif int_first == 1 or int_first == 426:
                df_clone.drop(col, axis=1, inplace=True)
        elif 'nan' in first_val:
            df_clone.drop(col, axis=1, inplace=True)

    df_clone.rename(columns=col_dict, inplace=True)

    # Since October 2021, all values in "Image ID" column of Excel file
    # are blank. In order to keep them compatible with the old format,
    # all blank image IDs are set to 'NA'.
    if 'img_id' not in df_clone.columns:
        df_clone['img_id'] = 'NA'

    # Drop rows whose value in 'raw_info' column is missing
    dropped_idx = df_clone[df_clone['raw_info'].isna()].index
    df_clone.drop(dropped_idx, inplace=True)

    # Drop rows with null image id values
    dropped_idx = df_clone[df_clone['img_id'].isnull()].index
    df_clone.drop(dropped_idx, inplace=True)

    return df_clone


def get_filename_key(input_str):
    """
    Return a filename key, which includes only '_' and digits in `input_str`.
    """

    filename_key = ""
    for c in input_str:
        if c == '_' or c.isdigit():
            filename_key += c

    if len(filename_key) == 0:
        my_log("ERROR: filename key not found in '{input_str}'")
        sys.exit(1)

    return filename_key


def get_polished_info(input_str):
    polished_str = input_str.strip()

    if polished_str.startswith('HPAP '):
        polished_str = input_str.replace('HPAP ', 'HPAP')

    if '_' not in polished_str or 'HPAP' not in polished_str:
        print("ERROR: invalid filename in Excel: '{input_str}'")
        sys.exit(1)

    tokens = polished_str.split("_", 1)
    donor = tokens[0].strip()
    donor_id = donor.split("HPAP")[1].zfill(3)

    return f"HPAP{donor_id}_{tokens[1]}"


def parse_donor(input_str):
    donor = input_str.replace("HPPAP", 'HPAP').split(" ", 1)[0].strip().rsplit("_")[0]
    padded_id = donor.split("HPAP")[-1].zfill(3)

    return f"HPAP-{padded_id}"


def parse_anatomy(value):
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

    # Read the Excel file
    my_log("Reading Excel file ...")
    raw_histology = pd.read_excel(io=excel_filename, header=None)

    # Polish the data in Excel file
    clean_histology = format_histology_df(raw_histology)

    # Add new columns to match each row in Excel with an image file:
    clean_histology['filename_key'] = clean_histology['raw_info'].apply(
        get_filename_key
    )

    clean_histology['polished_info'] = clean_histology['raw_info'].apply(
        get_polished_info
    )

    clean_histology['donor'] = clean_histology['polished_info'].apply(parse_donor)
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
    img_files, excel_filename = check_src(src_dir)

    # Make sure that destination directory is good
    check_dest(dest_dir)

    # Create a map between source image file and destination image file
    src2dest = map_src_to_dest(src_dir, img_files, excel_filename)

    # Copy image files from source to destination
    copy_src_to_dest(src2dest, dest_dir)

    my_log("Done!")
