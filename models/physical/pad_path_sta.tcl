set pdk $::env(PROBE_PDK)
set cells $pdk/libs.ref/sg13cmos5l_stdcell
read_lef $cells/lef/sg13cmos5l_tech.lef
read_lef $cells/lef/sg13cmos5l_stdcell.lef
read_liberty $cells/lib/sg13cmos5l_stdcell_$::env(PROBE_CORNER).lib
read_verilog /work/mapped.v
link_design pad_path_probe

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
report_design_area

puts "GROUP all_setup"
report_checks -path_delay max -format full_clock_expanded -digits 3
puts "GROUP all_hold"
report_checks -path_delay min -format full_clock_expanded -digits 3
puts "GROUP reg_setup"
report_checks -from [all_registers -clock_pins] -to [all_registers -data_pins] \
    -path_delay max -format full_clock_expanded -digits 3
puts "GROUP reg_hold"
report_checks -from [all_registers -clock_pins] -to [all_registers -data_pins] \
    -path_delay min -format full_clock_expanded -digits 3
source /work/endpoints.tcl
exit
