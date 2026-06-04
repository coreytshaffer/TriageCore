# TriageCore — Resource Estimation Methodology

## Overview

TriageCore records the estimated resource consumption of every agentic coding
task it orchestrates. Because direct hardware measurement (e.g., RAPL, NVML,
smart-plug readings) is not universally available across desktop environments,
TriageCore uses a **heuristic estimation model** grounded in the literature on
computational energy accounting. All parameters are configurable in
`triagecore.toml`; defaults are documented below alongside the formulae.

Every estimate is stored in the append-only task ledger together with the
`estimation_method` and `measurement_boundary` fields so that readers of any
derived data can assess the scope and assumptions of each figure.

---

## 1. Operational Energy

### Operational Energy Formula

$$E = \frac{P \cdot t}{3{,}600{,}000}$$

| Symbol | Quantity | Default |
| :--- | :--- | :--- |
| $E$ | Energy consumption (kWh) | — |
| $P$ | Device power draw during inference (W) | **300 W** |
| $t$ | Task wall-clock duration (s) | measured |

**Rationale for default power assumption.**  
A value of 300 W is a conservative mid-range estimate for a consumer desktop
GPU (e.g., NVIDIA RTX 3070–4090 class) running local inference at moderate
load. Users with known hardware specifications should override this value in
`triagecore.toml` using a device profile. The 3,600,000 divisor converts
watt-seconds to kilowatt-hours (1 kWh = 3.6 × 10⁶ J).

**Implementation reference:** `SustainabilityEstimator.estimate()` in
[`triage_core/sustainability.py`](../triage_core/sustainability.py), line 25.

---

## 2. Operational Carbon Emissions

### Operational Carbon Emissions Formula

$$C_{\text{op}} = E \times I_{\text{grid}}$$

| Symbol | Quantity | Default |
| :--- | :--- | :--- |
| $C_{\text{op}}$ | Operational carbon emissions (gCO₂e) | — |
| $E$ | Energy (kWh), from §1 | — |
| $I_{\text{grid}}$ | Grid carbon intensity (gCO₂e / kWh) | **400 gCO₂e / kWh** |

**Rationale for default grid intensity.**  
The global average grid carbon intensity is approximately 475 gCO₂e / kWh
(IEA, 2023). A default of 400 gCO₂e / kWh is used to represent a modestly
cleaner mixed grid (e.g., US average ≈ 386 gCO₂e / kWh, EU average
≈ 255 gCO₂e / kWh). Users in high-renewable regions should supply a
location-specific value. Time-of-day variation is not currently modelled;
this is noted as a limitation.

**Implementation reference:** line 26.

---

## 3. Indirect Water Footprint

### Indirect Water Footprint Formula

$$W = E \times f_{\text{water}}$$

| Symbol | Quantity | Default |
| :--- | :--- | :--- |
| $W$ | Indirect water consumption (litres) | — |
| $E$ | Energy (kWh), from §1 | — |
| $f_{\text{water}}$ | Water intensity of electricity generation (L / kWh) | **1.5 L / kWh** |

**Rationale.**  
Electricity generation consumes water through steam-cycle cooling, evaporation
at hydroelectric reservoirs, and fuel processing. The default factor of
1.5 L / kWh is derived from global average estimates for a mixed
thermoelectric–renewable grid (Meldrum et al., 2013; Grubert & Sanders, 2018).
Regional water intensity can vary by more than an order of magnitude; this
estimate is conservatively low for grids with significant thermoelectric
generation. Direct on-premise cooling water consumption is not included in this
boundary.

**Measurement boundary:** indirect electricity-related water only.

**Implementation reference:** line 27.

---

## 4. Embodied Carbon Allocation

### Embodied Carbon Allocation Formula

$$C_{\text{emb}} = C_{\text{device}} \times \frac{t / 3600}{H_{\text{lifetime}}}$$

| Symbol | Quantity | Default |
| :--- | :--- | :--- |
| $C_{\text{emb}}$ | Embodied carbon allocated to this task (gCO₂e) | — |
| $C_{\text{device}}$ | Total embodied carbon of the host device (gCO₂e) | **300,000 gCO₂e** |
| $t$ | Task duration (s) | measured |
| $H_{\text{lifetime}}$ | Expected device operational lifetime (hours) | **20,000 h** |

**Rationale.**  
Hardware manufacture accounts for a substantial share of a computing device's
lifetime carbon footprint (Gupta et al., 2022). The default of 300,000 gCO₂e
(300 kg CO₂e) is a representative figure for a mid-range desktop workstation
including GPU (Malmodin & Lundén, 2018; Boavizta consortium estimates). The
lifetime of 20,000 hours corresponds to approximately 10 years of average daily
use (~5.5 hours/day).

