# Sources, rights and acquisition notes

Purpose: distinguish publisher claims, downloaded evidence and unresolved documentation.

Primary source: [UbiLab datasets](https://ubilab.mpu.edu.mo/data.html), Macao Polytechnic University (MPU), UbiLab / MPU–UCLA Joint Research Center in Ubiquitous Computing. The saved `source_page.html` is the unmodified downloaded page.

Direct official files:

- https://ubilab.mpu.edu.mo/Dataset_Preprocessed.csv
- https://ubilab.mpu.edu.mo/Dataset_NissanLeaf-2021_2022.csv
- https://ubilab.mpu.edu.mo/Nissan_Leaf_Model2018_Data_Description.xlsx

The source describes a 2018 Nissan Leaf, nominal 250 ms logging, 4.5 million samples and coverage from November 2020 to December 2021. These are publisher claims about the collection, not assumed dimensions of the downloadable files. EDA measures the actual files separately. No semantic release version is provided. HTTP Last-Modified and SHA-256 identify the downloaded snapshot.

No explicit dataset license or commercial redistribution permission was found on the source page or in the workbook. The page requests research citations. Do not interpret public download access or the hosting site's footer as an open-data license. Confirm reuse rights with the researchers before redistributing source data.

The page lists these supporting publications:

1. Aguiari, Chou, Tse, Pau. *Monitoring Electric Vehicles on The Go*. CCNC 2022, pp. 885–888. DOI: https://doi.org/10.1109/CCNC49033.2022.9700713. Institutional record: https://cris.unibo.it/handle/11585/875565.
2. Chou, Aguiari, Tse, Tang, Pau. *Impact Evaluation of Driving Style on Electric Vehicle Battery based on Field Testing Result*. CCNC 2023, pp. 1143–1146. DOI: https://doi.org/10.1109/CCNC51644.2023.10060822. Institutional record: https://research.mpu.edu.mo/en/publications/impact-evaluation-of-driving-style-on-electric-vehicle-battery-ba/.
3. *Forecasting the Temperature of BEV Battery Pack Based on Field Testing Data*. 2023. DOI: https://doi.org/10.1007/978-3-031-28990-3_1.

The monitoring paper's institutional record describes an earlier 1.7-million-record collection and a logger with differentiated polling schedules. Its dimensions must not be substituted for this download. Its PDF download returned HTTP 403 at both institutional direct URLs attempted; no PDF is claimed to have been saved. See `access_log.json`. The landing page provides a browser opening link, but a successful direct PDF transfer could not be verified here.

The downloaded workbook is the available detailed parameter documentation. `parameter_dictionary_extracted.csv` is a reproducible extraction, not a modification of the workbook. Some column aliases are inferred and marked. In particular, ambient temperature has a Celsius/Fahrenheit documentation conflict; brake and accelerator units are explicitly uncertain. The workbook is not a mandatory CSV schema. It does not fully document Driver_ID, Trip, export indices, accumulated fields or calendar encodings.

There is no downloaded release-specific preprocessing program or full transformation log. Comparing matching indices and timestamps can reveal changed or excluded observations; it cannot establish which exact algorithm produced each change.

Source CSVs are uncompressed. The XLSX is internally ZIP-compressed; expanded XML/member bytes are recorded in the download manifest. Raw telemetry was resumed with HTTP range requests checked against Content-Range and the original ETag; `raw_range_transfer.json` records byte ranges. The assembled file retains source byte order.
