# Nova SDK DSPy Compatibility Issue - Root Cause Analysis

## **Issue Summary**
The Nova Prompt Optimizer SDK has a **method signature incompatibility** with the DSPy library it depends on, causing optimization failures with `TypeError` exceptions.

## **Root Cause**
**API Contract Mismatch** between Nova SDK and DSPy library:

### **Nova SDK Implementation**
**File**: `src/amzn_nova_prompt_optimizer/core/optimizers/nova_prompt_optimizer/nova_grounded_proposer.py`

**Method**: `propose_instructions_for_program()` expects **6 parameters**:
```python
def propose_instructions_for_program(
    self, trainset, program, demo_candidates, trial_logs, N, T  # T is required
):
```

**Internal Call**: Nova SDK passes `T` parameter to parent class:
```python
self.propose_instruction_for_predictor(
    program=program,
    predictor=predictor,
    pred_i=pred_i,
    T=T,  # ← This parameter causes the error
    demo_candidates=demo_candidates,
    # ... other params
)
```

### **DSPy Library Expectation**
**File**: `dspy/teleprompt/mipro_optimizer_v2.py`

**Calling Code**: DSPy only provides **5 parameters** (missing `T`):
```python
instruction_candidates = proposer.propose_instructions_for_program(
    trainset=trainset,
    program=program,
    demo_candidates=demo_candidates,
    N=self.num_instruct_candidates,
    trial_logs={},
    # Missing: T parameter
)
```

**Parent Method**: `GroundedProposer.propose_instruction_for_predictor()` **does not accept** `T` parameter.

## **Error Manifestation**
1. **First Error**: `NovaGroundedProposer.propose_instructions_for_program() missing 1 required positional argument: 'T'`
2. **Second Error**: `GroundedProposer.propose_instruction_for_predictor() got an unexpected keyword argument 'T'`

## **Detailed Error Traces**

### Error 1: Missing T Parameter
```
TypeError: NovaGroundedProposer.propose_instructions_for_program() missing 1 required positional argument: 'T'
```

**Call Stack**:
```
dspy/teleprompt/mipro_optimizer_v2.py:407
→ proposer.propose_instructions_for_program(trainset, program, demo_candidates, N, trial_logs)
→ NovaGroundedProposer.propose_instructions_for_program() expects T parameter
```

### Error 2: Unexpected T Parameter
```
TypeError: GroundedProposer.propose_instruction_for_predictor() got an unexpected keyword argument 'T'
```

**Call Stack**:
```
nova_grounded_proposer.py:75
→ self.propose_instruction_for_predictor(T=T, ...)
→ Parent DSPy class doesn't accept T parameter
```

## **Impact**
- **All optimization operations fail** when using Nova SDK with current DSPy version
- **MIPROv2 optimizer cannot complete** instruction proposal phase
- **No workaround available** without code modification
- **Blocks core functionality** of the Nova Prompt Optimizer

## **Recommended Fixes**

### **Option 1: Make T Parameter Optional (Recommended)**
**File**: `src/amzn_nova_prompt_optimizer/core/optimizers/nova_prompt_optimizer/nova_grounded_proposer.py`

```python
def propose_instructions_for_program(
    self, trainset, program, demo_candidates, trial_logs, N, T=None
):
    if T is None:
        T = N  # Use N as default, or len(trainset), or other appropriate default
    # ... rest of method
```

### **Option 2: Remove T from Internal Calls**
**File**: `src/amzn_nova_prompt_optimizer/core/optimizers/nova_prompt_optimizer/nova_grounded_proposer.py`

```python
# Remove T=T from this call:
self.propose_instruction_for_predictor(
    program=program,
    predictor=predictor,
    pred_i=pred_i,
    # T=T,  # ← Remove this line
    demo_candidates=demo_candidates,
    demo_set_i=demo_set_i,
    trial_logs=trial_logs,
    tip=selected_tip,
)
```

### **Option 3: Update DSPy Integration**
Update the MIPROv2 optimizer to provide the `T` parameter when calling Nova methods.

## **Temporary Workaround Applied**
A frontend monkey patch has been applied in `sdk_worker.py` to handle both issues:

```python
# Patch 1: Handle missing T parameter
def patched_propose_instructions_for_program(self, trainset, program, demo_candidates, trial_logs, N, T=None):
    if T is None:
        T = N
    return original_propose_method(self, trainset, program, demo_candidates, trial_logs, N, T)

# Patch 2: Filter out unexpected T parameter
def patched_propose_instruction_for_predictor(self, *args, **kwargs):
    kwargs_filtered = {k: v for k, v in kwargs.items() if k != 'T'}
    return original_propose_instruction_method(self, *args, **kwargs_filtered)
```

## **Environment Details**
- **Nova SDK Version**: Latest from repository
- **DSPy Version**: Current version in environment
- **Python Version**: 3.12
- **Error First Observed**: After recent git pull (September 10, 2025)

## **Urgency**
**High** - This breaks core optimization functionality and prevents users from using the Nova SDK's primary feature.

## **Next Steps**
1. **Immediate**: Apply Option 1 (make T parameter optional) to restore functionality
2. **Long-term**: Review API contracts between Nova SDK and DSPy to prevent future incompatibilities
3. **Testing**: Ensure fix works with all supported DSPy versions
4. **Documentation**: Update any documentation that references the T parameter

---

**Report Generated**: September 10, 2025  
**Reported By**: Frontend Integration Team  
**Status**: Temporary workaround applied, permanent fix needed
