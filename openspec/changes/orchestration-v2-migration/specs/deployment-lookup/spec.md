## REMOVED Requirements

### Requirement: Deployment ID Configuration
**Reason**: Per-model deployment IDs (`model_to_deployment_ids`) are replaced by the Orchestration V2 architecture where a single orchestration deployment serves all models. Model routing is done by passing `model_name` in the request body, not by selecting a deployment URL.
**Migration**: Remove `model_to_deployment_ids` and `deployment_models` from `config.json`. Add `orchestration_url` to each subaccount, or rely on auto-discovery of the orchestration service deployment.
