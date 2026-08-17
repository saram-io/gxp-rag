# DEV-2024-089: Investigation of Temperature Excursion in Walk-In Cold Room CR-03

## Document Control & Metadata
- **Document ID**: DEV-2024-089
- **Type**: Deviation / Non-conformance Report (Major)
- **Department**: Quality Assurance & Facilities
- **Date of Occurrence**: 2024-06-12 03:14 UTC
- **Status**: Closed / Approved

---

### 1.0 Event Description
On June 12, 2024 at 03:14 UTC, the Building Monitoring System (BMS) recorded an alarm condition in Walk-In Cold Room CR-03. The internal air temperature rose from the controlled storage setpoint of 2.0°C - 8.0°C to a peak of 12.4°C for an elapsed duration of 2 hours and 42 minutes before secondary backup refrigeration compressor Unit B kicked in.

### 2.0 Immediate Actions Taken
1. Facilities technician dispatched immediately to inspect compressor valves and refrigerant lines.
2. QA quarantined all stored clinical drug substance lots (Lots DS-4091, DS-4092, and DS-4093) with physical quarantine placards and electronic status locks in the Enterprise ERP.
3. Placed secondary calibrated TempTale data loggers directly onto product pallet surfaces.

### 3.0 Root Cause Analysis (Fishbone & 5-Whys)
- **Primary Root Cause**: Mechanical failure of the primary compressor solenoid expansion valve due to seal desiccation and unlubricated actuator needle.
- **Contributing Cause**: Preventive maintenance cycle was extended by 45 days during the facility expansion project without formal Change Control approval.
- **Fail-safe Defect**: Auto-switchover relay to Backup Compressor Unit B had a faulty delay timer module set to 150 minutes instead of 15 minutes.

### 4.0 Product Quality & Stability Impact Assessment
- Stability data for Drug Substance Product X confirms stability at room temperature (20°C-25°C) for up to 48 hours without degradation, high-molecular-weight species (HMWS) formation, or potency loss.
- High-resolution SEC-HPLC testing of quarantined Lots DS-4091, DS-4092, and DS-4093 yielded monomer purity > 99.1% (specification: ≥ 98.0%) and potency 101.4% (specification: 95.0% - 105.0%).
- Conclusion: No adverse impact on safety, efficacy, or stability of the stored clinical product.

### 5.0 Corrective and Preventive Actions (CAPA)
1. **CAPA-2024-045**: Replaced faulty solenoid expansion valve and updated BMS automatic compressor switchover timer relay to 10 minutes maximum threshold.
2. **CAPA-2024-046**: Revised Preventive Maintenance SOP-FAC-019 to mandate monthly seal inspection and prohibit PM schedule extensions without formal QA Change Control approval.
3. Conducted 72-hour thermal mapping under full-load conditions to requalify Cold Room CR-03.
