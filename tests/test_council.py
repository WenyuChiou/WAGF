import pytest
from unittest.mock import MagicMock
from validators.council import CouncilValidator
from broker.interfaces.skill_types import ValidationResult

def test_unanimous_council():
    v1 = MagicMock()
    v1.validate.return_value = [ValidationResult(valid=True, validator_name="v1", errors=[])]
    
    v2 = MagicMock()
    v2.validate.return_value = [ValidationResult(valid=False, validator_name="v2", errors=["Rejected by v2"])]
    
    council = CouncilValidator(validators=[v1, v2], consensus_mode="UNANIMOUS")
    results = council.validate(MagicMock(), {}, MagicMock())
    
    # UNANIMOUS returns everything, so it should include the error
    assert any(not r.valid for r in results)
    assert len(results) == 2

def test_majority_council_pass():
    v1 = MagicMock()
    v1.validate.return_value = [ValidationResult(valid=True, validator_name="v1", errors=[])]
    
    v2 = MagicMock()
    v2.validate.return_value = [ValidationResult(valid=True, validator_name="v2", errors=[])]
    
    v3 = MagicMock()
    v3.validate.return_value = [ValidationResult(valid=False, validator_name="v3", errors=["Rejected by v3"])]
    
    council = CouncilValidator(validators=[v1, v2, v3], consensus_mode="MAJORITY")
    results = council.validate(MagicMock(), {}, MagicMock())
    
    # 2/3 passed, so MAJORITY should approve (return no errors)
    assert all(r.valid for r in results)
    # It should only return the valid results
    assert len(results) == 2

def test_majority_council_fail():
    v1 = MagicMock()
    v1.validate.return_value = [ValidationResult(valid=True, validator_name="v1", errors=[])]
    
    v2 = MagicMock()
    v2.validate.return_value = [ValidationResult(valid=False, validator_name="v2", errors=["Error 2"])]
    
    v3 = MagicMock()
    v3.validate.return_value = [ValidationResult(valid=False, validator_name="v3", errors=["Error 3"])]
    
    council = CouncilValidator(validators=[v1, v2, v3], consensus_mode="MAJORITY")
    results = council.validate(MagicMock(), {}, MagicMock())
    
    # 1/3 passed, so MAJORITY should reject (return only errors)
    assert all(not r.valid for r in results)
    assert len(results) == 2
    assert "Error 2" in results[0].errors[0]
