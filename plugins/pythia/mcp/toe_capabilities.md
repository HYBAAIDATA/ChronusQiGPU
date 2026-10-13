# MCP tool surface — twelve TOE capabilities

Maps onto `euclid/cognition/toe_capabilities.py`. Every result carries its truth class and a digest. A decision may return REFUSED or ACQUIRE_EVIDENCE, not only ACT.

| Capability | MCP tool | Truth-class envelope |
|------------|----------|----------------------|
| represent | toe_represent | observation → multi-representation state |
| model | toe_model | world model with contradiction detection |
| identify | toe_identify | causal identification; may REFUSE |
| intervene | toe_intervene | intervention query |
| counterfactual | toe_counterfactual | counterfactual query |
| evaluate_futures | toe_evaluate_futures | futures evaluation |
| uncertainty | toe_uncertainty | value of information over declared ranges |
| plan | toe_plan | plan under constraints |
| request_information | toe_request_information | evidence acquisition |
| explain | toe_explain | explanation of decision |
| revise | toe_revise | world-model revision |
| run | toe_run | full cycle; may return REFUSED or ACQUIRE_EVIDENCE |

## Rule

An MCP layer that flattens these into "here's your answer" undoes the discipline the backend enforces. Expose the refusals as first-class results.