Allocation follows the proportional-use method: the fraction of device lifetime
consumed by a task determines the fraction of embodied carbon attributed to it.
This method is analogous to the allocation approach used in lifecycle assessment
(ISO 14044) and in cloud carbon accounting literature (Lannelongue et al., 2021).

**Measurement boundary:** embodied carbon of host device only; manufacturing
carbon of model weights, training infrastructure, or storage media is not
included in this boundary.

**Implementation reference:** lines 29–30.

---

## 5. Per-Accepted-Task Resource Intensity

### Per-Accepted-Task Resource Intensity Formula

$$R_{\text{accepted}} = \frac{\sum R_i}{N_{\text{accepted}}}$$

| Symbol | Quantity |
| :--- | :--- |
| $R_{\text{accepted}}$ | Mean resource consumption per accepted task |
| $\sum R_i$ | Total resource consumption across all tasks of type $R$ |
| $N_{\text{accepted}}$ | Count of tasks whose outcome is `accepted = true` |

This metric is the primary scientific outcome variable of TriageCore experiments.
It deliberately penalises configurations that produce low per-task costs but
high rejection or retry rates, because rejected work still consumed real
resources without producing accepted software artefacts.

**Reported dimensions:**

- kWh per accepted task
- gCO₂e per accepted task
- litres of water per accepted task
- gCO₂e embodied carbon per accepted task
- tokens (input + output) per accepted task
- human review minutes per accepted task
- optional subjective review workload (`not_recorded`, `low`, `medium`, or `high`)

Human review minutes measure elapsed review time. The optional
`review_workload` label records the reviewer's perceived assessment burden and
should be analysed as a subjective ordinal indicator, not as an objective
performance metric.

### Local-First Benefit Signals

The desktop telemetry dashboard intentionally foregrounds local-first benefit
signals because the workbench is also an operator environment. These signals can
help the user keep collecting evidence, building artifacts, and noticing when
more work is staying on local compute. Current dashboard signals include:

- accepted yield
- percent of tasks routed through local-first runners
- count of accepted local-first tasks
- percent of tasks that did not require mandatory human review

These are motivational and operational indicators, not standalone proof of
environmental savings. Reports, papers, and methodology artifacts should describe
them as benefit or avoidance signals unless a study defines a baseline
comparison, such as local-first routing versus a remote-only workflow using the
same benchmark fixture set.

---

## 6. Model And Backend Comparison

Model/backend comparison studies use the same benchmark fixture set across
each candidate configuration and tag all evidence with a shared `study_id` plus
a unique `run_id` for each backend/model pair. Reports group evidence by
supervision lane, backend, and backend/model so that supervised workflows,
runtime-adapter differences, and model differences are not confused with one
another.

Comparison runs should use:

- identical benchmark fixtures
- identical timeout settings unless timeout is the experimental variable
- explicit backend type, base URL when applicable, and model identifier
- separate `run_id` values for every backend/model pair
- the combined `benchmark-report --study-id <study>` output for interpretation
- the `By Supervision` section when local-only and supervised outcomes are mixed

Expected destructive-task handoff is treated as correct safety behavior. A
configuration should only be preferred when it improves accepted outcomes
without increasing unexpected handoffs, validator failures, or subjective review
burden.

---

## 7. Supervised Hybrid Workflows

TriageCore distinguishes local-only execution from supervised hybrid workflows.
A local draft, worker-council result, benchmark run, or pipeline attempt may be
reviewed by Codex, Antigravity, Gemini, or a human reviewer before it is treated
as accepted work. These reviews are recorded as `supervisor_reviewed` events
rather than merged into the original local execution event.

This separation matters because supervision changes the workflow being studied.
A Codex-reviewed patch and an Antigravity-supervised IDE implementation may use
the same local model output, but they also add different review tools, reasoning
contexts, token costs, and human oversight patterns. Reports should therefore
label supervised outcomes separately from local-only outcomes whenever they are
used as scientific evidence.

Supervisor review fields include the supervising tool, model, profile, decision,
notes, linked artifact path, and estimated supervisor input/output tokens when
exact usage is not available. Estimated token fields should be interpreted as
approximate evidence only.

Benchmark reports summarize supervisor reviews under the same `study_id` and
`run_id` filters as the benchmark evidence. The `Supervisor Reviews` table
reports review counts, decision counts, and estimated supervisor token totals by
tool. Supervisor token values remain manual estimates unless a supervisor tool
log or API exposes exact usage data.

This boundary is intentionally conservative: imported exact usage, imported
estimates, and manual estimates are labelled separately so claims remain
verifiable, reproducible, and falsifiable.

---

## 8. Default Parameter Summary

