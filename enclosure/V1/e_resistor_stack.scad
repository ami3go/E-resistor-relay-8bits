// E-Resistor 8-bit modular open stacking frame — prototype V1
// Source resistor PCB: ami3go/E-resistor-relay-8bits / Resistors-board/Resistors-board.kicad_pcb
// PCB outline 145x55x1.6; hole centres 138x48; 3.2mm drill.
// Relay PCB dimensions/mounting centres are NOT established: articulated arms accommodate different boards.
// Units: millimetres. CAD geometry is support-free when printed in the documented orientation.
// Choose part = "base", "tray", "arm", "lower_post", "stack_post", "assembled", "stacked", or "exploded".

part = "exploded";
$fn = 44;

// Frame and verified lower PCB
frame_x=178; frame_y=86; rail=7.5; frame_t=4.5;
res_x=145; res_y=55; res_t=1.6; res_hole_x=138; res_hole_y=48;
res_boss_h=6.4; res_boss_d=9.3; res_insert_d=4.2; res_insert_depth=5.4;
// 14 mm is a PROVISIONAL terminal-block envelope; measure the assembled resistor PCB.
res_components_h=14;
// Configuration: set lower_post_h to tune 5–10 mm *component-to-PCB* clearance.
lower_post_h=21;
tray_t=5.2;
arm_t=3.6;
relay_t=1.6; relay_x_visual=145; relay_y_visual=56;
relay_components_max=30;  // provisional tall component/RJ45 envelope from upper PCB top
stack_post_h=45;

corner_x=83; corner_y=39;
pivot_x=74; pivot_y=38;
frame_bore=3.6; post_od=11.4;
slot_d=3.6;

z_res_bottom=frame_t+res_boss_h;
z_res_top=z_res_bottom+res_t;
z_tray=frame_t+lower_post_h;
z_tray_top=z_tray+tray_t;
z_relay_bottom=z_tray_top+arm_t;
z_relay_top=z_relay_bottom+relay_t;
stack_pitch=z_tray_top+stack_post_h;
actual_gap=z_relay_bottom-(z_res_top+res_components_h);
actual_headroom=stack_pitch-(z_relay_top+relay_components_max);

assert(res_x==145 && res_y==55 && res_hole_x==138 && res_hole_y==48);
assert(actual_gap>=5 && actual_gap<=10, "Adjust lower_post_h and res_components_h for 5–10 mm component clearance");
assert(actual_headroom>=5, "Increase stack_post_h for relay component headroom");

echo(str("Nominal resistor component-to-relay PCB clearance: ",actual_gap," mm"));
echo(str("Nominal upper component-to-next-base clearance: ",actual_headroom," mm"));
echo(str("Vertical repeat pitch: ",stack_pitch," mm"));

