from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class HypothesisDefinition(BaseModel):
    id: str = Field(..., description="Unique identifier for the hypothesis, e.g., H1")
    description: str = Field(..., description="Human-readable explanation of the hypothesized issue")
    prior_probability: float = Field(..., description="Initial probability belief (0.0 to 1.0)")

class DiagnosticTest(BaseModel):
    hypothesis_id: str = Field(..., description="The ID of the hypothesis this test diagnoses")
    script: str = Field(..., description="Python script to run in the isolated sandbox environment")
    expected_positive_output: str = Field(..., description="Stdout string that indicates a confirmed hypothesis")
    expected_negative_output: str = Field(..., description="Stdout string that indicates a falsified hypothesis")

class VerificationSuite(BaseModel):
    regression_script: str = Field(..., description="Script to verify if the primary feature is restored to healthy")
    adversarial_script: str = Field(..., description="Script to test corner cases and check for new regressions")

class IncidentDefinition(BaseModel):
    id: str = Field(..., description="Unique incident ID, e.g., RCB-001")
    category: str = Field(..., description="Category from the 10 core categories (e.g., Database, Network)")
    title: str = Field(..., description="Name of the specific incident")
    symptoms: Dict[str, Any] = Field(..., description="Initial metrics, error logs, or trace details")
    ground_truth_cause: str = Field(..., description="The actual hypothesis ID that is the true cause")
    hypotheses: List[HypothesisDefinition] = Field(..., description="List of candidate hypotheses for the incident")
    diagnostic_tests: List[DiagnosticTest] = Field(..., description="Available diagnostic tests to run")
    verification_suite: VerificationSuite = Field(..., description="Tests to run for patch approval")
    injected_fault_script: str = Field(..., description="Script that applies the fault to the replica workspace")
    correct_patch: str = Field(..., description="Git diff/patch text that correctly resolves the incident")
