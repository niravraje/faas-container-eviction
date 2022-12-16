#!/bin/bash

trace_dir="../traces"
trace_output_dir="../output"
log_dir="$trace_output_dir/logs"
memory_dir="$trace_output_dir/memory"
plot_dir="./figs/"
num_funcs=20
char='a'
policy="LFUGROUP_MAXINITGROUP_CLOSEST"

# -------------------- a --------------------

# run simulation
python3 ./sim/ParallelRunner.py --tracedir $trace_dir --numfuncs $num_funcs --savedir $trace_output_dir --logdir $log_dir --char $char --policy $policy --mem 5000 --mem 6000 --mem 8000 --mem 2000 --mem 4000 --mem 1000

# plot graphs
python3 ./analyze/PlotResults.py --pckldir $trace_output_dir --plotdir $plot_dir --numfuncs $num_funcs --char $char --policy $policy

echo "********* 20 A tests are done *********"

# -------------------- b --------------------

char='b'

# run simulation
python3 ./sim/ParallelRunner.py --tracedir $trace_dir --numfuncs $num_funcs --savedir $trace_output_dir --logdir $log_dir --char $char --policy $policy --mem 2000 --mem 3000 --mem 3500 --mem 4000 --mem 1000 --mem 1500

# plot graphs
python3 ./analyze/PlotResults.py --pckldir $trace_output_dir --plotdir $plot_dir --numfuncs $num_funcs --char $char --policy $policy

echo "********* 20 B tests are done *********"

# -------------------- c --------------------

char='c'

# run simulation
python3 ./sim/ParallelRunner.py --tracedir $trace_dir --numfuncs $num_funcs --savedir $trace_output_dir --logdir $log_dir --char $char --policy $policy --mem 1000 --mem 2000 --mem 4000 --mem 500 --mem 800 --mem 10000

# plot graphs
python3 ./analyze/PlotResults.py --pckldir $trace_output_dir --plotdir $plot_dir --numfuncs $num_funcs --char $char --policy $policy

echo "********* 20 C tests are done *********"