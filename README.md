
# Readme

## Nirav Raje - Changes Made in the Original Codebase

- In LambdaScheduler.py, added eviction policies by setting `self.eviction_policy` in the constructor of LambdaScheduler. [[Link]](https://github.com/niravraje/faas-container-eviction/blob/c9cee4fd19919d5906743eb4bbab841b605d13fd/code/sim/LambdaScheduler.py#L33)
- In LambdaScheduler.py in the runInvocation() method, added the code to increment frequency on invocation for LFU-based policies, add to LRU cache for the LRU policy, priority calculation for DUAL_GREEDY approach. [[Link]](https://github.com/niravraje/faas-container-eviction/blob/c9cee4fd19919d5906743eb4bbab841b605d13fd/code/sim/LambdaScheduler.py#L520)
- In Container.py, added `invoke_freq`, `init_time` and `priority` for the Container object. [[Link]](https://github.com/niravraje/faas-container-eviction/blob/c9cee4fd19919d5906743eb4bbab841b605d13fd/code/sim/Container.py#L7)
  ```
  class Container:
    
    state = "COLD"
    
    def __init__(self, lamdata: LambdaData):
        self.metadata = lamdata
        self.invoke_freq = 1
        self.priority = 0
        self.init_time = lamdata.run_time - lamdata.warm_time
  ```
- Below the RandomEvictionPicker function, there is a list of functions added as per the `self.eviction_policy` set containing all policy functions. [[Link]](https://github.com/niravraje/faas-container-eviction/blob/c9cee4fd19919d5906743eb4bbab841b605d13fd/code/sim/LambdaScheduler.py#L191)
- The example scripts `run_all_20.sh`, `run_all_50.sh`, `run_all_100.sh` make it convenient to run a, b, and c traces for 20, 50 and 100 functions together.

## Overall design. 

`code/ParallelRunner.py` runs multiple instances of `LambdaScheduler.py`, each of which is is a self-contained simulation.
The simulation uses `Container.py` and `LambdaData.py` as data classes to track goings-on inside the simulation.

## Input. Format. LambdaData fields: fn:kind, ... 

Inputs to the simulator are a series of functions, and a trace of their invocations over a 24 hour period.
This second part is a simple list of `LambdaData` and float time that is iterated over.
You shouldn't need to examine these pickle files directly, but you can create custom traces for debugging using the exaples in `./code/support/TraceGen.py`.

## How to Run Simulation

There are many example scripts in `code/` for examples on how to run the simulator.
They run a specific trace we have supplied at a number of different memory levels to show how well the policy performed.
Results are then plotted for you and stored into `code/figs`.

### Debug

Set up debugging at the very bottom of `LambdaScheduler`, with a pickle trace file or a custom trace from `TraceGen.py`.
Running the `LambdaScheduler.py` file will run this one trace at a specific memory size, and you can then debug it any way you wish.

### Each invocation handled (run_invocation)

- Eviction API: Which function, args, 
  - `cache_miss` - creates a new `Container` to run a function that was not pre-warmed, may evict non-running containers if necessary
  - `Eviction` - called by `cache_miss` if not enough memory exists. Calls the custom eviction function `EvictionFunc` to get a list of `Container`s to evict and removes them from the `ContainerPool`
  - `EvictionFunc` - a function reference set in the constructor of `LambdaScheduler` that executes a custom eviction function based on `eviction_policy`

### Objects
  - LambdaData - The information about a function: unique name, memory usage, and runtime. **There are in the trace pickle file, so do not edit this class**
  - Container - Representing a function in memory
    - c.metadata - a `LambdaData` object withe the function information

### Data structures:
 - `RunningC` - A dictionary of `Container` to a tuple holding `(launch_time, finish_time)`, holding all those functions that are currently running
 - `ContainerPool` - All the `Container` objects active in the system, both running and warm

### Important Functions
  - `runInvocation` - the entrypoint for the scheduler
  - `cleanup_finished` - removes those containers from `RunningC` that have finished running. Called in `runInvocation` before anything else is done
  - `RemoveFromPool` - Remove a `Container` from `ContainerPool`. **must call this function to ensure bookkeeping is correct**
  - `AddToPool` - Add a `Container` to `ContainerPool`. **must call this function to ensure bookkeeping is correct**

### Useful features
  - `mem_capacity` - total memory the server has for functions
  - `mem_size` - the amount of memory being used by functions
  - `eviction_policy` - The eviction policy being used, a string
  - `evdict` - Accounting of the number of times each function has been evicted
  - `capacity_misses` - functions dropped due to insufficient resources

## Suggested places to make changes

`RandomEvictionPicker`. 
You will need to provide a custom eviction picker function, and in the constructor assign it to `EvictionFunc`.
You should also give a `policy` to go along with it, making it easy to differentiate the `RAND` policy from your new policy.


`runInvocation`.
This function will allow you to track each request on arrival, know if invocation was cold or warm, etc.
If you're looking to do prediction or general bookkeeping on each request, do it here. 

