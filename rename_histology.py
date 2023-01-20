#!/usr/bin/env python3

"""Upload histology data to Pennsieve server."""

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
        elif regex_matched('\\d{4}-\\d{2}-', first_val):
            # skip date columns (such as "Captured Date" and "Upload Date")
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


def fix_dataset_name(input_str):
    polished_str = input_str.strip()

    if polished_str.startswith('HPAP '):
        polished_str = input_str.replace('HPAP ', 'HPAP')

    donor = polished_str.split("_", 1)[0].strip()
    rest_of_str = "_" + polished_str.split("_", 1)[1]
    donor_id = donor.split("HPAP")[1].zfill(3)

    return f"HPAP{donor_id}{rest_of_str}"


def get_filename_key(input_str):
    filename_key = ""
    for c in input_str:
        if c == '_' or c.isdigit():
            filename_key += c

    if len(filename_key) == 0:
        my_log("ERROR: filename key not found in '{input_str}'")
        sys.exit(1)

    return filename_key


def parse_donor(value):
    donor = value.strip().replace("HPPAP", 'HPAP').split(" ", 1)[0].strip().rsplit("_")[0]
    padded_id = donor.split("HPAP")[-1].zfill(3)

    return f"HPAP-{padded_id}"


def regex_matched(regex, string):
    return len(re.findall(regex, string)) > 0


def parse_anatomy(value):
    pan = re.findall("(pancreas)\\s?-?\\s?(\\w+)", value)
    spl = re.findall("(spleen)", value)
    lyn = re.findall("(LN)\\s?-?\\s?(\\w+)?", value)
    duo = re.findall("(duodenum)\\s?-?\\s?(\\w+)?|(duod)\\s?(\\w+)?", value)
    thy = re.findall("(thymus)\\s?\n?", value)
    art = re.findall("(artery)\\s?\n?", value)
    rand = re.findall("(Mesentery opo)", value)

    # Remove empty findall results
    finds = [x[0] for x in [pan, spl, lyn, duo, thy, art, rand] if len(x) > 0]

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
        my_log(f"Key #2 not found in anatomy_dict: {key2}")
        sys.exit(1)


def stain_for_upload(value):
    if value.upper().strip() == "OCT":
        return 'OCT'

    if 'VAN' in value.upper().strip():
        return 'VANDERBILT'

    return value.upper()


def parse_stain(value):
    if value.upper().strip() == "OCT":
        return 'OCT-flash-frozen'

    if 'VAN' in value.upper().strip():
        return 'OCT-lightly-fixed'

    return value.upper()


def match_img_path(sheet_data, file_paths):
    sheet_copy = sheet_data.copy()

    # Find each image file's basename (w/o extension and trailing whitespace chars)
    filename_keys = [
        get_filename_key(os.path.basename(fp).rsplit('.', 1)[0])
        for fp in file_paths
    ]

    file_pairs = list(zip(filename_keys, file_paths))

    if (sheet_copy['img_id'] == 'NA').all():
        # New Excel format: all values in 'Image ID' column are blank
        merge_col = 'filename_key'
    else:
        # OLD Excel format: values in 'Image ID' column are image files' name
        # (without extension)
        merge_col = 'img_id'

    file_pairs_df = pd.DataFrame(file_pairs, columns=[merge_col, 'filepath'])
    return sheet_copy.merge(file_pairs_df, on=merge_col)


def psv_destination(row):
    anatomy_str = str(row["anatomy"])
    anatomy_lower = anatomy_str.lower()
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

    my_log(f"psv_destination(): no match for '{anatomy_str}'")
    sys.exit(1)


# Add the unique num identifier
def unique_name(value):
    splt_val = value.split('_')
    donor = splt_val[0]
    anatomy = splt_val[2]
    stain = splt_val[3]

    if donor not in unique_dict.keys():
        unique_dict[donor] = dict()

    if anatomy not in unique_dict[donor].keys():
        unique_dict[donor][anatomy] = dict()

    if stain not in unique_dict[donor][anatomy].keys():
        unique_dict[donor][anatomy][stain] = 1
        return unique_dict[donor][anatomy][stain]

    unique_dict[donor][anatomy][stain] += 1

    return unique_dict[donor][anatomy][stain]


