## hpapdata-utils

This repository includes some utilities to handle `hpapdata`.
* `rename_histology.py`: based on [this script][1] (in `hpap-apps` repository)
* `rename_imc.py`: based on [this script][2] (in `pennsieve-utils` repository)


### 1. Requirements:

1. Python 3.7+

2. `requirements.txt`

### 2. Setup

Run the following commands before using any Python scripts in this repository:

```shell
# Create a Python virtual environment
python3 -m venv venv-hpapdata-utils

# Activate the virtual environment
source venv-hpapdata-utils/bin/activate

# Install required packages
cd <path>/hpapdata-utils
pip install -r requirements.txt
```

### 3. Related Resources

* See HPAP documentations at:
  https://github.com/faryabiLab/hpap-hub#1-hpap-documentation

* HPAP back-end and front-end source code is hosted at:
  https://github.com/faryabiLab/hpap

* To add new HPAP issues, go to: https://github.com/faryabiLab/hpap-hub/issues



[1]: https://github.com/faryabiLab/hpap-apps/blob/master/data_curator_tools/psv_pipelines/psv_histology_upload.py
[2]: https://github.com/faryabiLab/pennsieve-utils/blob/master/rename_imc.py
