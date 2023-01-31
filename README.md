# hpapdata-utils

This repository includes some utilities to handle `hpapdata`.
* `rename_histology.py`: based on [this script](https://github.com/faryabiLab/hpap-apps/blob/master/data_curator_tools/psv_pipelines/psv_histology_upload.py)
* `rename_imc.py`: based on [this script](https://github.com/faryabiLab/pennsieve-utils/blob/master/rename_imc.py)


### Requirements:

1. Python 3.7+

2. `requirements.txt`

### Setup

Run the following commands before running any Python scripts in this repository:

```shell
# Create a Python virtual environment
python3 -m venv venv-hpapdata-utils

# Activate the virtual environment
source venv-hpapdata-utils/bin/activate

# Install required packages
cd <path>/hpapdata-utils
pip install -r requirements.txt
```
