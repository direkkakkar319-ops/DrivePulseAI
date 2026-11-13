# IVST large-scale real-world NEV battery dataset (v1 metadata record)

- Official record: [State Key Laboratory of Intelligent Vehicle Safety Technology](https://ivstskl.changan.com.cn/?p=2697).
- Associated paper: Liu et al., [Multi-modal framework for battery state of health evaluation using open-source electric vehicle data](https://doi.org/10.1038/s41467-025-56485-7), *Nature Communications* (2025).
- Publisher description: 300 discontinued fleet EVs; 0–500,000 km; 0.5–4 years; roughly 850 million records sampled every 10 seconds. The full archive is listed as 72 GB compressed / 581 GB uncompressed; a 100 MB sample is offered.
- Publicly listed fields: terminal time, SOC, speed, odometer, charge status, pack voltage/current, min/max cell voltage, min/max temperature, cell-voltage list and temperature-probe list.
- Publisher lists CC BY-NC-SA 4.0 and requires agreeing to separate research-only terms. The terms prohibit commercial use and external services and restrict redistribution without authorization. The download form requests name, phone, email, institution and use purpose.
- Access status: sample acquisition is pending the applicant details and the user's confirmation of the publisher terms. No sample or full archive is present in this repository. Do not commit downloaded data; the publisher's terms restrict redistribution. If access is granted, store the source archive locally under the ignored `raw/` directory and record its checksum and audit report here.

## Model-target assessment from public evidence

The associated paper describes SOH labels derived from operating telemetry using filtering, SOC correction and ampere-hour integration. It focuses on SOH estimation, not observed failure events. The publisher says the dataset may be used for RUL prediction and fault diagnosis, but its public field list does not specify an end-of-life target, failure event timestamp, censoring indicator or prediction horizon. Those targets are **not verified** by the public description; the sample must be inspected before deciding whether any target can be constructed without inventing labels.

The public descriptions call the vehicles fleet EVs but do not establish passenger-car body class or explain the stable per-vehicle ID available in the files. Those points also require sample inspection. The dataset is therefore a promising **SOH** candidate, not yet approved training data for RUL or failure prediction.

See [`ml/reports/data_validation/step2_ivst_300_ev.json`](../../../../ml/reports/data_validation/step2_ivst_300_ev.json) for the metadata audit and outstanding checks.
