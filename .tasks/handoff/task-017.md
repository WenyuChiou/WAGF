# Task-017: JOH Stress Testing

## Objective
Validate the "Robustness" of the framework by subjecting Gemma 3 and Llama 3 to four extreme scenarios (Appendix A).

## Scenarios
1. **ST-1 Panic Machine**: High Neuroticism + Cat 5 Warning. (Exp: Relocate rate increases?)
2. **ST-2 Optimistic Veteran**: 30-year quiet history. (Exp: Inaction rate increases?)
3. **ST-3 Memory Goldfish**: Broken context window. (Exp: Amnesia of Year 1 flood?)
4. **ST-4 Format Breaker**: Noisy injection. (Exp: Repair Yield?)

## Target Models
- **Gemma 3 4B** (Primary)
- **Llama 3.2 3B** (Secondary)
(DeepSeek/GPT-OSS excluded due to cost)

## Execution Plan
- [ ] Edit `run_stress_marathon.ps1` to exclude Large Models.
- [ ] Run `run_stress_marathon.ps1`.
- [ ] Run `analyze_stress.py`.
