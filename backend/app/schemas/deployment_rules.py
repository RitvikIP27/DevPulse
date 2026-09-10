from pydantic import BaseModel, Field


class DeploymentRuleCreate(BaseModel):
    workflow_name_pattern: str = Field(min_length=1, max_length=200)
    environment: str = Field(default="production", min_length=1, max_length=100)
    is_production: bool = True


class DeploymentRuleOut(BaseModel):
    id: int
    repository_id: int
    workflow_name_pattern: str
    environment: str
    is_production: bool
    matched_run_count: int


class DeploymentRuleListResponse(BaseModel):
    rules: list[DeploymentRuleOut]
    deployment_source: str
