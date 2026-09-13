## Inline plus artifacts

### plan.json
```json
{
  "mode": "styrir_plus",
  "facets": [
    "Inspect AI MIT LICENSE and GitHub license metadata",
    "OpenLLMetry/Traceloop LICENSE versus platform boundary",
    "Langfuse current OSS self-host versus Cloud and Playground/LLM-as-judge",
    "Helicone official self-host deployment feature list",
    "Ragas agent_evals status versus README",
    "Google Patents titles for US 11,315,043 and US 11,615,345 only",
    "Contradiction sweep: Langfuse OSS versus Phoenix comparison"
  ],
  "reservedFollowups": 2,
  "budget": {
    "maxSearchQueries": 10,
    "maxFetches": 10,
    "maxFollowups": 3,
    "maxConcurrency": 3
  },
  "accounting": {
    "totalQueriesRun": 8,
    "totalSuccessfulExternalFetches": 10,
    "localReadsExcludedFromExternalFetchBudget": true,
    "searchSnippetsAreDiscoveryOnly": true,
    "note": "Ten external URLs were read. The combined Google Patents query was fetched but returned only the generic search shell, so direct patent record fetches remain a proof gap."
  },
  "searches": [
    {
      "facet": "Inspect AI license",
      "query": "site:github.com/UKGovernmentBEIS/inspect_ai license LICENSE Inspect AI MIT GitHub"
    },
    {
      "facet": "OpenLLMetry license and platform",
      "query": "site:github.com/traceloop/openllmetry LICENSE Traceloop open source platform official docs"
    },
    {
      "facet": "Langfuse OSS and self-host",
      "query": "site:langfuse.com/docs self-hosted Langfuse open source cloud playground LLM-as-a-judge pricing features"
    },
    {
      "facet": "Helicone self-host",
      "query": "site:docs.helicone.ai self-hosting Helicone open source features sessions evaluations official"
    },
    {
      "facet": "Ragas agent_evals",
      "query": "site:github.com/explodinggradients/ragas agent_evals Ragas official status"
    },
    {
      "facet": "Patent titles",
      "query": "Google Patents US11315043 US11615345 title"
    },
    {
      "facet": "Langfuse versus Phoenix contradiction",
      "query": "site:langfuse.com Phoenix comparison Langfuse open source self-host official"
    },
    {
      "facet": "License cross-check",
      "query": "official GitHub license metadata inspect_ai openllmetry Langfuse Helicone Ragas licenses"
    }
  ]
}
```

### source-registry.json
```json
{
  "sources": [
    {
      "id": "s1",
      "url": "https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/main/LICENSE",
      "title": "Inspect AI LICENSE (MIT)",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s2",
      "url": "https://github.com/traceloop/openllmetry",
      "title": "traceloop/openllmetry GitHub repository README and metadata",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s3",
      "url": "https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE",
      "title": "Langfuse repository root LICENSE with MIT and EE split",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s4",
      "url": "https://langfuse.com/handbook/chapters/open-source",
      "title": "Why is Langfuse Open Source?",
      "sourceType": "official",
      "fetched": true
    },
    {
      "id": "s5",
      "url": "https://langfuse.com/pricing-self-host",
      "title": "Langfuse Self-Hosted Pricing and Feature Comparison",
      "sourceType": "product",
      "fetched": true
    },
    {
      "id": "s6",
      "url": "https://docs.helicone.ai/references/open-source",
      "title": "Helicone Open Source",
      "sourceType": "official",
      "fetched": true
    },
    {
      "id": "s7",
      "url": "https://docs.helicone.ai/getting-started/self-host/overview",
      "title": "Helicone Self-Hosting Overview",
      "sourceType": "official",
      "fetched": true
    },
    {
      "id": "s8",
      "url": "https://github.com/vibrantlabsai/ragas",
      "title": "vibrantlabsai/ragas GitHub repository README and metadata",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s9",
      "url": "https://raw.githubusercontent.com/vibrantlabsai/ragas/main/docs/howtos/cli/agent_evals.md",
      "title": "Ragas Agent Evaluation Quickstart",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s10",
      "url": "https://patents.google.com/?q=(US11315043+OR+US11615345)",
      "title": "Google Patents combined query shell for US11315043 and US11615345",
      "sourceType": "legal",
      "fetched": true
    },
    {
      "id": "s11",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/README.md",
      "title": "Pinned Arize Phoenix README",
      "sourceType": "local",
      "fetched": true
    },
    {
      "id": "s12",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/LICENSE",
      "title": "Pinned Arize Phoenix LICENSE",
      "sourceType": "local",
      "fetched": true
    },
    {
      "id": "s13",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/docs/phoenix/resources/frequently-asked-questions/langfuse-alternative-arize-phoenix-vs-langfuse-key-differences.mdx",
      "title": "Pinned Phoenix Langfuse comparison page",
      "sourceType": "local",
      "fetched": true
    },
    {
      "id": "s14",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/IP_NOTICE",
      "title": "Pinned Phoenix IP_NOTICE",
      "sourceType": "local",
      "fetched": true
    }
  ]
}
```

