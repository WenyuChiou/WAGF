"""
Flood Adaptation Validators
PMT 一致性驗證器和洪水反應驗證器
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from validators.base import BaseValidator
from broker.legacy.types import DecisionRequest, ValidationResult


class PMTConsistencyValidator(BaseValidator):
    """
    PMT 一致性驗證器 (Rule 4)
    
    規則: 高威脅 + 高效能信念 + "Do Nothing" = 不一致
    """
    
    name = "PMTConsistencyValidator"
    
    def __init__(self):
        # 高威脅關鍵詞
        self.high_threat_keywords = [
            "worried", "concerned", "scared", "at risk", 
            "dangerous", "vulnerable", "threatened", "fear"
        ]
        
        # 高效能關鍵詞
        self.high_efficacy_keywords = [
            "can protect", "effective", "would help", "prevent damage",
            "reduce risk", "worthwhile", "beneficial", "useful"
        ]
    
    def validate(self, request: DecisionRequest, context: dict) -> ValidationResult:
        errors = []
        
        threat = request.reasoning.get("threat", "").lower()
        coping = request.reasoning.get("coping", "").lower()
        decision = request.action_code
        
        # 檢查是否為 "Do Nothing"
        is_elevated = context.get("is_elevated", False)
        is_do_nothing = (decision == "4") or (is_elevated and decision == "3")
        
        # 檢查高威脅
        has_high_threat = any(kw in threat for kw in self.high_threat_keywords)
        
        # 檢查高效能
        has_high_efficacy = any(kw in coping for kw in self.high_efficacy_keywords)
        
        # PMT 不一致: 高威脅 + 高效能 + 不行動
        if has_high_threat and has_high_efficacy and is_do_nothing:
            errors.append(
                "PMT inconsistency: High threat perception and high coping efficacy "
                "but chose Do Nothing. This contradicts Protection Motivation Theory."
            )
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            metadata={
                "high_threat_detected": has_high_threat,
                "high_efficacy_detected": has_high_efficacy,
                "is_do_nothing": is_do_nothing
            }
        )


class FloodResponseValidator(BaseValidator):
    """
    洪水反應驗證器 (Rule 5)
    
    規則: 洪水發生 + 聲稱安全 = 不一致
    """
    
    name = "FloodResponseValidator"
    
    def __init__(self):
        self.safe_claim_keywords = [
            "feel safe", "not worried", "no concern", 
            "protected", "secure", "safe from"
        ]
    
    def validate(self, request: DecisionRequest, context: dict) -> ValidationResult:
        errors = []
        
        threat = request.reasoning.get("threat", "").lower()
        flood_status = context.get("flood_status", "")
        
        # 檢查是否發生洪水
        flood_occurred = flood_status and "flood occurred" in flood_status.lower()
        
        if flood_occurred:
            # 檢查是否聲稱安全
            claims_safe = any(kw in threat for kw in self.safe_claim_keywords)
            
            if claims_safe:
                errors.append(
                    "Flood Response inconsistency: A flood occurred this year "
                    "but the agent claims to feel safe. This is cognitively inconsistent."
                )
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            metadata={
                "flood_occurred": flood_occurred,
                "claims_safe": any(kw in threat for kw in self.safe_claim_keywords) if flood_occurred else False
            }
        )


class UnbiasedValidator(BaseValidator):
    """
    無偏驗證器 (整合所有規則)
    對齊現有實驗的 UnbiasedValidator
    """
    
    name = "UnbiasedValidator"
    
    def validate(self, request: DecisionRequest, context: dict) -> ValidationResult:
        errors = []
        
        threat = request.reasoning.get("threat", "").lower()
        coping = request.reasoning.get("coping", "").lower()
        decision = request.action_code
        
        # Rule 1: Low threat + Relocate
        low_threat = ["not worried", "safe", "no risk", "unlikely", "minimal"]
        if any(kw in threat for kw in low_threat) and decision == "4":
            errors.append("Claims low threat but chose Relocate")
        
        # Rule 2: Cannot afford + expensive
        cannot_afford = ["cannot afford", "can't afford", "too expensive"]
        if any(kw in coping for kw in cannot_afford) and decision in ["2", "3", "4"]:
            errors.append("Claims cannot afford but chose expensive option")
        
        # Rule 3: Already have + buy again
        if "already have insurance" in coping and decision == "1":
            errors.append("Claims already has insurance but chose to buy")
        
        # Delegate to specialized validators
        pmt_validator = PMTConsistencyValidator()
        pmt_result = pmt_validator.validate(request, context)
        errors.extend(pmt_result.errors)
        
        flood_validator = FloodResponseValidator()
        flood_result = flood_validator.validate(request, context)
        errors.extend(flood_result.errors)
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)
