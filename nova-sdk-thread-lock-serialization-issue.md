# Nova SDK Thread Lock Serialization Issue - Root Cause Analysis

## **Issue Summary**
The Nova Prompt Optimizer SDK fails during optimization due to **thread lock serialization errors** when DSPy attempts to create deep copies of language model objects containing non-serializable threading primitives.

## **Root Cause**
**Serialization Design Flaw** in Nova SDK's integration with boto3/botocore clients that contain thread locks.

### **Error Details**
**Error Message**: `TypeError: cannot pickle '_thread.lock' object`

**Call Stack**:
```
dspy/clients/base_lm.py:122 → copy.deepcopy(self)
↓
Python's copy.deepcopy() attempts to serialize all object attributes
↓
Encounters threading.Lock objects in boto3/botocore clients
↓
Python's pickle module cannot serialize thread locks
↓
TypeError: cannot pickle '_thread.lock' object
```

### **Technical Explanation**

#### **Why DSPy Needs Deep Copies**
DSPy's MIPROv2 optimizer creates copies of language models during instruction proposal:

```python
# dspy/propose/grounded_proposer.py:417
rollout_lm = self.prompt_model.copy()

# dspy/clients/base_lm.py:122  
def copy(self):
    new_instance = copy.deepcopy(self)  # ← Fails here
    return new_instance
```

#### **Why Nova SDK Objects Contain Thread Locks**
The Nova SDK uses **BedrockConverseHandler** which contains:
1. **boto3 Bedrock client** - Has internal thread locks for connection pooling
2. **botocore session objects** - Contains threading primitives for thread safety
3. **Rate limiting mechanisms** - May use threading.Lock for synchronization

#### **Why Thread Locks Cannot Be Serialized**
- **Thread locks are OS-level primitives** tied to specific processes/threads
- **Python's pickle module** cannot serialize active threading objects
- **Deep copy relies on pickle** for complex object serialization
- **Cross-process/thread boundaries** make locks meaningless

## **Affected Components**

### **Primary Component**
**File**: `src/amzn_nova_prompt_optimizer/core/inference/bedrock_converse.py`
**Class**: `BedrockConverseHandler`

**Problem**: Contains boto3 clients with non-serializable thread locks

### **Integration Point**
**File**: `dspy/clients/base_lm.py`
**Method**: `copy()` - Uses `copy.deepcopy()` which fails on thread locks

### **Trigger Condition**
**File**: `dspy/propose/grounded_proposer.py`
**Method**: `propose_instruction_for_predictor()` - Calls `self.prompt_model.copy()`

## **Impact Analysis**

### **Immediate Impact**
- **All optimization operations fail** during instruction proposal phase
- **MIPROv2 optimizer cannot create model copies** needed for rollouts
- **No workaround available** without code modification

### **Broader Impact**
- **Any DSPy integration** that needs to copy Nova SDK language models will fail
- **Parallel processing scenarios** where model copies are needed will break
- **Distributed optimization** becomes impossible

### **Environments Affected**
- ✅ **Frontend optimization** (with patches)
- ❌ **Jupyter notebooks** (without patches)
- ❌ **CLI usage** (without patches)
- ❌ **Any direct SDK usage** with DSPy

## **Error Reproduction**

### **Minimal Reproduction Case**
```python
import copy
from amzn_nova_prompt_optimizer.core.inference.bedrock_converse import BedrockConverseHandler

# Create handler (contains boto3 client with thread locks)
handler = BedrockConverseHandler(region_name="us-east-1")

# This will fail
try:
    copy.deepcopy(handler)
except TypeError as e:
    print(f"Error: {e}")  # "cannot pickle '_thread.lock' object"
```

### **Full Optimization Failure**
```python
from amzn_nova_prompt_optimizer.core.optimizers import NovaPromptOptimizer

# Setup optimizer with prompt, dataset, metric adapters
optimizer = NovaPromptOptimizer(...)

# This will fail during instruction proposal
result = optimizer.optimize(mode="pro")  # ← Crashes with thread lock error
```

## **Root Cause Categories**

### **1. Design Issue**
- **BedrockConverseHandler lacks serialization support**
- **No custom `__deepcopy__` method** implemented
- **No `__getstate__`/`__setstate__` methods** for pickle support

### **2. Integration Issue**
- **DSPy assumes all language models are serializable**
- **Nova SDK doesn't implement DSPy's serialization expectations**
- **No interface contract** for serialization requirements

### **3. Threading Architecture Issue**
- **boto3 clients use thread locks internally**
- **Nova SDK exposes these non-serializable objects**
- **No abstraction layer** to hide threading primitives

## **Recommended Fixes**

### **Option 1: Implement Custom Serialization (Recommended)**
**File**: `src/amzn_nova_prompt_optimizer/core/inference/bedrock_converse.py`

```python
class BedrockConverseHandler:
    def __deepcopy__(self, memo):
        # Create new instance instead of copying
        return BedrockConverseHandler(
            region_name=self.region_name,
            rate_limit=self.rate_limit
        )
    
    def __getstate__(self):
        # Return serializable state
        return {
            'region_name': self.region_name,
            'rate_limit': self.rate_limit
        }
    
    def __setstate__(self, state):
        # Reconstruct from serializable state
        self.__init__(
            region_name=state['region_name'],
            rate_limit=state['rate_limit']
        )
```

### **Option 2: Implement Copy Method**
```python
class BedrockConverseHandler:
    def copy(self):
        # Create new instance for copying
        return BedrockConverseHandler(
            region_name=self.region_name,
            rate_limit=self.rate_limit
        )
```

### **Option 3: Lazy Client Initialization**
```python
class BedrockConverseHandler:
    def __init__(self, region_name, rate_limit):
        self.region_name = region_name
        self.rate_limit = rate_limit
        self._client = None  # Don't create client until needed
    
    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client('bedrock-runtime', region_name=self.region_name)
        return self._client
```

## **Temporary Workaround Applied**
A frontend monkey patch intercepts `copy.deepcopy()` calls and handles thread lock errors:

```python
def patched_deepcopy(obj, memo=None):
    try:
        return original_deepcopy(obj, memo)
    except TypeError as e:
        if "cannot pickle '_thread.lock' object" in str(e):
            # Create new instance instead of deep copying
            # Handle thread locks by creating new locks
            # Fall back gracefully for unsupported objects
```

## **Testing Requirements**

### **Unit Tests Needed**
1. **Serialization test**: `copy.deepcopy(BedrockConverseHandler())`
2. **DSPy integration test**: Model copying in optimization context
3. **Thread safety test**: Ensure new instances work correctly

### **Integration Tests Needed**
1. **Full optimization test**: End-to-end optimization with model copying
2. **Parallel processing test**: Multiple concurrent optimizations
3. **Cross-environment test**: Notebook, CLI, and frontend usage

## **Related Issues**
- **T Parameter Issue**: Separate API compatibility problem
- **DSPy Version Compatibility**: May affect serialization requirements
- **boto3 Version Dependencies**: Thread lock implementation may vary

## **Priority Assessment**
**Critical** - This prevents core optimization functionality and affects all environments where model copying is needed.

## **Recommended Timeline**
1. **Immediate (1-2 days)**: Implement Option 1 (custom serialization)
2. **Short-term (1 week)**: Add comprehensive tests
3. **Long-term (1 month)**: Review all SDK components for serialization compatibility

---

**Report Generated**: September 11, 2025  
**Reported By**: Frontend Integration Team  
**Status**: Temporary workaround applied, permanent fix needed  
**Severity**: Critical - Blocks core functionality
