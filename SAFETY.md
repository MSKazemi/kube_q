# Safety, limitations and pre-deployment checks — kube_q

**Scope:** Command-line and optional browser interfaces to AI-assisted Kubernetes operations and third-party AI backends.  
**Issued:** 2026-10-17  
**Status:** Risk guidance, **not** a safety certification, compliance approval, or verified representation that technical controls have been implemented.

This document is meant to help users and maintainers identify foreseeable risks and the checks **they still need to perform**. It supplements [DISCLAIMER.md](DISCLAIMER.md) and the existing software license; it does not override either or remove non-waivable duties.

## Material risks to assess

- Wrong kubeconfig context or namespace can affect unintended production workloads.
- Local SQLite transcripts, files attached to conversations, profiles and logs can contain secrets or personal data.
- Local Python plugins may execute privileged code; web-terminal access or backend tokens may be mishandled.

## Required assessment before consequential deployment

- [ ] Verify context/namespace selection before changing resources and require a separately enforced approval decision for mutating actions.
- [ ] Test default permissions and storage of credentials, transcripts, exports and plugin source; apply restrictive filesystem permissions.
- [ ] Require authenticated, TLS-protected remote connections; never expose an unauthenticated web terminal to an untrusted network.
- [ ] Use test clusters to validate denied actions, connection failures, partial execution and response replay.

## Operational conditions

- Start with an isolated, disposable environment and the least privileges possible.
- Do not infer that a feature claim in project documentation proves that the safeguard is effectively enforced in every execution path. Perform threat modeling and independent testing.
- Independently validate material outcomes. Preserve audit evidence, tested version, configuration, dependencies, approver identity and incident response arrangements where appropriate.
- Before exposing a networked service, inspect authentication, authorization, logging, data handling, supply chain and applicable laws.
- Pause deployment when unresolved critical flaws, missing permissions, unexplained automation, or inaccurate claims are discovered. Route security reports privately rather than disclosing exploitable details in public issues.

**Important:** Project maintainers and users remain subject to applicable mandatory safety, privacy, security and product laws. A disclaimer does not substitute for these checks or guarantee immunity from claims.
