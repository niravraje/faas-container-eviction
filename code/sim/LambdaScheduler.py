import numpy as np
import random
from collections import defaultdict
from LambdaData import *
from Container import *
import os
from heapq import heappush, heappop

class LambdaScheduler:

    def __init__(self, policy:str="RAND", mem_capacity:int=32000, num_funcs:int=10, run:str="a", log_dir=""):
        fname = "{}-{}-{}-{}-".format(policy, num_funcs, mem_capacity, run)

        self.mem_capacity = mem_capacity
        self.mem_used = 0
        self.eviction_policy = policy

        self.wall_time = 0              # Current system time
        self.RunningC = dict()          # Container : (launch_time, launch_time+processing_time)
        self.ContainerPool = []         # simple list of `Container`s
        self.FunctionHistoryList = []   # list of tuplies (`LambdaData`, invocation_time)

        self.PerfLogFName = os.path.join(log_dir, fname+"performancelog.csv")
        self.PerformanceLog = open(self.PerfLogFName, "w")
        self.PerformanceLog.write("lambda,time,meta\n")

        self.evdict = defaultdict(int)
        self.capacity_misses = defaultdict(int)

        self.provider_overhead_base = 3000 # 3 seconds
        self.provider_overhead_pct = 0.2 # 20% of function runtime added to cold start

        # ---- Newly added data structures ----
        self.lru_cache = {}
        self.priority_min_heap = []

        if self.eviction_policy == "RAND":
          # Function to be called pick containers to evict
          self.EvictionFunc = self.RandomEvictionPicker

        elif self.eviction_policy == "CLOSEST_SIZE_LARGEST_KICK":
            self.EvictionFunc = self.evict_closest_else_kick_largest

        elif self.eviction_policy == "CLOSEST_SIZE_SMALLEST_KICK":
            self.EvictionFunc = self.evict_closest_else_kick_smallest
            
        elif self.eviction_policy == "LRU":
            self.EvictionFunc = self.evict_lru

        elif self.eviction_policy == "LFU_CLASSIC":
            self.EvictionFunc = self.evict_lfu_classic

        elif self.eviction_policy == "LFU_GROUP_CLOSEST":
            self.EvictionFunc = self.evict_lfu_group_closest

        elif self.eviction_policy == "LFU_GROUP_MAX_COLD_TIME":
            self.EvictionFunc = self.evict_lfu_group_maxcoldtime

        elif self.eviction_policy == "LFU_GROUP_MAX_INIT_TIME":
            self.EvictionFunc = self.evict_lfu_group_maxinittime

        elif self.eviction_policy == "LFUGROUP_MAXINITGROUP_CLOSEST":
            self.EvictionFunc = self.evict_lfu_group_maxinitgroup_closest

        elif self.eviction_policy == "LFUGROUP_CLOSESTGROUP_MAXINIT":
            self.EvictionFunc = self.evict_lfu_group_closestgroup_maxinit
        
        elif self.eviction_policy == "LFUGROUP_MAXINITGROUP_LARGEST":
            self.EvictionFunc = self.evict_lfu_group_maxinitgroup_largest

        elif self.eviction_policy == "DUAL_GREEDY_PRIORITY":
            self.EvictionFunc = self.evict_dual_greedy_priority_based

        else:
          raise NotImplementedError("Unkonwn eviction policy: {}".format(self.eviction_policy))

    ##############################################################

    def WritePerfLog(self, d:LambdaData, time, meta):
        msg = "{},{},{}\n".format(d.kind, time, meta)
        self.PerformanceLog.write(msg)

    ##############################################################

    def AssertMemory(self):
      """ Raise an exception if the memory assumptions of the simulation have been violated """
      used_mem = sum([c.metadata.mem_size for c in self.ContainerPool])
      if used_mem != self.mem_used:
        raise Exception("Container pool mem '{}' does not match tracked usage '{}'".format(used_mem, self.mem_used))
      if used_mem > self.mem_capacity:
        raise Exception("Container pool mem '{}' exceeds capacity '{}'".format(used_mem, self.mem_capacity))

    ##############################################################

    def ColdHitProcTime(self, d:LambdaData) -> float:
      """
      Total processing time for a cold hit on the given lambda
      """
      return self.provider_overhead_base + d.run_time + (self.provider_overhead_pct * d.run_time)

    ##############################################################

    def find_container(self, d: LambdaData):
        """ 
        Search through the containerpool for a non-running container with the sane metadata as `d`
        Return None if one cannot be found
        """
        if len(self.ContainerPool) == 0 :
            return None
        containers_for_the_lambda = [x for x in self.ContainerPool if (x.metadata == d and
                                                     x not in self.RunningC)]

        if containers_for_the_lambda == []:
            return None
        else:
            return containers_for_the_lambda[0]
        # Just return the first element.

    ##############################################################

    def container_clones(self, c: Container):
        """ Return all the conatienrs have the same function data as `c` """
        return [x for x in self.ContainerPool if x.metadata == c.metadata]

    ##############################################################

    def CheckFree(self, c):
      """
      Check
      """
      mem_size = c.metadata.mem_size
      return mem_size + self.mem_used <= self.mem_capacity

    ##############################################################

    def AddToPool(self, c: Container):
        """ Add contaienr to the ContainerPool, maintaining bookkeeping """
        mem_size = c.metadata.mem_size
        if mem_size + self.mem_used <= self.mem_capacity:
            #Have free space
            self.mem_used = self.mem_used + mem_size

            self.ContainerPool.append(c)
            return True
        else:
            # print ("Not enough space for memsize, used, capacity.", mem_size, self.mem_used, self.mem_capacity)
            return False

    ##############################################################

    def RemoveFromPool(self, c: Container):
      if c in self.RunningC:
        raise Exception("Cannot remove a running container")
      self.ContainerPool.remove(c)
      self.mem_used -= c.metadata.mem_size

    ############################################################

    def RandomEvictionPicker(self, to_free):
      """ 
      Return victim lists
      Simple eviction that randomly chooses from non-running containers
      """
      eviction_list = []
      # XXX Can't evict running containers!
      # Even with infinite concurrency, container will still exist in running_c
      available = [c for c in self.ContainerPool if c not in self.RunningC]

      while to_free > 0 and len(available) > 0:
        victim = random.choice(available)
        available.remove(victim)
        eviction_list.append(victim)
        to_free -= victim.metadata.mem_size

      return eviction_list


    # ----------- Helpers -----------

    def binary_search_closest(self, arr, key):
        start = 0
        end = len(arr) - 1
        while start < end:
            mid = start + (end - start) // 2
            if key > arr[mid].metadata.mem_size:
                start = mid + 1
            else:
                end = mid
        return end

    # -------- Custom policies -----------

    def evict_closest_else_kick_largest(self, to_free):
        """ Naive approach. Evict a container with a size closest to `to_free`.
        If `to_free` is greater than max mem size of largest container, then kick out largest container

        Sort the available list first and then perform binary search.
        This policy is not dependent on warm/cold run time of the function.
        """
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]
        available.sort(key=lambda c: c.metadata.mem_size)

        while to_free > 0 and len(available) > 0:
            victim_index = self.binary_search_closest(available, to_free)
            victim = available.pop(victim_index)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size

        return eviction_list

    def evict_closest_else_kick_smallest(self, to_free):
        """ Naive approach. Evict a container with a size closest to `to_free`.
        If `to_free` is greater than max mem size of largest container, then kick out smallest container

        Sort the available list first and then perform binary search.
        This policy is not dependent on warm/cold run time of the function.
        """
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]
        available.sort(key=lambda c: c.metadata.mem_size)

        while to_free > 0 and len(available) > 0:
            if to_free > available[-1].metadata.mem_size:
                victim_index = 0
            else:
                victim_index = self.binary_search_closest(available, to_free)
            victim = available.pop(victim_index)

            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size

        return eviction_list
    
    def evict_lru(self, to_free):
        """ Evict the least recently used/invoked container """
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        victim_index = 0
        cache_iterator = iter(self.lru_cache)

        while to_free > 0 and len(available) > 0:
            victim = next(cache_iterator)
            if victim not in available:
                continue

            available.remove(victim)
            del self.lru_cache[victim]
            cache_iterator = iter(self.lru_cache)

            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size

        return eviction_list

    def evict_lfu_classic(self, to_free):
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # Sort descendingly to allow pop in O(1)
        available.sort(key=lambda c: c.invoke_freq, reverse=True)

        while to_free > 0 and len(available) > 0:
            victim = available.pop() # O(1)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size

        return eviction_list

    def evict_lfu_group_closest(self, to_free):
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # Note: Sorting in ascending invoke_freq here, least invoked is at the start
        available.sort(key=lambda c: c.invoke_freq)
        group_size = int(0.1 * len(available)) if len(available) > 40 else 4

        while to_free > 0 and len(available) > 0:
            available_group = available[:group_size]
            # binary search to get closest memsize container
            victim_index = self.binary_search_closest(available_group, to_free)
            victim = available_group[victim_index]

            available.remove(victim)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size
        return eviction_list

    def evict_lfu_group_maxcoldtime(self, to_free):
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # Note: Sorting in ascending invoke_freq here, least invoked is at the start
        available.sort(key=lambda c: c.invoke_freq)
        group_size = int(0.1 * len(available)) if len(available) > 40 else 4

        while to_free > 0 and len(available) > 0:
            available_group = available[:group_size]

            # ASCENDING sort by cold start times
            available_group.sort(key=lambda c: c.metadata.run_time)

            victim = available_group.pop()
            available.remove(victim)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size

        return eviction_list
    
    def evict_lfu_group_maxinittime(self, to_free):
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # Note: Sorting in ascending invoke_freq here, least invoked is at the start
        available.sort(key=lambda c: c.invoke_freq)

        group_size = int(0.1 * len(available)) if len(available) > 40 else 4

        while to_free > 0 and len(available) > 0:
            lfu_group = available[:group_size]

            # ASCENDING sort by initialization time (environment setup time)
            lfu_group.sort(key=lambda c: c.metadata.run_time - c.metadata.warm_time)

            # choose container with least init/setup time as victim
            victim = lfu_group[0]
            
            available.remove(victim)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size

        return eviction_list

    def evict_lfu_group_maxinitgroup_closest(self, to_free):
        """
        Approach:
            Double-sorted-group approach:
            - First find "n" LFU containers.
            - Sort the lfu_group by initialization time.
            - From the sorted lfu_group, find "m" (where m < n) containers with the least initialization time
            - This is our maxinit_group. Sort the maxinit_group by mem_size.
            - In the sorted maxinit_group, perform Binary Search to find closest mem_size container.
            - This container is chosen as the victim.
        """
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # Note: Sorting in ascending invoke_freq here, least invoked is at the start
        available.sort(key=lambda c: c.invoke_freq)

        lfu_group_size = int(0.1 * len(available)) if len(available) > 40 else 4
        maxinit_group_size = int(0.05 * len(available)) if len(available) > 40 else 2

        while to_free > 0 and len(available) > 0:
            lfu_group = available[:lfu_group_size]

            # ASCENDING sort by initialization time
            lfu_group.sort(key=lambda c: c.metadata.run_time - c.metadata.warm_time)

            maxinit_group = lfu_group[:maxinit_group_size]

            # ASCENDING sort by mem_size
            maxinit_group.sort(key=lambda c: c.metadata.mem_size)

            # Binary search for the closest sized container from this sorted sub-group
            victim_index = self.binary_search_closest(maxinit_group, to_free)
            victim = maxinit_group[victim_index]
            # victim = maxinit_group[-1] # get largest container

            available.remove(victim)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size
        
        return eviction_list


    def find_closest_group(self, arr, key, group_size):
        if group_size >= len(arr):
            return arr
        
        victim_group_start = self.binary_search_closest(arr, key)

        victim_group_start = min(victim_group_start, len(arr) - group_size)

        return arr[victim_group_start:]
        

    def evict_lfu_group_closestgroup_maxinit(self, to_free):
        """
        """
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # Note: Sorting in ascending invoke_freq here, least invoked is at the start
        available.sort(key=lambda c: c.invoke_freq)
        lfu_group_size = int(0.1 * len(available)) if len(available) > 60 else 6
        closest_group_size = int(0.05 * len(available)) if len(available) > 60 else 3
        while to_free > 0 and len(available) > 0:
            lfu_group = available[:lfu_group_size]

            # ASCENDING sort by mem_size
            lfu_group.sort(key=lambda c: c.metadata.mem_size)

            closest_group = self.find_closest_group(lfu_group, to_free, closest_group_size)

            # ASCENDING sort by initialization time
            closest_group.sort(key=lambda c: c.metadata.run_time - c.metadata.warm_time)

            # Choose container with least init time from closest group as victim
            victim = closest_group[0]

            available.remove(victim)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size
        
        return eviction_list    

    def evict_lfu_group_maxinitgroup_largest(self, to_free):
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # Note: Sorting in ascending invoke_freq here, least invoked is at the start
        available.sort(key=lambda c: c.invoke_freq)

        lfu_group_size = int(0.1 * len(available)) if len(available) > 40 else 4
        maxinit_group_size = int(0.05 * len(available)) if len(available) > 40 else 2

        while to_free > 0 and len(available) > 0:
            lfu_group = available[:lfu_group_size]

            # ASCENDING sort by initialization time
            lfu_group.sort(key=lambda c: c.metadata.run_time - c.metadata.warm_time)

            maxinit_group = lfu_group[:maxinit_group_size]

            # ASCENDING sort by mem_size
            maxinit_group.sort(key=lambda c: c.metadata.mem_size)

            victim = maxinit_group[-1] # get largest container

            available.remove(victim)
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size
        
        return eviction_list

    def evict_dual_greedy_priority_based(self, to_free):
        eviction_list = []
        available = [c for c in self.ContainerPool if c not in self.RunningC]

        # sort descending
        available.sort(key=lambda c: c.priority, reverse=True)

        # containers_to_put_back = []
        while to_free > 0 and len(available) > 0:
            victim = available.pop()
            eviction_list.append(victim)
            to_free -= victim.metadata.mem_size
        return eviction_list

    #############################################################

    def Eviction(self, d: LambdaData):
        """ Return a list of containers that have been evicted """
        if len(self.RunningC) == len(self.ContainerPool):
            # all containers busy
            return []

        eviction_list = self.EvictionFunc(to_free=d.mem_size)

        for v in eviction_list:
          self.RemoveFromPool(v)
          # self.mem_used -= v.metadata.mem_size
          k = v.metadata.kind
          self.evdict[k] += 1

        return eviction_list

    ##############################################################

    def cache_miss(self, d:LambdaData):
        """ 
        A cache miss for the function.
        Create a new Container that has been added to the Container Pool and return it
        Return None if one could not be created

        Evicts non-running containers in an attempt to make room
        """
        c = Container(d)

        if not self.CheckFree(c) : #due to space constraints
          evicted = self.Eviction(d) #Is a list. containers already terminated

        added = self.AddToPool(c)
        if not added:
          # unable to add a new container due to memory constraints
          return None

        return c

    ##############################################################

    def cleanup_finished(self):
        """ Go through running containers, remove those that have finished """
        t = self.wall_time
        finished = []
        for c in self.RunningC:
            (start_t, fin_t) = self.RunningC[c]
            if t >= fin_t:
                finished.append(c)

        for c in finished:
            del self.RunningC[c]

        return len(finished)

    ##############################################################

    def runInvocation(self, d: LambdaData, t = 0):
        """ Entrypoint for the simulation """
        self.wall_time = t
        self.cleanup_finished()

        # print("container pool len:", len(self.ContainerPool))

        c = self.find_container(d)
        if c is None:
            #Launch a new container since we didnt find one for the metadata ...
            c = self.cache_miss(d)
            if c is None:
                # insufficient memory
                self.capacity_misses[d.kind] += 1
                return
            c.run()
            processing_time = self.ColdHitProcTime(d)
            self.RunningC[c] = (t, t+processing_time)
            self.WritePerfLog(d, t, "miss")
        else:
            c.run()
            processing_time = d.warm_time
            self.RunningC[c] = (t, t+processing_time)
            self.WritePerfLog(d, t, "hit")

            if self.eviction_policy == "LRU":
                # if hit, pop first to "move_to_front" later
                self.lru_cache.pop(c) # lru_cache is a dict, dict.pop() is like list.remove()


        if self.eviction_policy == "LRU":      
            self.lru_cache[c] = None

        c.invoke_freq += 1

        # For the dual-greedy approach given in the FaaSCache paper (cited in the report)
        if self.eviction_policy == "DUAL_GREEDY_PRIORITY":
            c.priority = self.wall_time + (c.init_time * c.invoke_freq / c.metadata.mem_size)

        self.FunctionHistoryList.append((d,t))
        self.AssertMemory()

    ##############################################################

    def miss_stats(self):
        """ Go through the performance log."""
        rdict = dict() #For each activation
        with open(self.PerfLogFName, "r") as f:
            line = f.readline() # throw away header
            for line in f:
                line = line.rstrip()
                d, ptime, evtype = line.split(",")
                k = d
                if k not in rdict:
                    mdict = dict()
                    mdict['misses'] = 0
                    mdict['hits'] = 0
                    rdict[k] = mdict

                if evtype == "miss":
                    rdict[k]['misses'] = rdict[k]['misses'] + 1
                elif evtype == "hit":
                    rdict[k]['hits'] = rdict[k]['hits'] + 1
                else:
                    pass

        #Also some kind of response time data?
        return rdict

    ##############################################################
    ##############################################################
    ##############################################################

if __name__ == "__main__":
    from pprint import pprint
    import pickle
    ls = LambdaScheduler(policy="RAND", mem_capacity=2048, num_funcs=20, run="b")

    pth = "../../traces/20-b.pckl"
    with open(pth, "r+b") as f:
        lambdas, input_trace = pickle.load(f)
    print(len(input_trace))

    for d, t in input_trace:
        ls.runInvocation(d, t)

    print("\n\nDONE\n")

    pprint(ls.evdict)
    pprint(ls.miss_stats())
    print("cap", ls.capacity_misses)

