#!/usr/bin/env python3
"""
Comprehensive PHI Redaction Test Suite
Tests MedGuard with real clinical note examples
"""

import json
import requests
import sys
from typing import Dict, List, Tuple

API_URL = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/v1/chat"

# Real clinical note examples with various PHI types
CLINICAL_NOTES = [
    {
        "name": "Emergency Department Note",
        "note": """
PATIENT: John Smith
MRN: 12345678
DOB: 01/15/1985
SSN: 555-12-3456
Phone: (617) 555-1234
Email: john.smith@email.com
Address: 123 Main St, Boston, MA 02115

CHIEF COMPLAINT: Chest pain

HISTORY OF PRESENT ILLNESS:
45-year-old male presents with acute onset chest pain that started 2 hours ago.
Patient reports the pain is substernal, radiating to left arm. Associated with
shortness of breath and diaphoresis.

ASSESSMENT AND PLAN:
1. Chest pain - likely cardiac etiology
   - EKG shows ST elevation in leads II, III, aVF
   - Troponin elevated at 2.5
   - Plan: Cardiac catheterization, start on aspirin and clopidogrel

2. Hypertension
   - Continue current medications
   - Follow up with primary care physician Dr. Sarah Johnson (phone: 617-555-5678)
""",
        "expected_phi": {
            "NAME": 2,  # John Smith, Sarah Johnson
            "PHONE": 2,  # (617) 555-1234, 617-555-5678
            "EMAIL": 1,  # john.smith@email.com
            "DATE": 1,   # 01/15/1985
            "SSN": 1,    # 555-12-3456
            "MRN": 1,    # 12345678
            "ADDRESS": 1 # 123 Main St...
        }
    },
    {
        "name": "Discharge Summary",
        "note": """
DISCHARGE SUMMARY

Patient Name: Maria Rodriguez
Medical Record Number: 98765432
Date of Birth: 03/22/1978
Contact: maria.rodriguez@hospital.com, (415) 555-9876

ADMISSION DATE: 12/15/2025
DISCHARGE DATE: 12/18/2025

DIAGNOSIS:
- Community-acquired pneumonia
- Type 2 Diabetes Mellitus

TREATMENT:
Patient was treated with ceftriaxone and azithromycin. Blood glucose
monitored and insulin adjusted. Discharged on oral antibiotics.

FOLLOW-UP:
Patient to follow up with Dr. Michael Chen at 555-123-4567 within 7 days.
""",
        "expected_phi": {
            "NAME": 2,  # Maria Rodriguez, Michael Chen
            "PHONE": 2,  # (415) 555-9876, 555-123-4567
            "EMAIL": 1,  # maria.rodriguez@hospital.com
            "DATE": 3,   # 03/22/1978, 12/15/2025, 12/18/2025
            "MRN": 1     # 98765432
        }
    },
    {
        "name": "Progress Note",
        "note": """
PROGRESS NOTE

Date: 01/03/2026
Attending: Dr. Emily Watson, MD
Resident: Dr. James Park, MD

Patient: Robert Williams (MRN: 45678901)
DOB: 11/05/1965
Phone: 212-555-3456
Email: r.williams@email.com

SUBJECTIVE:
Patient reports improvement in symptoms. No new complaints.

OBJECTIVE:
Vital signs stable. Physical exam unremarkable.

ASSESSMENT:
Patient doing well, ready for discharge.

PLAN:
Continue current medications. Follow up in clinic.
""",
        "expected_phi": {
            "NAME": 3,  # Robert Williams, Emily Watson, James Park
            "PHONE": 1,  # 212-555-3456
            "EMAIL": 1,  # r.williams@email.com
            "DATE": 2,   # 01/03/2026, 11/05/1965
            "MRN": 1     # 45678901
        }
    }
]

def test_phi_redaction(note_data: Dict) -> Tuple[bool, Dict]:
    """Test PHI redaction for a clinical note"""
    print(f"\n{'='*60}")
    print(f"Testing: {note_data['name']}")
    print(f"{'='*60}")
    
    payload = {
        "user_id": "test_phi_user",
        "role": "resident",
        "prompt": f"Summarize this clinical note:\n{note_data['note']}"
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # Check redaction summary
        redaction_summary = result.get("redaction_summary", {})
        expected = note_data["expected_phi"]
        
        print(f"\nExpected PHI types: {expected}")
        print(f"Detected PHI types: {redaction_summary}")
        
        # Calculate detection rate
        detected_count = sum(redaction_summary.values())
        expected_count = sum(expected.values())
        detection_rate = (detected_count / expected_count * 100) if expected_count > 0 else 0
        
        print(f"\nDetection Rate: {detection_rate:.1f}% ({detected_count}/{expected_count})")
        
        # Check for PHI in output
        output_has_phi = result.get("safety_flags", {}).get("phi_detected_in_output", False)
        if output_has_phi:
            print("⚠️  WARNING: PHI detected in output!")
        else:
            print("✅ No PHI detected in output")
        
        # Check response quality
        response_text = result.get("response", "")
        if len(response_text) > 50:
            print("✅ Response generated successfully")
        else:
            print("⚠️  Response seems too short")
        
        return True, {
            "detection_rate": detection_rate,
            "output_has_phi": output_has_phi,
            "redaction_summary": redaction_summary,
            "request_id": result.get("request_id")
        }
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, {"error": str(e)}


def run_all_tests():
    """Run all PHI redaction tests"""
    print("="*60)
    print("PHI REDACTION TEST SUITE")
    print("="*60)
    
    results = []
    for note_data in CLINICAL_NOTES:
        success, result = test_phi_redaction(note_data)
        results.append({
            "test": note_data["name"],
            "success": success,
            **result
        })
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    successful = sum(1 for r in results if r.get("success"))
    avg_detection_rate = sum(r.get("detection_rate", 0) for r in results) / len(results) if results else 0
    
    print(f"Tests Passed: {successful}/{len(results)}")
    print(f"Average Detection Rate: {avg_detection_rate:.1f}%")
    
    phi_in_output = sum(1 for r in results if r.get("output_has_phi"))
    if phi_in_output > 0:
        print(f"⚠️  WARNING: {phi_in_output} test(s) had PHI in output")
    else:
        print("✅ No PHI leaked to output in any test")
    
    return results


if __name__ == "__main__":
    results = run_all_tests()
    sys.exit(0 if all(r.get("success") for r in results) else 1)
