#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void car_update_25(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_24(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_30(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_26(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_27(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_29(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_28(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_update_31(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void car_err_fun(double *nom_x, double *delta_x, double *out_6901067303530388663);
void car_inv_err_fun(double *nom_x, double *true_x, double *out_4833799724295175621);
void car_H_mod_fun(double *state, double *out_2138515224401220993);
void car_f_fun(double *state, double dt, double *out_528840376280883437);
void car_F_fun(double *state, double dt, double *out_3763699230579528397);
void car_h_25(double *state, double *unused, double *out_5170848469693113472);
void car_H_25(double *state, double *unused, double *out_8756865118473177086);
void car_h_24(double *state, double *unused, double *out_2075474711332239505);
void car_H_24(double *state, double *unused, double *out_9219421473193035806);
void car_h_30(double *state, double *unused, double *out_8798824097078245685);
void car_H_30(double *state, double *unused, double *out_8886204065616417156);
void car_h_26(double *state, double *unused, double *out_8195508212401768168);
void car_H_26(double *state, double *unused, double *out_5948375636362318306);
void car_h_27(double *state, double *unused, double *out_6338592270769255209);
void car_H_27(double *state, double *unused, double *out_7385776696292709549);
void car_h_29(double *state, double *unused, double *out_6940010428382618763);
void car_H_29(double *state, double *unused, double *out_8375972721302024972);
void car_h_28(double *state, double *unused, double *out_5735276386092777692);
void car_H_28(double *state, double *unused, double *out_4988372335337996070);
void car_h_31(double *state, double *unused, double *out_9032531946121615124);
void car_H_31(double *state, double *unused, double *out_8726219156596216658);
void car_predict(double *in_x, double *in_P, double *in_Q, double dt);
void car_set_mass(double x);
void car_set_rotational_inertia(double x);
void car_set_center_to_front(double x);
void car_set_center_to_rear(double x);
void car_set_stiffness_front(double x);
void car_set_stiffness_rear(double x);
}