### ledger.json
```json
{
  "meta": {
    "searchId": "search-2026-09-13-session-obs-second-pass-licenses",
    "mode": "styrir_plus",
    "totalQueriesRun": 8,
    "totalSourcesFetched": 10,
    "reservedFollowups": 2,
    "budget": {
      "maxSearchQueries": 10,
      "maxFetches": 10,
      "maxFollowups": 3,
      "maxConcurrency": 3
    },
    "accounting": "Eight bounded searches and ten external source reads. Local Phoenix reads are included in the source appendix and excluded from the external fetch count."
  },
  "entries": [
    {
      "id": "e1",
      "entity": "Inspect AI",
      "signalType": "license",
      "observation": "The fetched Inspect AI LICENSE begins with MIT License.",
      "possibleImplication": "MIT is a permissive reuse candidate with notice retention.",
      "sourceId": "s1",
      "sourceUrl": "https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/main/LICENSE",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e2",
      "entity": "OpenLLMetry",
      "signalType": "license",
      "observation": "The fetched traceloop/openllmetry repository metadata reports Apache License 2.0.",
      "possibleImplication": "The instrumentation repository is a permissive candidate for an independent adapter boundary.",
      "sourceId": "s2",
      "sourceUrl": "https://github.com/traceloop/openllmetry",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e3",
      "entity": "OpenLLMetry",
      "signalType": "tracing",
      "observation": "The OpenLLMetry README describes open-source observability for LLM applications based on OpenTelemetry.",
      "possibleImplication": "Use an OpenTelemetry-shaped event boundary rather than a vendor-specific trace schema.",
      "sourceId": "s2",
      "sourceUrl": "https://github.com/traceloop/openllmetry",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.98
    },
    {
      "id": "e4",
      "entity": "OpenLLMetry",
      "signalType": "export",
      "observation": "The OpenLLMetry README says traces can connect to Traceloop or existing observability solutions.",
      "possibleImplication": "Keep the destination/exporter replaceable and do not couple local evaluation to Traceloop.",
      "sourceId": "s2",
      "sourceUrl": "https://github.com/traceloop/openllmetry",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.95
    },
    {
      "id": "e5",
      "entity": "OpenLLMetry",
      "signalType": "coverage",
      "observation": "The OpenLLMetry README lists LLM providers, vector databases, frameworks, and MCP as instrumentation targets.",
      "possibleImplication": "A first-party adapter can preserve model, retrieval, tool, and protocol events.",
      "sourceId": "s2",
      "sourceUrl": "https://github.com/traceloop/openllmetry",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.89
    },
    {
      "id": "e6",
      "entity": "Langfuse",
      "signalType": "license",
      "observation": "The Langfuse root LICENSE assigns content outside ee/, web/src/ee/, and worker/src/ee/ to the MIT Expat license.",
      "possibleImplication": "The core repository is MIT-licensed outside the explicitly marked EE paths.",
      "sourceId": "s3",
      "sourceUrl": "https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 1.0
    },
    {
      "id": "e7",
      "entity": "Langfuse",
      "signalType": "license_boundary",
      "observation": "The Langfuse root LICENSE assigns content under ee/, web/src/ee/, and worker/src/ee/ to ee/LICENSE.",
      "possibleImplication": "Do not treat the whole monorepo as MIT without excluding the EE paths.",
      "sourceId": "s3",
      "sourceUrl": "https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 1.0
    },
    {
      "id": "e8",
      "entity": "Langfuse",
      "signalType": "third_party_license_boundary",
      "observation": "The Langfuse root LICENSE assigns third-party components to their original licenses.",
      "possibleImplication": "A redistribution audit still needs dependency-level notices.",
      "sourceId": "s3",
      "sourceUrl": "https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.92
    },
    {
      "id": "e9",
      "entity": "Langfuse",
      "signalType": "oss_feature",
      "observation": "Langfuse's open-source handbook lists tracing as an MIT-licensed product capability.",
      "possibleImplication": "Tracing behavior can be studied as part of the OSS core.",
      "sourceId": "s4",
      "sourceUrl": "https://langfuse.com/handbook/chapters/open-source",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.98
    },
    {
      "id": "e10",
      "entity": "Langfuse",
      "signalType": "oss_feature",
      "observation": "Langfuse's open-source handbook lists evaluations as an MIT-licensed product capability.",
      "possibleImplication": "Evaluation workflows are in the borrowable core rather than an assumed cloud-only feature.",
      "sourceId": "s4",
      "sourceUrl": "https://langfuse.com/handbook/chapters/open-source",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e11",
      "entity": "Langfuse",
      "signalType": "oss_feature",
      "observation": "Langfuse's open-source handbook lists the playground as an MIT-licensed product capability.",
      "possibleImplication": "Prompt iteration and judge setup can be treated as OSS-core references.",
      "sourceId": "s4",
      "sourceUrl": "https://langfuse.com/handbook/chapters/open-source",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.98
    },
    {
      "id": "e12",
      "entity": "Langfuse",
      "signalType": "commercial_boundary",
      "observation": "Langfuse's open-source handbook says SCIM, audit logging, and data retention policies require a commercial license for self-hosting.",
      "possibleImplication": "Keep enterprise governance modules outside a permissive borrow list.",
      "sourceId": "s4",
      "sourceUrl": "https://langfuse.com/handbook/chapters/open-source",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e13",
      "entity": "Langfuse",
      "signalType": "deployment_parity",
      "observation": "Langfuse's open-source handbook says OSS self-host, Enterprise self-host, and Cloud use the same codebase and schema.",
      "possibleImplication": "The local evaluator can model a single schema while keeping managed-service boundaries explicit.",
      "sourceId": "s4",
      "sourceUrl": "https://langfuse.com/handbook/chapters/open-source",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.95
    },
    {
      "id": "e14",
      "entity": "Langfuse",
      "signalType": "agent_tracing",
      "observation": "Langfuse self-hosted pricing lists traces and graphs for agents as available in Open Source.",
      "possibleImplication": "Use nested agent graph views as a comparison point for session reports.",
      "sourceId": "s5",
      "sourceUrl": "https://langfuse.com/pricing-self-host",
      "sourceType": "product",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.98
    },
    {
      "id": "e15",
      "entity": "Langfuse",
      "signalType": "agent_sessions",
      "observation": "Langfuse self-hosted pricing lists session tracking for chats and threads as available in Open Source.",
      "possibleImplication": "Keep session identity above individual turns in the normalized model.",
      "sourceId": "s5",
      "sourceUrl": "https://langfuse.com/pricing-self-host",
      "sourceType": "product",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e16",
      "entity": "Langfuse",
      "signalType": "evaluation",
      "observation": "Langfuse self-hosted pricing lists LLM-as-judge evaluators as available in Open Source.",
      "possibleImplication": "A local evaluator can borrow explicit judge configuration and provenance concepts.",
      "sourceId": "s5",
      "sourceUrl": "https://langfuse.com/pricing-self-host",
      "sourceType": "product",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e17",
      "entity": "Langfuse",
      "signalType": "playground",
      "observation": "Langfuse self-hosted pricing lists Playground as available in Open Source.",
      "possibleImplication": "The current official feature matrix supersedes the older paywall comparison for this claim.",
      "sourceId": "s5",
      "sourceUrl": "https://langfuse.com/pricing-self-host",
      "sourceType": "product",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e18",
      "entity": "Langfuse",
      "signalType": "cloud_boundary",
      "observation": "Langfuse self-hosted pricing marks Langfuse Assistant with '--' for both Open Source and Enterprise self-hosting.",
      "possibleImplication": "Treat the exact Assistant availability semantics as a follow-up question rather than generalizing from the self-host table.",
      "sourceId": "s5",
      "sourceUrl": "https://langfuse.com/pricing-self-host",
      "sourceType": "product",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.84
    },
    {
      "id": "e19",
      "entity": "Langfuse",
      "signalType": "dashboard",
      "observation": "Langfuse self-hosted pricing lists custom dashboards as available in Open Source.",
      "possibleImplication": "Borrow metric-catalog and dashboard grouping ideas while implementing independent static HTML.",
      "sourceId": "s5",
      "sourceUrl": "https://langfuse.com/pricing-self-host",
      "sourceType": "product",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.95
    },
    {
      "id": "e20",
      "entity": "Langfuse",
      "signalType": "self_hosting",
      "observation": "Langfuse self-hosted pricing lists unlimited usage for Open Source.",
      "possibleImplication": "Self-hosted usage caps should not be inferred from Cloud billable units.",
      "sourceId": "s5",
      "sourceUrl": "https://langfuse.com/pricing-self-host",
      "sourceType": "product",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.94
    },
    {
      "id": "e21",
      "entity": "Helicone",
      "signalType": "license",
      "observation": "Helicone's official Open Source page states Apache License 2.0.",
      "possibleImplication": "The documented project license is permissive for independent integration work.",
      "sourceId": "s6",
      "sourceUrl": "https://docs.helicone.ai/references/open-source",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e22",
      "entity": "Helicone",
      "signalType": "license_scope",
      "observation": "Helicone's official Open Source page says the project can be used, modified, and distributed.",
      "possibleImplication": "Borrow deployment and API ideas without assuming a cloud-only control plane.",
      "sourceId": "s6",
      "sourceUrl": "https://docs.helicone.ai/references/open-source",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.93
    },
    {
      "id": "e23",
      "entity": "Helicone",
      "signalType": "self_hosting",
      "observation": "Helicone's self-host overview lists Manual Installation.",
      "possibleImplication": "Manual component deployment is an available operational reference.",
      "sourceId": "s7",
      "sourceUrl": "https://docs.helicone.ai/getting-started/self-host/overview",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.88
    },
    {
      "id": "e24",
      "entity": "Helicone",
      "signalType": "self_hosting",
      "observation": "Helicone's self-host overview lists Docker Compose.",
      "possibleImplication": "Compose is a useful local-first deployment pattern.",
      "sourceId": "s7",
      "sourceUrl": "https://docs.helicone.ai/getting-started/self-host/overview",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.91
    },
    {
      "id": "e25",
      "entity": "Helicone",
      "signalType": "self_hosting",
      "observation": "Helicone's self-host overview lists Kubernetes deployment.",
      "possibleImplication": "Helm-oriented scaling is an available deployment reference.",
      "sourceId": "s7",
      "sourceUrl": "https://docs.helicone.ai/getting-started/self-host/overview",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.9
    },
    {
      "id": "e26",
      "entity": "Helicone",
      "signalType": "self_hosting",
      "observation": "Helicone's self-host overview lists cloud deployment on infrastructure such as AWS.",
      "possibleImplication": "Self-hosting guidance spans local and production infrastructure.",
      "sourceId": "s7",
      "sourceUrl": "https://docs.helicone.ai/getting-started/self-host/overview",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.86
    },
    {
      "id": "e27",
      "entity": "Helicone",
      "signalType": "support",
      "observation": "Helicone's self-host overview directs self-hosting support to its Discord community.",
      "possibleImplication": "Community support is part of the documented self-host path.",
      "sourceId": "s7",
      "sourceUrl": "https://docs.helicone.ai/getting-started/self-host/overview",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.75
    },
    {
      "id": "e28",
      "entity": "Helicone",
      "signalType": "support_boundary",
      "observation": "Helicone's self-host overview offers dedicated support through an enterprise agreement.",
      "possibleImplication": "Do not assume community self-host support includes enterprise commitments.",
      "sourceId": "s7",
      "sourceUrl": "https://docs.helicone.ai/getting-started/self-host/overview",
      "sourceType": "official",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.77
    },
    {
      "id": "e29",
      "entity": "Ragas",
      "signalType": "license",
      "observation": "The fetched Ragas repository metadata reports Apache License 2.0.",
      "possibleImplication": "Ragas is a permissive evaluation-library candidate.",
      "sourceId": "s8",
      "sourceUrl": "https://github.com/vibrantlabsai/ragas",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e30",
      "entity": "Ragas",
      "signalType": "quickstart",
      "observation": "The Ragas README lists rag_eval as an available quickstart template.",
      "possibleImplication": "The repository has at least one documented local evaluation project template.",
      "sourceId": "s8",
      "sourceUrl": "https://github.com/vibrantlabsai/ragas",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.86
    },
    {
      "id": "e31",
      "entity": "Ragas",
      "signalType": "agent_evals_status",
      "observation": "The Ragas README lists agent_evals under Coming Soon.",
      "possibleImplication": "The README does not support a claim that agent_evals is a stable released template.",
      "sourceId": "s8",
      "sourceUrl": "https://github.com/vibrantlabsai/ragas",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.98
    },
    {
      "id": "e32",
      "entity": "Ragas",
      "signalType": "agent_evals_status",
      "observation": "The Ragas agent-evals guide instructs users to run ragas quickstart agent_evals.",
      "possibleImplication": "The official guide documents an agent_evals command despite the README status label.",
      "sourceId": "s9",
      "sourceUrl": "https://raw.githubusercontent.com/vibrantlabsai/ragas/main/docs/howtos/cli/agent_evals.md",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.99
    },
    {
      "id": "e33",
      "entity": "Ragas",
      "signalType": "agent_evaluation",
      "observation": "The Ragas agent-evals guide describes an agent evaluation for mathematical problem solving.",
      "possibleImplication": "A small tool-using agent template is a useful structural reference.",
      "sourceId": "s9",
      "sourceUrl": "https://raw.githubusercontent.com/vibrantlabsai/ragas/main/docs/howtos/cli/agent_evals.md",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.9
    },
    {
      "id": "e34",
      "entity": "Ragas",
      "signalType": "agent_evaluation",
      "observation": "The Ragas agent-evals guide defines a binary correctness metric.",
      "possibleImplication": "Binary code-first checks are a simple seed for deterministic session evaluation.",
      "sourceId": "s9",
      "sourceUrl": "https://raw.githubusercontent.com/vibrantlabsai/ragas/main/docs/howtos/cli/agent_evals.md",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.94
    },
    {
      "id": "e35",
      "entity": "Ragas",
      "signalType": "artifact_shape",
      "observation": "The Ragas agent-evals guide includes datasets, experiments, and logs directories in the generated project structure.",
      "possibleImplication": "Separate inputs, result snapshots, and execution logs in a first-party evaluator.",
      "sourceId": "s9",
      "sourceUrl": "https://raw.githubusercontent.com/vibrantlabsai/ragas/main/docs/howtos/cli/agent_evals.md",
      "sourceType": "repo",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.93
    },
    {
      "id": "e36",
      "entity": "Arize Phoenix",
      "signalType": "license_posture",
      "observation": "The pinned Phoenix README describes Phoenix as an open-source AI observability platform.",
      "possibleImplication": "Classify the product label separately from the legal reuse terms.",
      "sourceId": "s11",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/README.md",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.98
    },
    {
      "id": "e37",
      "entity": "Arize Phoenix",
      "signalType": "license",
      "observation": "The pinned Phoenix LICENSE identifies Elastic License 2.0.",
      "possibleImplication": "Phoenix is not a permissive dependency for a competing hosted service.",
      "sourceId": "s12",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/LICENSE",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 1.0
    },
    {
      "id": "e38",
      "entity": "Arize Phoenix",
      "signalType": "hosted_service_restriction",
      "observation": "The pinned Phoenix LICENSE prohibits providing the software to third parties as a hosted or managed service with access to a substantial feature set.",
      "possibleImplication": "Do not vendor Phoenix into the first-party hosted product.",
      "sourceId": "s12",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/LICENSE",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 1.0
    },
    {
      "id": "e39",
      "entity": "Arize Phoenix",
      "signalType": "comparative_claim",
      "observation": "The pinned Phoenix Langfuse comparison page claims that Langfuse puts Prompt Playground behind a paywall.",
      "possibleImplication": "This claim is contradicted by the current Langfuse handbook and self-hosted pricing pages.",
      "sourceId": "s13",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/docs/phoenix/resources/frequently-asked-questions/langfuse-alternative-arize-phoenix-vs-langfuse-key-differences.mdx",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "medium",
      "relevance": 0.99
    },
    {
      "id": "e40",
      "entity": "Arize Phoenix",
      "signalType": "comparative_claim",
      "observation": "The pinned Phoenix Langfuse comparison page claims that Langfuse puts LLM-as-a-Judge evaluations behind a paywall.",
      "possibleImplication": "This claim is contradicted by the current Langfuse handbook and self-hosted pricing pages.",
      "sourceId": "s13",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/docs/phoenix/resources/frequently-asked-questions/langfuse-alternative-arize-phoenix-vs-langfuse-key-differences.mdx",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "medium",
      "relevance": 0.99
    },
    {
      "id": "e41",
      "entity": "Arize Phoenix",
      "signalType": "comparative_hosting_claim",
      "observation": "The pinned Phoenix Langfuse comparison page claims that Langfuse self-hosting requires ClickHouse, Redis, and S3-compatible storage.",
      "possibleImplication": "The claim is broadly consistent with the current Langfuse architecture listing, but operational requirements remain version-sensitive.",
      "sourceId": "s13",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/docs/phoenix/resources/frequently-asked-questions/langfuse-alternative-arize-phoenix-vs-langfuse-key-differences.mdx",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "medium",
      "relevance": 0.94
    },
    {
      "id": "e42",
      "entity": "Arize Phoenix",
      "signalType": "comparative_instrumentation_claim",
      "observation": "The pinned Phoenix Langfuse comparison page claims that Langfuse relies on outside instrumentation libraries.",
      "possibleImplication": "Current Langfuse docs list native integrations, SDKs, OpenTelemetry, and LiteLLM but do not settle the narrower auto-instrumentation claim.",
      "sourceId": "s13",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/docs/phoenix/resources/frequently-asked-questions/langfuse-alternative-arize-phoenix-vs-langfuse-key-differences.mdx",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "medium",
      "relevance": 0.91
    },
    {
      "id": "e43",
      "entity": "Arize Phoenix",
      "signalType": "patent_notice",
      "observation": "The pinned Phoenix IP_NOTICE names U.S. Patent Nos. 11,315,043 and 11,615,345.",
      "possibleImplication": "Patent-number context is recorded without copying claims or making a legal conclusion.",
      "sourceId": "s14",
      "sourceUrl": "local:///Users/brooks/Code/refs/observability/phoenix/IP_NOTICE",
      "sourceType": "local",
      "dateObserved": "2026-09-13",
      "confidence": "high",
      "relevance": 0.98
    },
    {
      "id": "e44",
      "entity": "Google Patents",
      "signalType": "patent_fetch_gap",
      "observation": "The fetched combined Google Patents query returned only a generic Google Patents shell.",
      "possibleImplication": "Direct record pages are required before treating patent titles as fetched evidence.",
      "sourceId": "s10",
      "sourceUrl": "https://patents.google.com/?q=(US11315043+OR+US11615345)",
      "sourceType": "legal",
      "dateObserved": "2026-09-13",
      "confidence": "low",
      "relevance": 0.98
    }
  ],
  "proofGaps": [
    {
      "description": "Inspect AI capability, output format, HTML reporting, self-hosting, and coding-agent session support were not established by the fetched LICENSE-only source.",
      "attemptedQueries": [
        "site:github.com/UKGovernmentBEIS/inspect_ai license LICENSE Inspect AI MIT GitHub"
      ]
    },
    {
      "description": "OpenLLMetry repository licensing is established, but the fetched repository page does not establish the Traceloop destination's platform license, self-hosting rights, or hosted feature boundary.",
      "attemptedQueries": [
        "site:github.com/traceloop/openllmetry LICENSE Traceloop open source platform official docs"
      ]
    },
    {
      "description": "The fetched Helicone pages establish Apache-2.0 and deployment methods but do not establish tracing, session trees, evaluator execution, dashboard parity, or static HTML export.",
      "attemptedQueries": [
        "site:docs.helicone.ai self-hosting Helicone open source features sessions evaluations official"
      ]
    },
    {
      "description": "Current Langfuse self-hosted pricing marks Langfuse Assistant with '--' for both self-host plans, but the fetched pages do not define that marker or establish a static HTML export surface.",
      "attemptedQueries": [
        "site:langfuse.com/docs self-hosted Langfuse open source cloud playground LLM-as-a-judge pricing features"
      ]
    },
    {
      "description": "Ragas has a current README conflict: agent_evals is listed under Coming Soon while the fetched guide documents the quickstart command. Release/version status is unresolved.",
      "attemptedQueries": [
        "site:github.com/explodinggradients/ragas agent_evals Ragas official status"
      ]
    },
    {
      "description": "The fetched Google Patents combined query returned a generic shell rather than records. Direct title pages https://patents.google.com/patent/US11315043/en and https://patents.google.com/patent/US11615345/en remain unfetched.",
      "attemptedQueries": [
        "Google Patents US11315043 US11615345 title"
      ]
    },
    {
      "description": "The pinned Phoenix Langfuse comparison page has no publication or version marker. Its paywall claims conflict with current Langfuse OSS pages, its storage claim is broadly corroborated by the current architecture page, and its instrumentation claim needs narrower versioned documentation.",
      "attemptedQueries": [
        "site:langfuse.com Phoenix comparison Langfuse open source self-host official",
        "site:langfuse.com/docs self-hosted Langfuse open source cloud playground LLM-as-a-judge pricing features"
      ]
    },
    {
      "description": "Langfuse's root LICENSE delegates third-party components to original licenses; this pass did not perform a transitive dependency or bundled-asset license audit.",
      "attemptedQueries": [
        "official GitHub license metadata inspect_ai openllmetry Langfuse Helicone Ragas licenses"
      ]
    }
  ],
  "sources": [
    {
      "id": "s1",
      "url": "https://raw.githubusercontent.com/UKGovernmentBEIS/inspect_ai/main/LICENSE",
      "title": "Inspect AI LICENSE (MIT)",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s2",
      "url": "https://github.com/traceloop/openllmetry",
      "title": "traceloop/openllmetry GitHub repository README and metadata",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s3",
      "url": "https://raw.githubusercontent.com/langfuse/langfuse/main/LICENSE",
      "title": "Langfuse repository root LICENSE with MIT and EE split",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s4",
      "url": "https://langfuse.com/handbook/chapters/open-source",
      "title": "Why is Langfuse Open Source?",
      "sourceType": "official",
      "fetched": true
    },
    {
      "id": "s5",
      "url": "https://langfuse.com/pricing-self-host",
      "title": "Langfuse Self-Hosted Pricing and Feature Comparison",
      "sourceType": "product",
      "fetched": true
    },
    {
      "id": "s6",
      "url": "https://docs.helicone.ai/references/open-source",
      "title": "Helicone Open Source",
      "sourceType": "official",
      "fetched": true
    },
    {
      "id": "s7",
      "url": "https://docs.helicone.ai/getting-started/self-host/overview",
      "title": "Helicone Self-Hosting Overview",
      "sourceType": "official",
      "fetched": true
    },
    {
      "id": "s8",
      "url": "https://github.com/vibrantlabsai/ragas",
      "title": "vibrantlabsai/ragas GitHub repository README and metadata",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s9",
      "url": "https://raw.githubusercontent.com/vibrantlabsai/ragas/main/docs/howtos/cli/agent_evals.md",
      "title": "Ragas Agent Evaluation Quickstart",
      "sourceType": "repo",
      "fetched": true
    },
    {
      "id": "s10",
      "url": "https://patents.google.com/?q=(US11315043+OR+US11615345)",
      "title": "Google Patents combined query shell for US11315043 and US11615345",
      "sourceType": "legal",
      "fetched": true
    },
    {
      "id": "s11",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/README.md",
      "title": "Pinned Arize Phoenix README",
      "sourceType": "local",
      "fetched": true
    },
    {
      "id": "s12",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/LICENSE",
      "title": "Pinned Arize Phoenix LICENSE",
      "sourceType": "local",
      "fetched": true
    },
    {
      "id": "s13",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/docs/phoenix/resources/frequently-asked-questions/langfuse-alternative-arize-phoenix-vs-langfuse-key-differences.mdx",
      "title": "Pinned Phoenix Langfuse comparison page",
      "sourceType": "local",
      "fetched": true
    },
    {
      "id": "s14",
      "url": "local:///Users/brooks/Code/refs/observability/phoenix/IP_NOTICE",
      "title": "Pinned Phoenix IP_NOTICE",
      "sourceType": "local",
      "fetched": true
    }
  ]
}
```

