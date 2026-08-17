# SOP-QC-028: High-Performance Liquid Chromatography (HPLC) Operation & System Suitability

## Document Control & Metadata
- **Document ID**: SOP-QC-028
- **Version**: 4.0
- **Department**: Quality Control Analytical Laboratory
- **Effective Date**: 2024-02-01
- **Review Cycle**: 24 Months

---

### 1.0 Purpose
To provide standardized instructions for startup, mobile phase degassing, autosampler operation, chromatographic sequence execution, and system suitability acceptance criteria for Agilent 1260/1290 HPLC and UHPLC systems per USP <621> and FDA 21 CFR Part 211.165.

### 2.0 Scope
Applies to all potency, purity, and dissolution analytical release and stability testing performed in the QC Analytical Testing Laboratory.

### 3.0 Regulatory Standards
- FDA 21 CFR Part 211.165 (Testing and Release for Distribution)
- FDA 21 CFR Part 11 (Electronic Records, Audit Trails, and Empower CDS Integration)
- USP <621> (Chromatography)

### 4.0 System Suitability Acceptance Criteria
| Parameter | Acceptance Limit | Regulatory Basis |
|---|---|---|
| Retention Time (%RSD) | ≤ 1.0% (n = 6 replicate injections) | USP <621> |
| Peak Area Precision (%RSD) | ≤ 1.5% for active pharmaceutical ingredient (API) | USP <621> |
| Tailing Factor (T) | 0.8 ≤ T ≤ 1.8 | USP <621> |
| Theoretical Plates (N) | N ≥ 2500 per column specification | Product Test Specification |
| Baseline Drift | < 0.5 mAU/hour during 30-min equilibration | Manufacturer Specification |

### 5.0 Procedure

#### 5.1 Mobile Phase Preparation & Column Equilibration
**5.1.1 Mobile Phase Preparation and Vacuum Filtration** (QC Analyst)
> Prepare mobile phase solvents using HPLC-grade acetonitrile and 18.2 MΩ-cm Milli-Q purified water. Filter all aqueous buffers through 0.22 µm nylon membrane filters and sonicate under vacuum for 15 minutes to degas.
> - *Critical Parameters*: pH buffer tolerance ± 0.05 pH units; Sonication duration: 15 to 20 minutes.
> - *Acceptance Criteria*: Clear, particulate-free solution without microbubbles.

**5.1.2 Purge and Column Temperature Stabilization** (QC Analyst)
> Prime all solvent channels at 5.0 mL/min with purge valve open for 5 minutes. Set column oven temperature to target method temperature (e.g., 35.0°C ± 0.5°C) and purge column at method flow rate for minimum 20 column volumes.
> - *Critical Parameters*: Flow rate stability: ± 0.01 mL/min; Column Temp: 35.0°C ± 0.5°C; Pressure fluctuation: < 2.0 bar.
> - *Acceptance Criteria*: Stable flat baseline with drift < 0.5 mAU over 15 minutes.

#### 5.2 System Suitability Injection Sequence
**5.2.1 Sequence Setup in 21 CFR Part 11 Compliant CDS** (QC Analyst)
> In Waters Empower or OpenLab CDS, load approved method template. Inject: Blank (n=2), System Suitability Reference Standard (n=6), Bracketing Standards every 10 sample injections, and Independent Check Standard.
> - *Critical Parameters*: Auto-audit trail logging enabled; secure electronic signature lock.
> - *Acceptance Criteria*: All system suitability parameters pass prior to evaluating test samples.

### 6.0 Out-of-Specification (OOS) & Anomaly Protocol
If system suitability criteria fail, abort the analytical sequence. Do not inject test samples. Label data as "INVALID - SYSTEM SUITABILITY FAILURE", preserve chromatographic raw files, and notify QC Supervisor to trigger an OOS investigation per SOP-QC-005.
