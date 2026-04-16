# Significance Tests

## RQ2 Full vs Flat household action rates (CLEAN pooled)

      cell                 action  n_full  n_flat         U        p  rank_biserial flag
  MG-Owner             do_nothing    2600    3900 4930900.0 0.018940      -0.027436     
  MG-Owner          buy_insurance    2600    3900 5207150.0 0.020573       0.027051     
  MG-Owner buy_contents_insurance    2600    3900       NaN      NaN            NaN   NA
  MG-Owner          elevate_house    2600    3900 5071950.0 0.617030       0.000385     
  MG-Owner         buyout_program    2600    3900       NaN      NaN            NaN   NA
  MG-Owner               relocate    2600    3900       NaN      NaN            NaN   NA
 NMG-Owner             do_nothing    2600    3899 4915354.5 0.016747      -0.030253     
 NMG-Owner          buy_insurance    2600    3899 5212304.0 0.025141       0.028332     
 NMG-Owner buy_contents_insurance    2600    3899       NaN      NaN            NaN   NA
 NMG-Owner          elevate_house    2600    3899 5078441.5 0.299740       0.001922     
 NMG-Owner         buyout_program    2600    3899       NaN      NaN            NaN   NA
 NMG-Owner               relocate    2600    3899       NaN      NaN            NaN   NA
 MG-Renter             do_nothing    2600    3900 5046600.0 0.709896      -0.004615     
 MG-Renter          buy_insurance    2600    3900       NaN      NaN            NaN   NA
 MG-Renter buy_contents_insurance    2600    3900 5097300.0 0.664351       0.005385     
 MG-Renter          elevate_house    2600    3900       NaN      NaN            NaN   NA
 MG-Renter         buyout_program    2600    3900       NaN      NaN            NaN   NA
 MG-Renter               relocate    2600    3900 5066100.0 0.157289      -0.000769     
NMG-Renter             do_nothing    2600    3900 5017350.0 0.408556      -0.010385     
NMG-Renter          buy_insurance    2600    3900       NaN      NaN            NaN   NA
NMG-Renter buy_contents_insurance    2600    3900 5125250.0 0.385931       0.010897     
NMG-Renter          elevate_house    2600    3900       NaN      NaN            NaN   NA
NMG-Renter         buyout_program    2600    3900       NaN      NaN            NaN   NA
NMG-Renter               relocate    2600    3900 5067400.0 0.536984      -0.000513     

## RQ3 SP x protective coupling by arm

         arm    N       chi2             p  cramers_v  protective_rate_sp_lowmid  protective_rate_sp_highvh
CLN_Flat_123 5191 868.254602 7.816754e-191   0.408976                   0.378011                   0.851823
 CLN_Flat_42 5193 900.188553 8.929593e-198   0.416349                   0.362667                   0.819426
CLN_Flat_456 5197 765.933195 1.377208e-168   0.383901                   0.381707                   0.852325
CLN_Full_123 5195 849.004852 1.196503e-186   0.404261                   0.389262                   0.853899
 CLN_Full_42 5197 895.493769 9.363194e-197   0.415102                   0.382916                   0.847116
 LEG_Full_42 5162 846.664977 3.860194e-186   0.404992                   0.387634                   0.812013

## Within-agent SP-up -> switch-to-protective by arm

         arm    N      chi2            p  cramers_v  sp_up_switch_rate  sp_flatdown_switch_rate
CLN_Flat_123 4792  9.656242 1.887093e-03   0.044890           0.078563                 0.051269
 CLN_Flat_42 4794 28.879331 7.703053e-08   0.077615           0.085921                 0.042581
CLN_Flat_456 4798 20.880656 4.888060e-06   0.065969           0.098182                 0.055122
CLN_Full_123 4796 11.910625 5.581468e-04   0.049834           0.081776                 0.051015
 CLN_Full_42 4797 29.967060 4.394484e-08   0.079038           0.088581                 0.043523
 LEG_Full_42 4764  5.692952 1.703318e-02   0.034569           0.060513                 0.041964

## MG-Owner Y13 has_insurance across arms

ANOVA F=1.677360, p=1.380151e-01

      Multiple Comparison of Means - Tukey HSD, FWER=0.05      
===============================================================
   group1       group2    meandiff p-adj   lower  upper  reject
---------------------------------------------------------------
CLN_Flat_123  CLN_Flat_42    -0.05 0.9707 -0.2331 0.1331  False
CLN_Flat_123 CLN_Flat_456     0.01    1.0 -0.1731 0.1931  False
CLN_Flat_123 CLN_Full_123     0.05 0.9707 -0.1331 0.2331  False
CLN_Flat_123  CLN_Full_42    -0.01    1.0 -0.1931 0.1731  False
CLN_Flat_123  LEG_Full_42     0.12 0.4195 -0.0631 0.3031  False
 CLN_Flat_42 CLN_Flat_456     0.06 0.9368 -0.1231 0.2431  False
 CLN_Flat_42 CLN_Full_123      0.1 0.6244 -0.0831 0.2831  False
 CLN_Flat_42  CLN_Full_42     0.04 0.9892 -0.1431 0.2231  False
 CLN_Flat_42  LEG_Full_42     0.17 0.0862 -0.0131 0.3531  False
CLN_Flat_456 CLN_Full_123     0.04 0.9892 -0.1431 0.2231  False
CLN_Flat_456  CLN_Full_42    -0.02 0.9996 -0.2031 0.1631  False
CLN_Flat_456  LEG_Full_42     0.11 0.5206 -0.0731 0.2931  False
CLN_Full_123  CLN_Full_42    -0.06 0.9368 -0.2431 0.1231  False
CLN_Full_123  LEG_Full_42     0.07 0.8842 -0.1131 0.2531  False
 CLN_Full_42  LEG_Full_42     0.13 0.3266 -0.0531 0.3131  False
---------------------------------------------------------------