def upload_to_psv(row):
    """Upload an image file to Pennseive server."""

    file_path = row['filepath']
    if not os.path.isfile(file_path):
        my_log(f"ERROR: '{file_path}' not exist")
        return

    img_basename = os.path.basename(file_path)
    collection_id = row['Colid']
    psv_item = psv.get(collection_id)

    pack_items = [x.name for x in psv_item.items]
    img_id = row['img_id']
    new_name = row['new_name']

    file_found = None
    if img_id != 'NA' and img_id in pack_items:
        file_found = img_id
    elif img_id == 'NA' and img_basename in pack_items:
        file_found = img_basename
    elif new_name in pack_items:
        file_found = new_name

    if file_found:
        my_log(f"'{file_found}' already exists on Pennsieve server, skipped")
        return

    my_log(f"Upload '{img_basename}' ...")
    abs_path = os.path.abspath(file_path)
    psv_item.upload(abs_path, display_progress=True)
    psv_item.update()
    my_log(f"'{img_basename}' uploaded")


def rename_file(row):
    """Rename an image file on Pennsieve server."""

    psv_collection = psv.get(row['Colid'])
    img_id = row['img_id']
    new_name = row['new_name']
    img_basename = os.path.basename(row['filepath'])

    # Get target package to rename
    pack = None
    for x in psv_collection.items:
        if x.name == new_name:
            pack = psv.get(x.id)
            return False

        if img_id != 'NA' and x.name == img_id:
            pack = psv.get(x.id)
            break

        if img_id != 'NA' and x.get_property('aperio.ImageID') == img_id:
            pack = psv.get(x.id)
            break

        if img_id == 'NA' and x.name == img_basename:
            pack = psv.get(x.id)
            break

    if pack is None:
        my_log(f"'{new_name}': package not found on Pennsieve server")
        return False

    old_name = pack.name
    pack.name = new_name
    pack.update()
    my_log(f"'{old_name}' renamed to '{new_name}'")
    return True


# ============================ Main program ==================================

