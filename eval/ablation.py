#!/usr/bin/env python3
"""
Ablation studies: Test individual defense layers
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import requests
except ImportError:
    print("Warning: requests not installed. Install with: pip install requests")
    requests = None

# Import MedGuardEvaluator
sys.path.insert(0, str(Path(__file__).parent))
from baseline import MedGuardEvaluator


class AblationEvaluator:
    """
    Evaluate different MedGuard configurations for ablation studies
    
    Configurations:
    - baseline: Direct Bedrock (no defenses)
    - phi_only: PHI redaction only (no injection detection)
    - injection_only: Injection detection only (no PHI redaction)
    - full_stack: All defenses enabled
    """
    
    def __init__(self, api_url: str, auth_token: Optional[str] = None):
        self.api_url = api_url
        self.auth_token = auth_token
    
    def evaluate_configuration(
        self,
        test_cases: List[Dict],
        config_name: str,
        disable_phi: bool = False,
        disable_injection: bool = False
    ) -> List[Dict]:
        """
        Evaluate a specific configuration
        
        Note: This requires modifying the handler to support config flags.
        For now, we simulate by analyzing responses.
        """
        results = []
        
        # For true ablation, we'd need handler modifications
        # For now, we'll use the full MedGuard and analyze what defenses triggered
        evaluator = MedGuardEvaluator(self.api_url, self.auth_token)
        
        for test_case in test_cases:
            prompt = test_case.get("prompt", "")
            result = evaluator.invoke_medguard(prompt)
            
            # Simulate disabled defenses
            if disable_phi:
                result["phi_counts_input"] = {}
                result["phi_counts_output"] = {}
            
            if disable_injection:
                result["injection_score"] = 0
            
            results.append(result)
            time.sleep(0.5)
        
        return results
    
    def run_ablation_study(
        self,
        test_cases: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """
        Run full ablation study across all configurations
        
        Returns:
            Dict mapping config name to results
        """
        configurations = {
            "full_stack": {"disable_phi": False, "disable_injection": False},
            # Note: True ablation requires handler modifications
            # These are placeholders for when we add config flags
        }
        
        results = {}
        
        for config_name, config_params in configurations.items():
            print(f"Evaluating configuration: {config_name}")
            results[config_name] = self.evaluate_configuration(
                test_cases,
                config_name,
                **config_params
            )
        
        return results


def analyze_defense_contribution(
    ablation_results: Dict[str, List[Dict]]
) -> Dict[str, float]:
    """
    Analyze contribution of each defense layer
    
    Returns:
        Dict with marginal benefit of each layer
    """
    # This would compare:
    # - baseline vs phi_only: PHI defense benefit
    # - baseline vs injection_only: Injection defense benefit
    # - baseline vs full_stack: Combined benefit
    
    # Placeholder - requires baseline comparison
    return {
        "phi_defense_benefit": 0.0,
        "injection_defense_benefit": 0.0,
        "combined_benefit": 0.0
    }
