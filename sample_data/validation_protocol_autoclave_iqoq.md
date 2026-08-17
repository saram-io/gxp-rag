# VAL-PRT-019: Installation and Operational Qualification (IQ/OQ) Protocol for Autoclave AC-101

## Document Control & Metadata
- **Document ID**: VAL-PRT-019
- **Type**: Validation Protocol (IQ/OQ)
- **Department**: Validation & Engineering
- **Target Equipment**: Fedegari Steam Sterilizer AC-101 (Serial # F-88192)
- **Version**: 1.0

---

### 1.0 Objective & Scope
To provide documented verification that the Fedegari AC-101 Autoclave has been installed according to manufacturer specifications, utility requirements, GAMP 5 computerized system guidelines, and operates predictably within validated temperature and pressure boundaries (121.1°C to 124.0°C, 2.05 to 2.25 bar steam pressure).

### 2.0 Regulatory & Standards References
- FDA 21 CFR Part 211.68 (Automatic, Mechanical, and Electronic Equipment)
- ISPE GAMP 5 2nd Edition (Risk-Based Approach to Compliant GxP Computerized Systems)
- EN 285 (Sterilization - Steam Sterilizers - Large Sterilizers)
- ISO 17665-1 (Sterilization of health care products - Moist heat)

### 3.0 Installation Qualification (IQ) Requirements & Tests
| Test ID | Description | Acceptance Criteria | Verified By |
|---|---|---|---|
| IQ-01 | Equipment Utilities Verification | Clean Steam supply 2.8 - 3.5 bar, WFI cooling water 2-8°C, Compressed Air 6.0 bar. | Engineering |
| IQ-02 | Materials of Construction (MOC) | Chamber and piping 316L Stainless Steel with Mill Certificates and Ra ≤ 0.5 µm. | Validation Eng |
| IQ-03 | Calibration of Critical Instruments | Temperature RTDs (Class A PT100) and pressure transmitters calibrated with NIST-traceable standards. | Metrology |
| IQ-04 | 21 CFR Part 11 Software Audit Trail | Siemens S7 / SCADA system configured with individual user roles, password complexity, and immutable event logging. | CSV Specialist |

### 4.0 Operational Qualification (OQ) Tests & Execution Steps

#### 4.1 Empty Chamber Thermal Distribution (OQ-01)
**4.1.1 Thermocouple Array Placement** (Validation Engineer)
> Place 16 calibrated Kaye Validator thermal sensors throughout the chamber geometric envelope, including geometric center, drain line, and door gaskets.
> - *Critical Parameters*: Sensor calibration drift < 0.25°C pre/post run.
> - *Acceptance Criteria*: All 16 sensors reach and maintain 121.1°C - 123.5°C during the 30-minute exposure phase; Temperature spread among all sensors ≤ 1.0°C.

#### 4.2 Vacuum Leak Rate Test (Bowie-Dick) (OQ-02)
**4.2.1 Vacuum Integrity and Steam Penetration** (Validation Operator)
> Run automated vacuum leak rate cycle. Chamber is evacuated to 100 mbar absolute, isolated, and held for 10 minutes.
> - *Critical Parameters*: Chamber vacuum 100 mbar.
> - *Acceptance Criteria*: Leak rate ≤ 1.3 mbar/min (per EN 285). Bowie-Dick indicator sheet exhibits uniform dark brown/black color change without air retention zones.

#### 4.3 Biological Indicator (BI) Lethality Verification (OQ-03)
**4.3.1 Spore Inactivation Test** (Microbiology Specialist)
> Co-locate *Geobacillus stearothermophilus* biological indicators (population ≥ 1.0 x 10^6 spores, D121 ≥ 1.5 min) adjacent to thermocouple sensors in hard-to-penetrate load sites.
> - *Critical Parameters*: Calculated lethality Fo ≥ 15.0 minutes.
> - *Acceptance Criteria*: 100% kill after 7-day incubation at 55°C-60°C (0 positive growth vials).

### 5.0 Signatures & Approvals
- Protocol Author: Validation Engineer
- Technical Reviewer: Lead Microbiologist
- Regulatory Approval: Head of Quality Assurance
