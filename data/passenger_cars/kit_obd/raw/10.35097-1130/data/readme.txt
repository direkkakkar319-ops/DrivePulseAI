#
# Copyright 2022 FIZ Karlsruhe - Leibniz-Institut fuer Informationsinfrastruktur GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

Description for the payload directory "data"
--------------------------------------------

Overview:
- /dataset contains the directory and file structure of the originally uploaded dataset.
- /descriptive-md contains the descriptive metadata of the dataset and all sub-entities in XML format.
- /technical-md contains the technical metadata of the dataset and all sub-entities in XML format.


Conventions in /descriptive-md:
- dataset.desc_md.xml contains the descriptive metadata of the dataset.
- The directory tree in /descriptive-md/dataset is identical to the structure of /dataset.
- Within /descriptive-md/dataset, the metadata files have the same names as in /dataset, suffixed with ".desc_md.xml".


Conventions in /technical-md:
- dataset.tech_md.xml contains the technical metadata of the dataset.
- The directory tree in /technical-md/dataset is identical to the structure of /dataset.
- Within /technical-md/dataset, the metadata files have the same names as in /dataset, suffixed with ".tech_md.xml". 