if __name__ == "__main__":
    args = sys.argv

    if len(args) != 5:
        my_log(
            f"'{args[0]}' requires 4 arguments but only finds {len(args) - 1}",
            with_time=False
        )
        if len(args) > 1:
            my_log(' '.join(args[1:]), with_time=False)

        my_log(
            f"Usage: "
            f"{args[0]} <sql_user> <sql_passwd> <sql_port> <image_dir>",
            with_time=False
        )
        sys.exit(1)

    # Parse arguments
    sql_user = args[1]
    sql_pass = args[2]
    sql_port = args[3]
    img_dir = args[4]

    img_dir = img_dir.replace("\\", "/").replace('"', '')
    if img_dir.endswith('/'):  # remove trailing '/'
        img_dir = img_dir[:-1]

    img_files = list()
    excel_files = list()
    for x in os.listdir(img_dir):
        if x.endswith(IMG_FILE_EXTENSION):
            img_files.append(x)
        elif x.endswith('.xlsx'):
            excel_files.append(x)

    # Make sure that one and only one Excel file is found in `img_dir`:
    if len(excel_files) == 0:
        my_log(f"Excel file not found in {img_dir}")
        sys.exit(1)

    if len(excel_files) != 1:
        my_log(f"Multiple Excel files found in {img_dir}")
        sys.exit(1)

    num_img = len(img_files)
    if num_img == 0:
        my_log(f"No image file found in '{img_dir}'")
        sys.exit(1)

    my_log(f"{num_img} image file(s) found in '{img_dir}'")

    img_paths = [
        os.path.abspath(img_dir + "/" + x) for x in img_files
    ]

    # Read Excel file, which is included in `img_dir`
    my_log("Reading Excel file ...")
    excel_filename = f"{img_dir}/{excel_files[0]}"
    raw_histology = pd.read_excel(io=excel_filename, header=None)

    # Polish the data in Excel file
    clean_histology = format_histology_df(raw_histology)

    # Add a new column to match each row in Excel with each image file in `img_dir`
    clean_histology['filename_key'] = clean_histology['raw_info'].apply(get_filename_key)

    clean_histology['polished_info'] = clean_histology['raw_info'].apply(fix_dataset_name)
    clean_histology.loc[:, 'donor'] = clean_histology['polished_info'].apply(parse_donor)
    clean_histology.loc[:, 'anatomy'] = clean_histology['polished_info'].apply(parse_anatomy)
    clean_histology.drop('polished_info', axis=1, inplace=True)

    clean_histology.loc[:, 'stain'] = clean_histology['stain'].apply(stain_for_upload)
    clean_histology.loc[:, 'renamed_stain'] = clean_histology['stain'].apply(parse_stain)

    my_log("Preparing for upload: generate new names ...")
    clean_histology = match_img_path(clean_histology, img_paths)

    # Ensure that there's at least one row in `clean_histology` table:
    if clean_histology.shape[0] == 0:
        my_log("ERROR: no matched image files found")
        sys.exit(1)

    # Ensure that each image file in `img_dir` gets matched with 1 row in Excel
    img_set = set(img_files)
    excel_set = {os.path.basename(f) for f in clean_histology['filepath']}
    if img_set > excel_set:
        unmatched = sorted(img_set - excel_set)
        my_log(
            f"ERROR: {len(unmatched)} image file(s) in '{img_dir}' can not be "
            f"matched with '{excel_files[0]}':"
        )
        for idx, f in enumerate(unmatched, start=1):
            my_log(f"  ({idx}) '{f}'", with_time=False)
        sys.exit(1)


    # Shorten the anatomy name to just the collection header
    clean_histology['psv_dest'] = clean_histology.apply(
        lambda row: psv_destination(row), axis=1
    )

    clean_histology.loc[:, 'new_name'] = (
        clean_histology['donor'].astype(str) + "_Histology_" +
        clean_histology['anatomy'].str.replace(" ", "-").str.replace("---", "-") +
        "_" + clean_histology["renamed_stain"] + "_H-and-E"
    )

    clean_histology.sort_values(
        ['anatomy', 'renamed_stain', 'img_id'], inplace=True
    )

    clean_histology['unique_num'] = clean_histology['new_name'].apply(
        unique_name
    ).astype(str)

    clean_histology['new_name'] = (
        clean_histology['new_name'] + '_' + clean_histology['unique_num']
    )

    col_df["donor"] = col_df["Dataset"].str.split(" ").str[0].str.strip()

    # Merge datasets together for final record keeping and upload
    my_log("Combining collections with files ...")
    merged_data = clean_histology.merge(
        col_df[["Colname", "Colpath", "Colid", "donor"]],
        how='left',
        left_on=["donor", "psv_dest"],
        right_on=["donor", "Colname"]
    )

    if merged_data['Colid'].isna().all():
        my_log("No matching collections found in Pennsieve server, exiting")
        sys.exit(1)

    my_log("Recording new histology files to HPAP 'histology_master' table ...")
    record_df = merged_data[
        [
            'raw_info',
            'stain',
            'img_id',
            'donor',
            'anatomy',
            'renamed_stain',
            'unique_num'
        ]
    ]

    # Rename 'raw_info' column to 'file_name_ref'
    record_df.rename(columns={'raw_info': 'file_name_ref'}, inplace=True)


    # Upload files to Pennsieve server
    merged_data.apply(upload_to_psv, axis=1)

    # Rename files on Pennsieve server
    merged_data['rename_status'] = merged_data.apply(rename_file, axis=1)

    # Keep only the rows whose `rename_status` is True:
    merged_data = merged_data[merged_data['rename_status'] == True]

    # Save renamed files in MySQL database
    num_renamed = merged_data.shape[0]
    if num_renamed:
        my_log("Recording old and new filenames in HPAP 'file_rename_log' table ...")
        current_time = time.time()
        time_str = datetime.datetime.fromtimestamp(current_time).strftime(
            '%Y-%m-%d %H:%M:%S'
        )

        if (merged_data['img_id'] == 'NA').all():
            filename_col = 'raw_info'
        else:
            filename_col = 'img_id'

        rename_df = merged_data[[filename_col, 'new_name']]
        rename_df.loc[:, 'date_changed'] = time_str
        rename_df.columns = ["original_filename", "new_filename", "date_changed"]

    my_log(f"{num_img} file(s) uploaded, {num_renamed} file(s) renamed")
    my_log("Done!")
