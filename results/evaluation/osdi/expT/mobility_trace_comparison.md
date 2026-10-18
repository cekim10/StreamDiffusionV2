# Experiment T - measured mobility trace comparison (2026-10-17, for review; no dataset substituted)

Primary sources read on 2026-10-17; nothing downloaded for the alternatives. Selection criteria are data properties
only (provenance, license, resolution, handover semantics, diversity), not expected OTTER performance. "Documented" =
stated by the dataset's own page / paper / repository; "requires inspection" = only the data can settle it.

| | **Lumos5G 1.0** (frozen) | **UCC 4G LTE dataset** (Raca et al., MMSys'18) | **Berlin V2X** (VTC 2023-Spring) | SIGCOMM'22 5G mobility artifact |
|---|---|---|---|---|
| provenance | UMN; IEEE DataPort node/3598; project page networking.umn.edu/lumos5g | UCC MISL; Zenodo record 1219679; UCC page ucc.ie/en/misl/research/datasets/ivid_4g_lte_dataset | Fraunhofer HHI, Ericsson, TU Dresden, TU Kaiserslautern, BMW; IEEE DataPort open-access/berlin-v2x (DOI 10.21227/8cj7-q373); GitHub fraunhoferhhi/BerlinV2X | Hassan et al., "Vivisecting Mobility Management in 5G Cellular Networks", SIGCOMM'22; GitHub SIGCOMM22-5GMobility/artifact |
| license | CC BY 4.0 (LICENSE file in the archive, DataPort) | Zenodo: CC BY 4.0; the UCC page asks for citation of the paper and states no license | GitHub repository: CC0-1.0 (repository license; whether it covers the data files on DataPort is **unverified**; the DataPort license field is empty) | none stated (no LICENSE file seen) |
| access | public Google Drive link (verified, no authentication) or DataPort login | Zenodo (LTE_Dataset.zip, 2.3 MB) and UCC direct link | DataPort, free IEEE login (cellular_dataframe.parquet 24.44 MB) | GitHub `data/` folder |
| resolution | 1 s (`seq_num`) | 1 s (G-NetTrack Pro; an auxiliary set with another sampling interval exists) | merged and resampled to 1 s; RRC information is event-based in the raw logs | not documented |
| cell identity field | `tower_id`, "anonymized tower identifier" | `CellId`: "Serving cell for mobile device"; also `NetworkMode` (2G/3G/4G) and the serving eNodeB's GPS position (`Cell_Longitude`, `Cell_Latitude`, from OpenCellid) and `Distance` | `PCell_Cell_ID` (range 2-503, i.e. a physical cell ID range) and `PCell_Cell_Identity` from MobileInsight `LTE_RRC_Serv_Cell_Info`; SCell (carrier-aggregation) fields separately | folders per paper figure (e.g. `figure8-ho_prep_duration`, `figure13-same_diff_pci`); per-second traces not documented |
| handover semantics | **connectivity transitions**: verified in the data, `tower_id` never changes while the UE stays 5G-connected (0 of 1,298 changes); changes occur when leaving 5G (842) or while on LTE (454) | serving-cell change reported by Android (documented field; whether every change is a handover vs a reselection in idle and how 3G/4G mode changes appear **requires inspection**); the paper lists handover events among the collected information | **serving-cell (PCell) changes from RRC**, the closest to actual handovers among the candidates (documented source; per-change verification requires inspection); SCell changes are carrier-aggregation events, not handovers | handover events are the paper's subject, but the released per-figure data are processed results; suitability as continuous traces **requires inspection** |
| trajectory diversity | one 1,300 m loop (Minneapolis), walking and driving, 118 runs (verified) | Cork city and suburbs, commuter routes; static, pedestrian, bus (or tram), car, train (Cork-Dublin, mixed 3G/4G); 135 traces of ~15 min; two operators | urban Berlin, up to 4 cars over 3 days, two operators, several scenarios | cross-country driving (6,200 km+), three U.S. carriers (paper) |
| site mapping aid | none (anonymized IDs) | serving eNodeB coordinates allow a physical site grouping (cells of one eNodeB) | cell identity (eNodeB part derivable from the 28-bit identity, **requires inspection**) | - |

## Assessment against the frozen migration mapping (no hypothesis change)

The frozen rules of section 3.1 are mechanical (a per-second identifier sequence; ranking by first appearance;
site = floor(rank / k); H-second dwell; <= 3 sites per 120 s window; persistent site-to-node mapping). They apply
unchanged to any trace with a per-second serving-cell identifier, but the frozen text names Lumos5G and `tower_id`:
using another dataset is a **substitution that needs an amendment** (field, trace unit and cluster definitions), not a
hypothesis change.

- **Berlin V2X** supports the mapping most directly: the identifier is the RRC serving cell (PCell), so a change is a
  serving-cell change rather than a connectivity transition; 1 s resolution; urban driving with several cars and two
  operators. Needed in an amendment: identifier = `PCell_Cell_Identity` (or `PCell_Cell_ID` per operator), the trace unit
  (per device and drive/scenario), rows without a PCell (no LTE service) treated like missing values (frozen fill rule),
  SCell changes ignored. Risks: the data license (CC0 on the repository; data license unverified); the user's DataPort
  login; driving only.
- **UCC 4G** supports it with one extra rule: the identifier = `CellId` while `NetworkMode` is 4G; seconds in 2G/3G are
  connectivity transitions and need an explicit rule (e.g. treated as missing and filled, or excluded windows). It adds
  pedestrian, bus and train mobility and a physical site grouping from eNodeB coordinates (an alternative to the
  rank-based k). License CC BY 4.0 (Zenodo).
- **SIGCOMM'22 artifact:** not suitable without inspection (processed per-figure data, no license).
- **Lumos5G** stays as the frozen candidate and is best described as a *measured connectivity-transition workload*:
  its migrations follow 5G coverage loss and LTE tower changes along one loop, not 5G handovers.

## Decision needed (nothing selected)

1. Keep Lumos5G as the primary mobility source (frozen) and report its semantics as a limitation; or
2. amend to add Berlin V2X (and/or UCC 4G) as an additional or replacement mobility source, with the field, unit and
   missing-value definitions above, before any segment is selected. Either way the hypotheses and thresholds stay as
   frozen.

Sources: https://ieee-dataport.org/node/3598 ; https://networking.umn.edu/lumos5g ; https://zenodo.org/records/1219679 ;
https://www.ucc.ie/en/misl/research/datasets/ivid_4g_lte_dataset/ ; https://cora.ucc.ie/handle/10468/6400 (MMSys'18 paper,
author version, section 3) ; https://ieee-dataport.org/open-access/berlin-v2x ; https://github.com/fraunhoferhhi/BerlinV2X ;
https://raw.githubusercontent.com/fraunhoferhhi/BerlinV2X/main/metadata/cellular_info.csv ;
https://github.com/SIGCOMM22-5GMobility/artifact ; https://www-users.cse.umn.edu/~fengqian/paper/5g_mobility_sigcomm22.pdf
