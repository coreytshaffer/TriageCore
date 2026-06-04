# Supporting References

This document collects source material for TriageCore as a scientific model evaluation and token-balancing workbench. The first section is a draft APA 7-style reference list for future paper development. The second section explains how each source supports the project.

## Draft APA 7 Reference List

Chen, L., Zaharia, M., & Zou, J. (2023). *FrugalGPT: How to use large language models while reducing cost and improving performance*. arXiv. https://arxiv.org/abs/2305.05176

Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J. W., Wallach, H., Daume III, H., & Crawford, K. (2021). Datasheets for datasets. *Communications of the ACM, 64*(12), 86-92. https://doi.org/10.1145/3458723

Liang, P., Bommasani, R., Lee, T., Tsipras, D., Soylu, D., Yasunaga, M., Zhang, Y., Narayanan, D., Wu, Y., Kumar, A., Newman, B., Yuan, B., Yan, B., Zhang, C., Cosgrove, C., Manning, C. D., Re, C., Acosta-Navas, D., Hudson, D. A., ... Wu, Y. (2022). *Holistic evaluation of language models*. arXiv. https://arxiv.org/abs/2211.09110

Mitchell, M., Wu, S., Zaldivar, A., Barnes, P., Vasserman, L., Hutchinson, B., Spitzer, E., Raji, I. D., & Gebru, T. (2019). Model cards for model reporting. In *Proceedings of the Conference on Fairness, Accountability, and Transparency* (pp. 220-229). Association for Computing Machinery. https://doi.org/10.1145/3287560.3287596

National Institute of Standards and Technology. (2023). *Artificial intelligence risk management framework (AI RMF 1.0)* (NIST AI 100-1). U.S. Department of Commerce. https://doi.org/10.6028/NIST.AI.100-1

National Institute of Standards and Technology. (n.d.). *AI RMF core*. NIST Trustworthy and Responsible AI Resource Center. Retrieved June 4, 2026, from https://airc.nist.gov/airmf-resources/airmf/5-sec-core/

Organisation for Economic Co-operation and Development. (n.d.). *OECD AI principles*. Retrieved June 4, 2026, from https://www.oecd.org/en/topics/ai-principles.html

Patterson, D., Gonzalez, J., Le, Q., Liang, C., Munguia, L. M., Rothchild, D., So, D., Texier, M., & Dean, J. (2021). *Carbon emissions and large neural network training*. arXiv. https://arxiv.org/abs/2104.10350

Schwartz, R., Dodge, J., Smith, N. A., & Etzioni, O. (2020). Green AI. *Communications of the ACM, 63*(12), 54-63. https://doi.org/10.1145/3381831

Shinn, N., Cassano, F., Berman, E., Gopinath, A., Narasimhan, K., & Yao, S. (2023). *Reflexion: Language agents with verbal reinforcement learning*. arXiv. https://arxiv.org/abs/2303.11366

Stanford Center for Research on Foundation Models. (n.d.). *Holistic evaluation of language models*. Retrieved June 4, 2026, from https://crfm.stanford.edu/helm/

Strubell, E., Ganesh, A., & McCallum, A. (2019). *Energy and policy considerations for deep learning in NLP*. arXiv. https://arxiv.org/abs/1906.02243

Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2022). *ReAct: Synergizing reasoning and acting in language models*. arXiv. https://arxiv.org/abs/2210.03629

## Project Notes

### Adjacent Tooling

CodeCarbon is a mature reference for Python-side energy and emissions tracking. TriageCore should not try to replace it; future work can either integrate it or use it as a validation reference for local estimates. <https://docs.codecarbon.io/>

Green Algorithms is a useful reference for transparent computational footprint estimation and calculator-style public communication. TriageCore can borrow the clarity of its assumptions and boundary reporting. <https://www.green-algorithms.org/>

EcoLogits is directly relevant for generative-AI impact estimation, especially API-based LLM use. TriageCore's local-backend ledger can complement this by focusing on local model and workbench-level decisions. <https://ecologits.ai/>

OpenTelemetry is the stronger general-purpose standard for traces, metrics, and logs across distributed software. TriageCore should learn from its trace/log vocabulary when coordinating disparate tools, while staying smaller and local-first. <https://opentelemetry.io/docs/>

LangGraph and AutoGen are stronger full agent-orchestration frameworks. TriageCore can remain useful by focusing on human-readable task ledgers, bounded handoffs, review decisions, local backend comparison, and environmental evidence rather than competing as a general-purpose agent framework. <https://docs.langchain.com/oss/python/langgraph> <https://microsoft.github.io/autogen/>

### Model Evaluation

HELM supports the evaluation design because it argues for broad, transparent, reproducible model evaluation instead of relying on one benchmark or one aggregate score.

The Stanford HELM project site is useful as a practical reference for scenarios, metrics, model comparisons, and public release of prompts and completions.

### Token Balancing And Model Routing

FrugalGPT supports TriageCore's idea that routing should be task-sensitive. The project can compare smaller local models, larger local models, and handoff paths as a cascade rather than treating one model as universally best.

### Human Oversight And AI Risk Management

The NIST AI RMF provides a defensible governance frame for risk classification, measurement, management, documentation, and accountability.

The NIST AI RMF Core supports defined and documented human oversight processes. This maps directly to TriageCore's principle that learning updates should be proposed by the system but accepted by a human.

The OECD AI Principles support transparency, responsible disclosure, robustness, safety, and accountability. These are useful for positioning TriageCore as a responsible local AI workbench rather than only a developer utility.

### Documentation And Auditability

Model Cards support the idea that model performance should be documented by intended use, limitations, and measured behavior. TriageCore can produce local model cards or task-class cards from its ledger.

Datasheets support transparent documentation of benchmark tasks, input files, prompt sets, and evaluation datasets used by TriageCore.

### Compute, Energy, And Sustainability

Green AI supports treating efficiency as a first-class evaluation criterion alongside accuracy or task success.

Strubell et al. help justify energy and compute accounting as part of AI evaluation methodology, especially for NLP systems.

Patterson et al. provide a useful carbon accounting frame and show why hardware, datacenter location, model architecture, and efficiency choices matter.

### Agent Learning And Reflection

Reflexion supports the idea that agents can learn from trial-and-error feedback without updating model weights. TriageCore should adapt this cautiously by storing proposed lessons for human review.

ReAct supports the design value of observable reasoning/action traces. TriageCore can use this idea for audit trails while keeping sensitive reasoning and irreversible tool use subject to review.

## Mapping To TriageCore

| TriageCore goal | Supporting references |
| --- | --- |
| Transparent model evaluation | HELM |
| Token-aware model routing | FrugalGPT, Green AI |
| Human-reviewed learning | NIST AI RMF, OECD AI Principles, Reflexion |
| Local audit trails | Model Cards, Datasheets, NIST AI RMF |
| Energy and emissions logging | Green AI, Strubell et al., Patterson et al. |
| Agent traceability | ReAct, NIST AI RMF |

## Suggested Paper Framing

TriageCore can be framed as a small-scale experimental system for studying whether local AI agents can be routed, evaluated, and improved through transparent evidence logs while preserving human authority over behavioral changes.

Suggested research question:

Can a local-first agent workbench reduce unnecessary high-cost model use while preserving safety, auditability, and human review through task classification, token-aware routing, and append-only mistake logging?
