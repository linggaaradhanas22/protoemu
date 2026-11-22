set cells $::env(PROBE_PDK)/libs.ref/sg13cmos5l_stdcell
read_lef $cells/lef/sg13cmos5l_tech.lef
read_lef $cells/lef/sg13cmos5l_stdcell.lef
define_corners slow fast
read_liberty -corner slow $cells/lib/sg13cmos5l_stdcell_slow_1p08V_125C.lib
read_liberty -corner fast $cells/lib/sg13cmos5l_stdcell_fast_1p32V_m40C.lib
read_verilog /work/mapped.v
link_design full_core_probe

set period [expr {50.0 / 3}]
create_clock -name clk -period $period [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]
set inputs [all_inputs -no_clocks]
set_input_delay -max -clock clk [expr {$period * 0.20}] $inputs
set_input_delay -min -clock clk 0 $inputs
set_output_delay -max -clock clk [expr {$period * 0.20}] [all_outputs]
set_output_delay -min -clock clk 0 [all_outputs]
set_driving_cell -lib_cell sg13cmos5l_buf_4 -pin X $inputs
set_load 0.006 [all_outputs]
set_max_fanout 10 [current_design]

proc measure {phase} {
    puts "PHASE $phase"
    report_design_area
    foreach {corner kind delay} {slow setup max fast hold min} {
        puts "GROUP all_$kind"
        report_checks -corner $corner -path_delay $delay -format full_clock_expanded -digits 3
        puts "GROUP reg_$kind"
        report_checks -corner $corner -from [all_registers -clock_pins] -to [all_registers -data_pins] \
            -path_delay $delay -format full_clock_expanded -digits 3
    }
}

initialize_floorplan -site CoreSite -die_area $::env(PROBE_DIE) -core_area $::env(PROBE_CORE)
make_tracks
set_wire_rc -signal -layer Metal3
set_wire_rc -clock -layer Metal4
place_pins -hor_layers Metal3 -ver_layers Metal2
global_placement -density 0.35
estimate_parasitics -placement
repair_design -max_wire_length 400
detailed_placement
estimate_parasitics -placement
measure placed

clock_tree_synthesis -root_buf sg13cmos5l_buf_16 -buf_list {sg13cmos5l_buf_8 sg13cmos5l_buf_4 sg13cmos5l_buf_2}
set_propagated_clock [get_clocks clk]
detailed_placement
estimate_parasitics -placement
measure cts

repair_timing -setup -setup_margin 0.1 -max_utilization 60
detailed_placement
estimate_parasitics -placement
repair_timing -hold -hold_margin 0.08 -max_utilization 60
detailed_placement
estimate_parasitics -placement
measure repaired