| Parameter | Symbol | Default | Unit | Override key in `triagecore.toml` |
| :--- | :--- | :--- | :--- | :--- |
| Device power draw | $P$ | 300 | W | `sustainability.default_watts` |
| Grid carbon intensity | $I_{\text{grid}}$ | 400 | gCO₂e / kWh | `sustainability.grid_intensity_gco2e_per_kwh` |
| Water intensity | $f_{\text{water}}$ | 1.5 | L / kWh | `sustainability.water_intensity_l_per_kwh` |
| Device embodied carbon | $C_{\text{device}}$ | 300,000 | gCO₂e | `sustainability.device_embodied_gco2e` |
| Device lifetime | $H_{\text{lifetime}}$ | 20,000 | hours | `sustainability.device_lifetime_hours` |

---

## 9. Estimation Caveats and Limitations

1. **Power draw is assumed, not measured.** Direct measurement via RAPL
   (Intel/AMD), NVML (NVIDIA), or a smart plug would substantially improve
   accuracy. The current model assumes constant load at the configured wattage
   for the full task duration; idle periods within a task are not accounted for.

2. **Grid intensity is static.** Carbon intensity varies by time of day and
   season. Tools such as ElectricityMaps or the WattTime API could provide
   real-time intensity values as a future enhancement.

3. **Water estimates are regional-average proxies.** The factor of 1.5 L / kWh
   may underestimate intensity for coal-heavy grids or overestimate for
   predominantly hydro/wind grids.

4. **Embodied carbon defaults are order-of-magnitude estimates.** Actual figures
   depend on hardware manufacturer, manufacturing region, and device class.
   Boavizta device profiles or manufacturer-published product carbon footprint
   disclosures should be used where available.

5. **Training carbon is out of scope.** The embodied carbon of the model weights
   themselves (i.e., the compute used to train the LLM) is not attributed to
   inference tasks in this version. This is a known boundary choice, consistent
   with operational-boundary carbon accounting, and should be stated explicitly
   in any published results.

6. **All estimates are labelled as estimates.** Every ledger record includes
   `"estimation_method": "heuristic_profile_v1"` and
   `"measurement_boundary": "local operational estimate plus optional embodied amortisation"`
   to signal this scope to downstream consumers of the data.

---

## 10. Execution Hardware Specification

For the comparison study of local model execution and specialist councils (Study 002), the benchmarking environment was standardized on a host workstation with the following hardware specifications:

- **Host System**: Alienware m18 R1 AMD Laptop
- **Processor (CPU)**: AMD Ryzen 9 7845HX with Radeon Graphics (12 physical cores, 24 threads, AVX/AVX2 support)
- **System Memory (RAM)**: 32 GB DDR5 RAM (33,487,876,096 bytes)
- **Dedicated Graphics (GPU)**: NVIDIA GeForce RTX 4070 Laptop GPU (Discrete, Compute Capability 8.9, 8 GB VRAM / 8,585,216,000 bytes)
- **Operating System**: Windows 11 Pro 64-bit (Build 26200)

This system configuration is representative of developer-class workstations where local model offloading is actively deployed to protect the cloud compute budget.

---

## 11. References

Grubert, E., & Sanders, K. T. (2018). Water use in the United States energy
system: A national assessment and unit process inventory of water consumption
and withdrawals. *Environmental Science & Technology, 52*(11), 6695–6703.
<https://doi.org/10.1021/acs.est.8b00139>

Gupta, U., Kim, Y. G., Lee, S., Tse, J., Lee, H. H. S., Wei, G.-Y.,
Brooks, D., & Wu, C.-J. (2022). Chasing carbon: The elusive environmental
footprint of computing. *IEEE Micro, 42*(4), 37–47.
<https://doi.org/10.1109/MM.2022.3163226>

International Energy Agency. (2023). *Electricity 2024: Analysis and forecast
to 2026*. IEA. <https://www.iea.org/reports/electricity-2024>

Lannelongue, L., Grealey, J., & Inouye, M. (2021). Green algorithms: Quantifying
the carbon footprint of computation. *Advanced Science, 8*(12), 2100707.
<https://doi.org/10.1002/advs.202100707>

Malmodin, J., & Lundén, D. (2018). The energy and carbon footprint of the global
ICT and E&M sectors 2010–2015. *Sustainability, 10*(9), 3027.
<https://doi.org/10.3390/su10093027>

Meldrum, J., Nettles-Anderson, S., Heath, G., & Macknick, J. (2013). Life cycle
water use for electricity generation: A review and harmonization of literature
estimates. *Environmental Research Letters, 8*(1), 015031.
<https://doi.org/10.1088/1748-9326/8/1/015031>