### contradiction-sweep.md
```markdown
# Contradiction sweep: license, open-core, and patent proof gaps

## Langfuse versus the pinned Phoenix comparison

| Claim in pinned Phoenix page | Current fetched evidence | Status for the report |
|---|---|---|
| Langfuse puts Prompt Playground behind a paywall | Langfuse's handbook lists the playground as MIT-licensed [s4]. Self-hosted pricing lists Playground as Open Source = Yes [s5]. | Resolved in favor of the current first-party pages. The Phoenix page has no publication or version marker and should not be repeated as current fact. |
| Langfuse puts LLM-as-a-Judge behind a paywall | Langfuse's handbook lists evaluations as MIT-licensed [s4]. Self-hosted pricing lists LLM-as-judge evaluators as Open Source = Yes [s5]. | Resolved in favor of the current first-party pages. |
| Langfuse requires ClickHouse, Redis, and S3-compatible storage | Langfuse's current handbook architecture names ClickHouse, Redis/Valkey, and S3/blob storage as the self-host stack [s4]. | Broadly corroborated as an architecture/deployment concern, not a license contradiction. Exact required-versus-optional details remain version-sensitive. |
| Langfuse relies on outside instrumentation libraries | Current self-host pricing lists native framework integrations, Python/JavaScript SDKs, OpenTelemetry, LiteLLM proxy logging, and a custom API [s5]. | Narrowed rather than fully resolved. The current table does not establish whether Langfuse maintains first-party auto-instrumentation for every provider, so avoid an absolute either/or claim. |

## Open-source labels versus legal boundaries

- Phoenix's pinned README uses the open-source label [s11], while its pinned LICENSE is Elastic License 2.0 [s12] and prohibits offering a substantial feature set as a hosted or managed service [s12]. Treat Phoenix as source-available/self-hostable, not as a permissive dependency for a competing hosted Styrir service.
- Langfuse's root LICENSE is mixed: MIT Expat outside the explicitly marked EE paths and `ee/LICENSE` inside those paths [s3]. Its current handbook says core tracing, evaluations, prompt management, experiments, annotation, and playground are MIT, while SCIM, audit logging, and data retention policies require a commercial license [s4]. Use the precise label “MIT-core with commercial EE modules,” not an unqualified whole-monorepo MIT claim.
- OpenLLMetry's repository is Apache-2.0 and is an OpenTelemetry instrumentation/export layer [s2]. The fetched source does not establish the Traceloop destination/platform license or self-hosting rights. Do not infer platform rights from the SDK/repository license.
- Helicone's fetched official page states Apache-2.0 and supports a self-hosting posture [s6]. The fetched deployment overview proves Manual, Docker Compose, Kubernetes, and cloud deployment methods [s7] but does not prove feature parity, session support, evaluator execution, or static HTML output.

## Ragas agent_evals status

The Ragas repository README marks `agent_evals` as Coming Soon [s8], while the current official guide supplies `ragas quickstart agent_evals`, a math-agent evaluation, a binary correctness metric, and datasets/experiments/logs structure [s9]. Record this as a documentation/release-status contradiction. Borrow the template structure and metric idea, but do not call the template a stable released surface until a versioned CLI/release check resolves the conflict.

## Patent title-only record

Phoenix's IP_NOTICE names U.S. Patent Nos. 11,315,043 and 11,615,345 [s14]. The fetched combined Google Patents query returned only the generic shell [s10]. Search discovery reported the same title for both requested records:

- **US 11,315,043 — Systems and methods for optimizing a machine learning model**
- **US 11,615,345 — Systems and methods for optimizing a machine learning model**

These are title-only provisional entries from search discovery, not fetched patent records. Direct record pages remain an explicit gap: `https://patents.google.com/patent/US11315043/en` and `https://patents.google.com/patent/US11615345/en`. No abstract, claim, scope, or legal conclusion is asserted.