module rounded_plate(x,y,z,r=3) {
    hull() for(ix=[-1,1],iy=[-1,1]) translate([ix*(x/2-r),iy*(y/2-r),0]) cylinder(h=z,r=r);
}
module frame_ring(thickness) {
    difference() {
        rounded_plate(frame_x,frame_y,thickness,5);
        translate([0,0,-.5]) rounded_plate(frame_x-2*rail,frame_y-2*rail,thickness+1,3);
    }
}
module xy_ring_hole(x,y,t) {
    translate([x,y,-.3]) cylinder(h=t+.6,d=frame_bore);
}
module wire_tie_slots(t) {
    for(y=[-39,39],x=[-48,0,48])
        translate([x,y,t/2]) cube([12,2.5,t+.6],center=true);
}
module corner_ribs(t) {
    for(sx=[-1,1],sy=[-1,1]) {
        hull(){
            translate([sx*corner_x,sy*corner_y,0]) cylinder(d=11.4,h=t);
            translate([sx*(res_hole_x/2),sy*(res_hole_y/2),0]) cylinder(d=10,h=t);
        }
    }
}
module base() {
    difference() {
        union() {
            frame_ring(frame_t);
            corner_ribs(frame_t);
            for(sx=[-1,1],sy=[-1,1])
                translate([sx*(res_hole_x/2),sy*(res_hole_y/2),frame_t])
                    cylinder(d=res_boss_d,h=res_boss_h);
        }
        wire_tie_slots(frame_t);
        for(sx=[-1,1],sy=[-1,1]) {
            translate([sx*corner_x,sy*corner_y,0]) xy_ring_hole(0,0,frame_t);
            // Inserts installed from TOP of the resistor PCB support boss.
            translate([sx*(res_hole_x/2),sy*(res_hole_y/2),frame_t+res_boss_h-res_insert_depth])
                cylinder(d=res_insert_d,h=res_insert_depth+.3);
            // Pilot below insert so screw does not bottom on plastic.
            translate([sx*(res_hole_x/2),sy*(res_hole_y/2),frame_t])
                cylinder(d=3.1,h=res_boss_h+.1);
        }
    }
}
module tray() {
    difference() {
        union() {
            frame_ring(tray_t);
            for(sx=[-1,1],sy=[-1,1]) {
                hull() {
                    translate([sx*corner_x,sy*corner_y,0]) cylinder(d=11.4,h=tray_t);
                    translate([sx*pivot_x,sy*pivot_y,0]) cylinder(d=8.8,h=tray_t);
                }
            }
        }
        wire_tie_slots(tray_t);
        for(sx=[-1,1],sy=[-1,1]) {
            translate([sx*corner_x,sy*corner_y,0]) xy_ring_hole(0,0,tray_t);
            // Heat-set M3 insert for the relay PCB pivot arm; top insertion.
            translate([sx*pivot_x,sy*pivot_y,tray_t-4.4]) cylinder(d=4.2,h=4.6);
        }
    }
}
// Adjustable arm: pivot hole at centre, radial M3 slot between 8 and 28 mm.
// Orient radial slot toward a measured hole; tighten the anchor screw first.
// Printed lying flat. Slot screw: washer+M3 nut under arm, PCB+washer on top.
module arm() {
    difference() {
        hull(){
            cylinder(d=9.2,h=arm_t);
            translate([30,0,0]) cylinder(d=9.2,h=arm_t);
        }
        translate([0,0,-.1]) cylinder(d=3.6,h=arm_t+.2);
        hull() for(x=[8,28])
            translate([x,0,-.1]) cylinder(d=slot_d,h=arm_t+.2);
        // Flush-head clearance from BOTTOM for M3 flat/countersunk head.
        hull() for(x=[8,28])
            translate([x,0,-.1]) cylinder(d=6.0,h=1.9);
    }
}
// Double-ended heat-set insert sockets, with axial pilot. Both lengths print vertically.
module post(len) {
    difference() {
        cylinder(d=post_od,h=len);
        translate([0,0,-.1]) cylinder(d=3.0,h=len+.2);
        translate([0,0,-.1]) cylinder(d=4.2,h=5.7);
        translate([0,0,len-5.6]) cylinder(d=4.2,h=5.7);
    }
}
module pcb_lower_proxy() {
    difference(){
        cube([res_x,res_y,res_t],center=true);
        for(sx=[-1,1],sy=[-1,1])
            translate([sx*res_hole_x/2,sy*res_hole_y/2,-res_t]) cylinder(d=3.2,h=3*res_t);
    }
}
module pcb_upper_proxy() {
    difference(){
        cube([relay_x_visual,relay_y_visual,relay_t],center=true);
        // Proxy mounting coordinates ONLY, not measured on the YHQ001 board.
        for(sx=[-1,1],sy=[-1,1])
            translate([sx*69,sy*24,-relay_t]) cylinder(d=3.2,h=3*relay_t);
    }
}
module visible_lower_board(){
    color([.10,.43,.24]) translate([0,0,z_res_bottom+res_t/2]) pcb_lower_proxy();
    // Visualization ONLY of through-hole connector envelopes, no verified component heights.
    for(x=[-55,-22,11,44])
        color([.12,.54,.28]) translate([x,17,z_res_top]) cube([15,10,10],center=false);
    for(i=[-3:3])
        color([.10,.16,.10]) translate([i*17,-12,z_res_top]) cube([11,2,1.5],center=true);
}
module upper_arm_positions(){
    for(sx=[-1,1],sy=[-1,1]){
        px=sx*pivot_x; py=sy*pivot_y;
        hx=sx*69; hy=sy*24; // nominal demonstration target, must be measured
        theta=atan2(hy-py,hx-px);
        color([.87,.66,.20]) translate([px,py,z_tray_top]) rotate([0,0,theta]) arm();
    }
}
module visible_relay_board() {
    color([.03,.37,.38]) translate([0,0,z_relay_bottom+relay_t/2]) pcb_upper_proxy();
    for(i=[0:7]) {
        color([.14,.38,.80]) translate([-61+i*17,-15,z_relay_top]) cube([14,19,17]);
        color([.12,.65,.48]) translate([-61+i*17,12,z_relay_top]) cube([14,9,11]);
    }
    // Tall Ethernet connector model is a provisional envelope, not a board CAD import.
    color([.59,.63,.67]) translate([-65,-24,z_relay_top]) cube([16,17,25]);
}
module assembled(){
    color([.20,.23,.29]) base();
    visible_lower_board();
    for(sx=[-1,1],sy=[-1,1]) {
        color([.35,.38,.43]) translate([sx*corner_x,sy*corner_y,frame_t]) post(lower_post_h);
    }
    color([.22,.25,.32]) translate([0,0,z_tray]) tray();
    upper_arm_positions();
    visible_relay_board();
    for(sx=[-1,1],sy=[-1,1])
        color([.35,.38,.43]) translate([sx*corner_x,sy*corner_y,z_tray_top]) post(stack_post_h);
}
module exploded(){
    color([.20,.23,.29]) base();
    color([.10,.43,.24]) translate([0,0,z_res_bottom+7]) pcb_lower_proxy();
    for(sx=[-1,1],sy=[-1,1])
        color([.35,.38,.43]) translate([sx*corner_x,sy*corner_y,frame_t+14]) post(lower_post_h);
    color([.22,.25,.32]) translate([0,0,z_tray+28]) tray();
    for(sx=[-1,1],sy=[-1,1]){
        px=sx*pivot_x; py=sy*pivot_y;
        color([.87,.66,.20]) translate([px,py,z_tray_top+43])
          rotate([0,0,atan2(sy*24-py,sx*69-px)]) arm();
    }
    color([.03,.37,.38]) translate([0,0,z_relay_bottom+58]) pcb_upper_proxy();
    for(i=[0:7]) color([.14,.38,.80])
        translate([-61+i*17,-15,z_relay_top+59]) cube([14,19,17]);
    for(sx=[-1,1],sy=[-1,1])
        color([.35,.38,.43]) translate([sx*corner_x,sy*corner_y,z_tray_top+83]) post(stack_post_h);
    // ghost of next level frame to show repeating interface
    color([.7,.7,.7,.30]) translate([0,0,z_tray_top+145]) base();
}

if(part=="base") base();
else if(part=="tray") tray();
else if(part=="arm") arm();
else if(part=="lower_post") post(lower_post_h);
else if(part=="stack_post") post(stack_post_h);
else if(part=="assembled") assembled();
else if(part=="stacked") { assembled(); translate([0,0,stack_pitch]) assembled(); }
else if(part=="exploded") exploded();
else echo("Unknown part");
