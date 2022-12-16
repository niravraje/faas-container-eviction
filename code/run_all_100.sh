#!/bin/bash

trace_dir="../traces"
trace_output_dir="../output"
log_dir="$trace_output_dir/logs"
memory_dir="$trace_output_dir/memory"
plot_dir="./figs/"
num_funcs=100
char='a'
# policy="RAND"
# policy="CLOSEST_SIZE_LARGEST_KICK"
# policy="CLOSEST_SIZE_SMALLEST_KICK"
# policy="LRU"
# policy="LFU_CLASSIC"
# policy="LFU_GROUP_CLOSEST"
# policy="LFU_GROUP_MAX_COLD_TIME"
# policy="LFU_GROUP_MAX_INIT_TIME"
policy="LFUGROUP_MAXINITGROUP_CLOSEST"
# policy="LFUGROUP_CLOSESTGROUP_MAXINIT"
# policy="LFUGROUP_MAXINITGROUP_LARGEST"
# policy="DUAL_GREEDY_PRIORITY"


# -------------------- a --------------------

# run simulation
python3 ./sim/ParallelRunner.py --tracedir $trace_dir --numfuncs $num_funcs --savedir $trace_output_dir --logdir $log_dir --char $char --policy $policy --mem 5000 --mem 6000 --mem 7000 --mem 8000 --mem 8500 --mem 9500 --mem 10000

# plot graphs
python3 ./analyze/PlotResults.py --pckldir $trace_output_dir --plotdir $plot_dir --numfuncs $num_funcs --char $char --policy $policy

echo "********* 100 A tests are done *********"

# -------------------- b --------------------

char='b'

# run simulation
python3 ./sim/ParallelRunner.py --tracedir $trace_dir --numfuncs $num_funcs --savedir $trace_output_dir --logdir $log_dir --char $char --policy $policy  --mem 7500 --mem 10000 --mem 11000 --mem 13000 --mem 15000 --mem 5000 --mem 3000

# plot graphs
python3 ./analyze/PlotResults.py --pckldir $trace_output_dir --plotdir $plot_dir --numfuncs $num_funcs --char $char --policy $policy

echo "********* 100 B tests are done *********"

# -------------------- c --------------------

char='c'

# run simulation
python3 ./sim/ParallelRunner.py --tracedir $trace_dir --numfuncs $num_funcs --savedir $trace_output_dir --logdir $log_dir --char $char --policy $policy  --mem 7500 --mem 10000 --mem 11000 --mem 5000 --mem 3000 --mem 4000

# plot graphs
python3 ./analyze/PlotResults.py --pckldir $trace_output_dir --plotdir $plot_dir --numfuncs $num_funcs --char $char --policy $policy

echo "********* 100 C tests are done *********"