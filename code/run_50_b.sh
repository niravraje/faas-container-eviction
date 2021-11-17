#!/bin/bash

trace_dir="../traces"
trace_output_dir="../output"
log_dir="$trace_output_dir/logs"
memory_dir="$trace_output_dir/memory"
plot_dir="./figs/"
num_funcs=50
char='b'
policy="RAND"

# run simulation
python3 ./sim/ParallelRunner.py --tracedir $trace_dir --numfuncs $num_funcs --savedir $trace_output_dir --logdir $log_dir --char $char --policy $policy --mem 1000 --mem 2000 --mem 3000 --mem 1500 --mem 2500

# plot graphs
python3 ./analyze/PlotResults.py --pckldir $trace_output_dir --plotdir $plot_dir --numfuncs $num_funcs --char $char --policy $policy

