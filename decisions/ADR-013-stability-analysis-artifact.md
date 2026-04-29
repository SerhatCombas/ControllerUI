# ADR-013: StabilityAnalysisArtifact

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S5  
**Supersedes:** —  
**Superseded by:** —

## Context

Phase 2 stability and frequency-domain analysis produces multiple related results:

* state-space matrices `A`, `B`, `C`, `D`
* eigenvalues
* poles and zeros
* frequency response (magnitude, phase) for Bode plots
* root locus data
* gain and phase margins

These results are **derived** from the `ODEArtifact` via linearization (per ADR-010). They are not part of the model itself but of a control-design analysis.

The question: should these results live in `ODEArtifact`, in `SimulationResultArtifact`, or in a separate artifact?

## Decision

Stability and frequency-domain analysis results are stored in a dedicated **`StabilityAnalysisArtifact`** that is separate from both `ODEArtifact` and `SimulationResultArtifact`.

Schema:

```python
@dataclass(frozen=True)
class StabilityAnalysisArtifact:
    artifact_id: str                  # ULID with sa_ prefix
    ode_artifact_id: str              # source ODE
    operating_point: OperatingPoint   # how the linearization was performed
    A: np.ndarray
    B: np.ndarray
    C: np.ndarray
    D: np.ndarray
    eigenvalues: np.ndarray
    poles: np.ndarray
    zeros: dict[tuple[str, str], np.ndarray]  # per (input, output) pair
    frequency_response: dict[tuple[str, str], FrequencyResponse]
    margins: dict[tuple[str, str], StabilityMargins]
    nonlinear_warning: bool
    metadata: dict[str, Any]
    extensions: dict[str, Any]
```

The artifact is:

* **immutable** after creation (`frozen=True`)
* **referenced** by `PlotSlotConfig.analysis_ref` (per `03 §8.3` and ADR-016)
* **owned** by `ControllerDesignModule` (per ADR-006 and ADR-010)
* **rendered** by the unified Result Panel alongside `SimulationResultArtifact` (per ADR-015)

Multiple `StabilityAnalysisArtifact` instances can coexist, e.g., for different operating points of the same ODE.

## Alternatives Considered

### Alternative 1: Embed matrices in `ODEArtifact`

Add `A/B/C/D` to `ODEArtifact` for linear systems.

**Rejected because:**

* Conflicts with ADR-010 (linearization is a separate step)
* Forces nonlinear systems to silently linearize
* Couples modeling lifecycle to control-design lifecycle

### Alternative 2: Embed in `SimulationResultArtifact`

Add stability analysis to simulation results.

**Rejected because:**

* Stability analysis does not require simulation
* Simulation produces time-series; stability analysis produces structural data
* Different lifecycles, different consumers

### Alternative 3: Multiple smaller artifacts

Have `StateSpaceArtifact`, `BodeArtifact`, `PoleZeroArtifact` separately.

**Rejected because:**

* Fragmentation: each plot type would consume a different artifact
* Many artifacts share the same source data (the linearization), making consistency tricky
* Single artifact with all data is easier to cache and reference

## Consequences

### Positive

* Clean separation: ODE, simulation, stability are three independent artifacts
* Multiple operating points produce multiple stability artifacts
* Result Panel can mix simulation and stability plots in the same 4-slot grid
* Frozen dataclass enables safe sharing across threads

### Negative

* More artifact types to track
* Persistence schema is larger

### Risks

* Confusion about which artifact to use for which plot
* Mitigation: `08 §16.4` (Plot Binding Quick Lookup) maps each plot type to the correct artifact reference

## Related ADRs

- ADR-006 Controller Owns Transfer-Function and State-Space Builders
- ADR-010 Linearization Ownership
- ADR-015 Result Panel Unified With Grouped Dropdown
- ADR-016 channel_selection.kind Schema

## References

- `05_simulation_and_results_requirements.md` §16 (StabilityAnalysisArtifact)
- `06_data_flow_and_architecture.md` §4.3 (ControllerDesignModule)
- `07_implementation_order.md` §11 (Stage S5), §16.13 (S5 verification)
- `08_codex_execution_rules.md` §7.7 (StabilityAnalysisArtifact contract rules)
