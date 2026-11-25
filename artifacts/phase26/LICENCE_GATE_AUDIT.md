# Recommendation data licence audit

```mermaid
flowchart LR
    R["Recommend, compare, what-if"] --> D["Resolve registered version and scope"]
    D --> L["Check licence and deployment"]
    L --> C["Load permitted player pool"]
    C --> E["V3.2 engine"]
```

Default and explicit resolution converge at resolve_serving_reference. An override must equal the registered compatible snapshot. Cached reference objects still pass the licence gate per request. Unknown registry entries fail closed. Production-like settings take precedence over constructor-supplied local mode. An operator change to trusted deployment settings changes the policy mode for that deployment.

FC26 is UNVERIFIED and runs only under local or research policy. FC27 requires research opt-in and remains limited to local or research policy. The unit matrix traversed both environments and the production policy with and without opt-in and explicit overrides. It also tested invalid scope, mismatched references and removal of a warm-cache licence entry. End-to-end production response assertions require the FastAPI stack.
