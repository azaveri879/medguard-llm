#!/usr/bin/env python3
"""
Baseline comparison: Direct Bedrock invocation vs MedGuard
"""

import json
import time
from typing import Dict, List, Optional

try:
    import boto3
    import requests
except ImportError:
    print("Warning: boto3 or requests not installed. Install with: pip install boto3 requests")
    boto3 = None
    requests = None


class BaselineEvaluator:
    """Evaluate baseline (direct Bedrock) performance"""
    
    def __init__(self, model_id: str = "anthropic.claude-3-haiku-20240307-v1:0", region: str = "us-east-1"):
        if boto3 is None:
            raise ImportError("boto3 is required for baseline evaluation. Install with: pip install boto3")
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = model_id
    
    def invoke_direct(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Dict:
        """
        Invoke Bedrock directly without MedGuard
        
        Returns:
            Dict with response, latency_ms, success
        """
        start_time = time.time()
        
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 700,
                "temperature": 0.2,
            }
            
            if system_prompt:
                body["system"] = system_prompt
            else:
                body["system"] = "You are a helpful assistant."
            
            body["messages"] = [{"role": "user", "content": prompt}]
            
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body).encode("utf-8"),
                accept="application/json",
                contentType="application/json",
            )
            
            payload = json.loads(response["body"].read())
            response_text = payload.get("content", [{}])[0].get("text", "") if "content" in payload else json.dumps(payload)
            
            latency_ms = (time.time() - start_time) * 1000
            
            return {
                "response": response_text,
                "latency_ms": latency_ms,
                "success": True,
                "input": prompt,
                "phi_counts_input": {},  # No PHI detection in baseline
                "injection_score": 0  # No injection detection in baseline
            }
            
        except Exception as e:
            return {
                "response": "",
                "latency_ms": (time.time() - start_time) * 1000,
                "success": False,
                "error": str(e),
                "input": prompt,
                "phi_counts_input": {},
                "injection_score": 0
            }


class MedGuardEvaluator:
    """Evaluate MedGuard endpoint"""
    
    def __init__(self, api_url: str, auth_token: Optional[str] = None):
        if requests is None:
            raise ImportError("requests is required for MedGuard evaluation. Install with: pip install requests")
        self.api_url = api_url
        self.auth_token = auth_token
    
    def invoke_medguard(
        self,
        prompt: str,
        user_id: str = "eval_user",
        role: str = "resident"
    ) -> Dict:
        """
        Invoke MedGuard endpoint
        
        Returns:
            Dict with response, latency_ms, success, and MedGuard metrics
        """
        start_time = time.time()
        
        try:
            headers = {"Content-Type": "application/json"}
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            
            payload = {
                "user_id": user_id,
                "role": role,
                "prompt": prompt
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            latency_ms = (time.time() - start_time) * 1000
            
            return {
                "response": result.get("response", ""),
                "latency_ms": latency_ms,
                "success": True,
                "input": prompt,
                "phi_counts_input": result.get("redaction_summary", {}),
                "injection_score": result.get("safety_flags", {}).get("injection_score", 0),
                "request_id": result.get("request_id")
            }
            
        except Exception as e:
            return {
                "response": "",
                "latency_ms": (time.time() - start_time) * 1000,
                "success": False,
                "error": str(e),
                "input": prompt,
                "phi_counts_input": {},
                "injection_score": 0
            }


def run_baseline_comparison(
    test_cases: List[Dict],
    medguard_url: str,
    baseline_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
    auth_token: Optional[str] = None
) -> Dict[str, List[Dict]]:
    """
    Run comparison between baseline and MedGuard
    
    Args:
        test_cases: List of test cases with 'prompt' and optional 'expected_phi', 'is_attack'
        medguard_url: MedGuard API URL
        baseline_model_id: Bedrock model ID for baseline
        auth_token: Optional auth token for MedGuard
        
    Returns:
        Dict with 'baseline' and 'medguard' keys, each containing list of results
    """
    baseline_eval = BaselineEvaluator(baseline_model_id)
    medguard_eval = MedGuardEvaluator(medguard_url, auth_token)
    
    baseline_results = []
    medguard_results = []
    
    print(f"Running {len(test_cases)} test cases...")
    
    for i, test_case in enumerate(test_cases, 1):
        prompt = test_case.get("prompt", "")
        print(f"  [{i}/{len(test_cases)}] Testing: {prompt[:50]}...")
        
        # Baseline
        baseline_result = baseline_eval.invoke_direct(prompt)
        baseline_results.append(baseline_result)
        
        # MedGuard
        medguard_result = medguard_eval.invoke_medguard(prompt)
        medguard_results.append(medguard_result)
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
    
    return {
        "baseline": baseline_results,
        "medguard": medguard_results
    }
