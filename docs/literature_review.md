# Literature review and research gap

VibePrompt is presented as an NLP-based conversational requirements engineering system for agentic prompt generation. This note records the literature the design depends on and the gap the implementation is meant to measure. It does not claim that similarity, natural language inference, or prompt generation are individually new.

## Conversational requirements engineering

Requirements are rarely complete at the first statement. They are elicited, negotiated, and revised (Nuseibeh and Easterbrook, 2000). Standards such as ISO/IEC/IEEE 29148:2018 expect an identified problem, stakeholders, requirements, and constraints, not an undifferentiated chat log. In student projects the revision is especially informal: features are added, technologies are swapped, and the original objective can disappear. A chatbot can discuss those changes without keeping an authoritative structured state. That is the operational problem in the project definition.

## Traceability

Gotel and Finkelstein (1994) showed that requirements are hard to follow into design and test artifacts once their wording changes. VibePrompt therefore assigns stable identifiers (`REQ-001`) and keeps versions when a requirement is modified or removed. The specification and the compiled prompt are required to contain those identifiers. Coverage is defined as the share of validated requirement IDs still present in the artifact, not as a subjective reading of the conversation.

## Intent and extraction

User turns in this setting are actions on a project, not open-domain chat. The initial label set is `PROJECT_DESCRIPTION`, `ADD_REQUIREMENT`, `REMOVE_REQUIREMENT`, `MODIFY_REQUIREMENT`, `ASK_QUESTION`, `ASK_FEASIBILITY`, `SELECT_IDEA`, `REJECT_IDEA`, `REQUEST_GRILL`, `REQUEST_PROFESSIONAL_REVIEW`, `CHANGE_TECHNOLOGY`, `CHANGE_SCOPE`, `FINALIZE_PROJECT`, and `GENERATE_PROMPT`. Classical baselines are TF-IDF with logistic regression and TF-IDF with a linear SVM, following the usual comparison of sparse lexical models against later transformer classifiers (Devlin et al., 2019). A transformer classifier is an evaluation target, not a dependency of the running system.

Extraction is hybrid. Rules and lexicons capture duration, team size, exclusions, technologies, and "must use" slots. spaCy supplies linguistic features when the English model is installed (Honnibal et al., 2020). Large language model JSON is merged only after Pydantic validation. Free-form model text is not written into project state.

## Semantic similarity

Paraphrase is the normal way requirements drift in wording. "Detect phishing emails" and "Identify malicious email messages" should link rather than become two unrelated requirements. Sentence-BERT (Reimers and Gurevych, 2019) is the intended embedding model, compared with TF-IDF or hashing similarity on a manually labeled 0–3 scale. Duplicate detection is a thresholded view of the same scores. The threshold is selected from validation data. The implementation does not treat any cutoff as universal.

## Contradiction

Two requirements can be mutually exclusive without sharing many words: a backend that must use Python and a backend that must use Java. Natural language inference, trained on datasets such as SNLI (Bowman et al., 2015) and MultiNLI (Williams et al., 2018), provides the entailment / neutral / contradiction distinction. The project maps that evidence onto `SUPPORTS`, `CONTRADICTS`, `MODIFIES`, `EXTENDS`, and `UNRELATED`, with a rule baseline for technology slots. When a contradiction is detected, the existing decision is not silently replaced. The user decides.

## Drift and scope

Concept drift in machine learning is a change in the data-generating process over time (Gama et al., 2014). The analogue here is a change in the project's objective during conversation: facial recognition, drone control, or a blockchain payment system added to an NLP phishing classifier. Embeddings supply a per-requirement similarity to the locked objective. Unrelated technical domains are the operational drift flag, because a single cosine cutoff is not a general law. Scope analysis is separate: extra clients, browser extensions, and a rising requirement count against a short deadline are scope expansion even when they still serve the original domain. Both reports leave the decision with the user.

## Language models as supporting generators

Transformers (Vaswani et al., 2017) and code-trained models (Chen et al., 2021) made it practical to ask a model to write software from a prompt. Surveys of language models for software engineering, including Hou et al. (2024), describe assistants that generate code, tests, and summaries. Those systems generally consume a prompt or a repository. They do not, by themselves, maintain a versioned requirements state across a student conversation or prove that the final prompt still contains the requirements that were agreed. Gemini is used here for generation: ideas, explanations, and optional prose. It is behind a provider interface so the backend is not coupled to one vendor. Multi-model generation is an optional later path for perspective diversity, not a Version 1 requirement.

## Research gap

Existing work already covers requirements elicitation, semantic similarity, natural language inference, and LLM software assistance as separate pieces. What is not established by that work is a measured pipeline that:

1. classifies conversational project actions,
2. stores a versioned requirement state with stable IDs,
3. detects paraphrase, contradiction, and domain drift against that state,
4. compiles an agent prompt from the specification rather than from the transcript, and
5. compares requirement coverage with a baseline that prompts a model from the conversation alone.

That comparison is RQ5. RQ1–RQ4 correspond to the intent, similarity, contradiction, and drift evaluations. Optional RQ6, on multi-model idea diversity, is out of the default path.

The contribution claimed for VibePrompt is this integration, the annotated dataset, and the evaluation method. It is not a claim that each component is novel.

## References

Bowman, S. R., Angeli, G., Potts, C., and Manning, C. D. (2015). A large annotated corpus for learning natural language inference. *Proceedings of EMNLP*.

Chen, M., Tworek, J., Jun, H., Yuan, Q., Pinto, H. P. d. O., Kaplan, J., Edwards, H., Burda, Y., Joseph, N., Brockman, G., et al. (2021). Evaluating large language models trained on code. arXiv:2107.03374.

Devlin, J., Chang, M.-W., Lee, K., and Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. *Proceedings of NAACL*.

Gama, J., Žliobaitė, I., Bifet, A., Pechenizkiy, M., and Bouchachia, A. (2014). A survey on concept drift adaptation. *ACM Computing Surveys*, 46(4).

Gotel, O. C. Z., and Finkelstein, A. C. W. (1994). An analysis of the requirements traceability problem. *Proceedings of the First International Conference on Requirements Engineering*.

Honnibal, M., Montani, I., Van Landeghem, S., and Boyd, A. (2020). spaCy: Industrial-strength natural language processing in Python. https://spacy.io

Hou, X., Zhao, Y., Liu, Y., Yang, Z., Wang, K., Li, L., Luo, X., Lo, D., Grundy, J., and Wang, H. (2024). Large language models for software engineering: A systematic literature review. *ACM Transactions on Software Engineering and Methodology*.

ISO/IEC/IEEE 29148:2018. Systems and software engineering — Life cycle processes — Requirements engineering.

Nuseibeh, B., and Easterbrook, S. (2000). Requirements engineering: a roadmap. *Proceedings of the Conference on the Future of Software Engineering*.

Reimers, N., and Gurevych, I. (2019). Sentence-BERT: Sentence embeddings using Siamese BERT-networks. *Proceedings of EMNLP-IJCNLP*.

Vaswani, A., Shazeer, N., Parmar, N., Uszkoreit, J., Jones, L., Gomez, A. N., Kaiser, Ł., and Polosukhin, I. (2017). Attention is all you need. *Advances in Neural Information Processing Systems*.

Williams, A., Nangia, N., and Bowman, S. R. (2018). A broad-coverage challenge corpus for sentence understanding through inference. *Proceedings of NAACL*.