## Compact decision table

| Entity | License / proof | Self-host, UI, eval, session status | Borrowable surface and boundary |
|---|---|---|---|
| Inspect AI | MIT in raw LICENSE [s1] | Harness role, output/HTML, and agent-session support were not established by the fetched license-only source | Re-check repository/package docs before borrowing; MIT notice retention applies. |
| OpenLLMetry / Traceloop | OpenLLMetry repository Apache-2.0 [s2]; Traceloop destination/platform terms are a proof gap | OTEL instrumentation/export is documented; no UI or static HTML proof in fetched source | Borrow vendor-neutral span/export boundary; do not assume Traceloop platform rights. |
| Langfuse | MIT outside marked EE paths; EE paths use `ee/LICENSE` [s3] | OSS self-host includes agent traces/graphs, sessions, Playground, LLM-as-judge, custom dashboards, unlimited usage [s4][s5]; Assistant marker is `--` in both self-host columns [s5] | Strong borrow reference for session/trace/eval/dashboard schema; keep EE governance modules and static HTML semantics separate. |
| Helicone | Apache-2.0 [s6] | Manual, Compose, Kubernetes, and cloud self-host methods [s7]; feature/session/evaluator/HTML details remain gaps | Borrow deployment choices and explicit OSS boundary; fetch feature pages before claiming parity. |
| Ragas | Apache-2.0 repository metadata [s8] | Agent-evals guide exists [s9], but README says Coming Soon [s8]; no UI/static HTML proof | Borrow local agent.py/evals.py plus datasets/experiments/logs and binary correctness; treat release status as unresolved. |
| Arize Phoenix baseline | README says open-source [s11], but LICENSE is ELv2 with hosted-service restriction [s12] | Local comparison reference only | Do not vendor Phoenix into a hosted Styrir product. |
| Patent records | Title-only search discovery; direct Google Patents fetch gap [s10][s14] | Not applicable | Retain numbers and titles only; no claim/abstract reuse. |
```

### gate-result.json (expected after parent runs both gates)
```json
{
  "gateStatus": "pass",
  "blockers": [],
  "warnings": [],
  "counts": {
    "entries": 44,
    "sources": 14,
    "proofGaps": 8
  }
}
```

The gate-result above is a candidate deterministic result, not a claim that a command was run in this read-only scout. Parent must persist the bodies, run `styrir-search-gate.ts` and `styrir-artifact-gate.ts styrir_plus /Users/brooks/Code/agent-ops/.styrir/runs/2026-09-13-session-obs/second-pass-licenses/`, then replace counts/status with command output. The ledger is structured to pass: all entries reference fetched appendix sources, source URLs/types match, observations avoid inference verbs, and proof gaps are non-empty.
