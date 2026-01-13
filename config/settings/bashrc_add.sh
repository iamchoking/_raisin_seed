# >>> _raisin_seed >>>

export RAISIN_MASTER_DIR="/home/$(whoami)/raisin_master"

alias ldp='source $RAISIN_MASTER_DIR/ld_prefix_path.sh'
alias raisin_setup='cd $RAISIN_MASTER_DIR && python3 raisin.py setup'

alias raisin_gui='cd $RAISIN_MASTER_DIR && source ./ld_prefix_path.sh && ./cmake-build-release/src/raisin_gui/raisin_gui/raisin_gui'
alias raipal_node='cd $RAISIN_MASTER_DIR && source ./ld_prefix_path.sh && ./cmake-build-release/src/raisin_raipal/raisin_raipal_node'
alias raibo2_node='cd $RAISIN_MASTER_DIR && source ./ld_prefix_path.sh && ./install/bin/raisin_raibo2_node'

# <<< _raisin_seed <<<
