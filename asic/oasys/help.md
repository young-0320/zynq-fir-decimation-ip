report_power(1)             General Commands Manual            report_power(1)

"Report and Check Commands"

report_power
SUMMARY
       Reports the power consumption information for the design.

USAGE
       report_power  [-all]  [-instance  <instance>]  [-hierarchical] [-inter‐
       nal_power { true | false }] [-switching_power { true | false }] [-leak‐
       age_power { true | false }] [[-total { true | false }] | [-total_only]]

ARGUMENTS
        -all
               Reports the power values of all instances in the design.

        -instance <instance>

              Reports the power for the specified instance.

        -hierarchical

              Reports the power of each hierarchical instance.

        -internal_power { true |false }

              Reports  internal  power. By default, this column is included in
              the report.

        -switching_power { true | false }

              Reports switching power. By default, this column is included  in
              the report.

        -leakage_power { true | false }

              Reports  leakage  power.  By default, this column is included in
              the report.

        -total { true | false }

              Reports the total power. By default, this column included in the
              report.

        -total_only

              Reports  only  the  total  power.  Cannot  be  used with -inter‐
              nal_power, -switching_power,  -leakage_power,  or  -total  argu‐
              ments.

DESCRIPTION
       Power  can  be  shown  for  a specific instance or at each hierarchical
       level. By default, -internal_power,  -switching_power,  -leakage_power,
       and -total arguments are all set.

EXAMPLES
       This example reports the internal, switching, leakage, and total power.

       % report_power

       Report Power (instances with prefix '*' are included in total) :

       --+-------------+----------------+-----------------+---------------+------------

         | Instance    | Internal Power | Switching Power |  Leakage  Power  |
       Total Power

         |              |  (uw)            | (uw)            | (uw)          |
       (uw)

       --+-------------+----------------+-----------------+---------------+------------

       1  |*IR_q_reg[7]  |  3.381459       | 0.006728        | 0.057166      |
       3.445353

       2 |*IR_q_reg[6] | 3.708899       | 0.009105         |  0.057166       |
       3.775170

       3  |*IR_q_reg[5]  |  3.531503       | 0.629139        | 0.057166      |
       4.217808

       4 |*IR_q_reg[4] | 3.362934       | 0.269173         |  0.057166       |
       3.689274

       5  |*IR_q_reg[3]  |  3.610359       | 0.190609        | 0.057166      |
       3.858135

       6 |*IR_q_reg[2] | 3.627044       | 0.755787         |  0.057166       |
       4.439998

       7  |*IR_q_reg[1]  |  3.438082       | 0.335269        | 0.057166      |
       3.830518

       8 |*IR_q_reg[0] | 3.558173       | 0.172637         |  0.057166       |
       3.787976

       87|*TOTAL        |  588.247375      |16.076899        | 15.91239      |
       620.236694

       --+-------------+----------------+-----------------+---------------+--------------

                                  01/04/2023                   report_power(1)
troff: <standard input>:74: warning [p 2, 3.2i]: can't break line
troff: <standard input>:80: warning [p 2, 4.5i]: can't break line
troff: <standard input>:100: warning [p 2, 9.3i]: can't break line
1
