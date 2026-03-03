#pragma once
#include "rednose/helpers/ekf.h"
extern "C" {
void live_update_4(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_9(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_10(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_12(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_35(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_32(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_13(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_14(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_update_33(double *in_x, double *in_P, double *in_z, double *in_R, double *in_ea);
void live_H(double *in_vec, double *out_5490119348772464611);
void live_err_fun(double *nom_x, double *delta_x, double *out_6646984315713411964);
void live_inv_err_fun(double *nom_x, double *true_x, double *out_8056451519626369914);
void live_H_mod_fun(double *state, double *out_4630700446418583353);
void live_f_fun(double *state, double dt, double *out_8070439592731977950);
void live_F_fun(double *state, double dt, double *out_1985882346206358481);
void live_h_4(double *state, double *unused, double *out_1796780288959808788);
void live_H_4(double *state, double *unused, double *out_7493858400916257390);
void live_h_9(double *state, double *unused, double *out_7480286601811911660);
void live_H_9(double *state, double *unused, double *out_7735048047545848035);
void live_h_10(double *state, double *unused, double *out_7257025280745634156);
void live_H_10(double *state, double *unused, double *out_8415847126520116035);
void live_h_12(double *state, double *unused, double *out_5086539314692097000);
void live_H_12(double *state, double *unused, double *out_5933429264761332431);
void live_h_35(double *state, double *unused, double *out_8945596357847983049);
void live_H_35(double *state, double *unused, double *out_3187866232436318722);
void live_h_32(double *state, double *unused, double *out_5860342105730581694);
void live_H_32(double *state, double *unused, double *out_5370597090256982695);
void live_h_13(double *state, double *unused, double *out_2680026215910150235);
void live_H_13(double *state, double *unused, double *out_1761319233331018027);
void live_h_14(double *state, double *unused, double *out_7480286601811911660);
void live_H_14(double *state, double *unused, double *out_7735048047545848035);
void live_h_33(double *state, double *unused, double *out_3961725470476228090);
void live_H_33(double *state, double *unused, double *out_37309227797461118);
void live_predict(double *in_x, double *in_P, double *in_Q, double dt);
}