# M3-S0 simulation results (eta 0.96, W 12)

## dog_rho1

gate: {'cancellations_equal': True, 'base_send_within_15pct': True, 'remote_within_10pct': True, 'discarded_within_15pct': True, 'pass': True, 'sim_base_send_s': 16.951490945816044, 'sim_remote_s': 51.6, 'sim_discarded_mb': 2783.9}

| policy | remote s | local s | cancelled | completed | final | discarded MB | staged MB | wasted MB | total MB | migrations (valid/180, delta MB, ready s) |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 51.6 | 0.02 | 2 | 1 | True | 2783.9 | 0.0 | 0.0 | 4552.0 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:21.34 |
| floor | 26.78 | 10.2 | 0 | 3 | True | 0.0 | 0.0 | 0.0 | 54.3 | B:180/0:2MB:7.31; C:180/0:2MB:7.220000000000001; D:180/0:2MB:7.149999999999999 |
| none+retain | 51.6 | 0.02 | 2 | 1 | True | 2783.9 | 0.0 | 0.0 | 4552.0 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:21.34 |
| star/oracle/fair/once | 41.44 | 0.02 | 2 | 1 | True | 1408.0 | 2012.8 | 9.6 | 4180.7 | B:0/180:1728MB:None; C:105/75:721MB:None; D:104/76:731MB:11.169999999999998 |
| star/oracle/fair/fresh | 41.44 | 0.02 | 2 | 1 | True | 1408.0 | 2012.8 | 9.6 | 4180.7 | B:0/180:1728MB:None; C:105/75:721MB:None; D:104/76:731MB:11.169999999999998 |
| star/oracle/residual/once | 48.54 | 0.02 | 2 | 1 | True | 2783.9 | 632.6 | 9.6 | 4883.2 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:32/148:1421MB:18.27 |
| star/oracle/residual/fresh | 48.54 | 0.02 | 2 | 1 | True | 2783.9 | 632.6 | 9.6 | 4883.2 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:32/148:1421MB:18.27 |
| star/causal/fair/once | 49.9 | 0.02 | 2 | 1 | True | 952.3 | 3805.1 | 1993.6 | 5339.0 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:125/55:530MB:19.63 |
| star/causal/fair/fresh | 50.06 | 0.02 | 2 | 1 | True | 952.3 | 3824.3 | 2012.8 | 5358.5 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:125/55:530MB:19.790000000000003 |
| star/causal/residual/once | 48.54 | 0.02 | 2 | 1 | True | 2783.9 | 1063.9 | 603.8 | 5316.6 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:32/148:1421MB:18.27 |
| star/causal/residual/fresh | 48.54 | 0.02 | 2 | 1 | True | 2783.9 | 1073.5 | 613.4 | 5326.2 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:32/148:1421MB:18.27 |
| line/oracle/fair/once | 41.44 | 0.02 | 2 | 1 | True | 1408.0 | 2012.8 | 9.6 | 4180.7 | B:0/180:1728MB:None; C:105/75:721MB:None; D:104/76:731MB:11.169999999999998 |
| line/oracle/fair/fresh | 41.44 | 0.02 | 2 | 1 | True | 1408.0 | 2012.8 | 9.6 | 4180.7 | B:0/180:1728MB:None; C:105/75:721MB:None; D:104/76:731MB:11.169999999999998 |
| line/oracle/residual/once | 48.54 | 0.02 | 2 | 1 | True | 2783.9 | 632.6 | 9.6 | 4883.2 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:32/148:1421MB:18.27 |
| line/oracle/residual/fresh | 48.54 | 0.02 | 2 | 1 | True | 2783.9 | 632.6 | 9.6 | 4883.2 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:32/148:1421MB:18.27 |
| line/causal/fair/once | 37.52 | 0.02 | 2 | 1 | True | 1408.0 | 3766.8 | 1140.6 | 5302.1 | B:0/180:1728MB:None; C:105/75:721MB:None; D:169/11:108MB:7.2500000000000036 |
| line/causal/fair/fresh | 37.52 | 0.02 | 2 | 1 | True | 1402.8 | 3785.9 | 1159.7 | 5316.2 | B:0/180:1728MB:None; C:105/75:721MB:None; D:169/11:108MB:7.2500000000000036 |
| line/causal/residual/once | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2492.0 | 508.0 | 5356.9 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:174/6:60MB:7.2500000000000036 |
| line/causal/residual/fresh | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2511.2 | 527.2 | 5376.1 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:174/6:60MB:7.2500000000000036 |
| tree/oracle/fair/once | 37.52 | 0.02 | 2 | 1 | True | 1459.9 | 2731.6 | 19.2 | 4232.7 | B:0/180:1728MB:None; C:105/75:721MB:16.72; D:178/2:22MB:7.2500000000000036 |
| tree/oracle/fair/fresh | 37.52 | 0.02 | 2 | 1 | True | 1459.9 | 2741.2 | 19.2 | 4232.7 | B:0/180:1728MB:None; C:105/75:721MB:16.92; D:179/1:12MB:7.2500000000000036 |
| tree/oracle/residual/once | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 1859.4 | 28.8 | 4878.0 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:158/22:213MB:7.2500000000000036 |
| tree/oracle/residual/fresh | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 1859.4 | 28.8 | 4878.0 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:158/22:213MB:7.2500000000000036 |
| tree/causal/fair/once | 46.48 | 0.02 | 2 | 1 | True | 952.3 | 3805.1 | 1993.6 | 5333.0 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:125/55:530MB:16.220000000000002 |
| tree/causal/fair/fresh | 46.48 | 0.02 | 2 | 1 | True | 952.3 | 3805.1 | 1993.6 | 5333.0 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:125/55:530MB:16.220000000000002 |
| tree/causal/residual/once | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2338.7 | 670.9 | 5364.4 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:158/22:213MB:7.2500000000000036 |
| tree/causal/residual/fresh | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2338.7 | 670.9 | 5364.4 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:158/22:213MB:7.2500000000000036 |
| butterfly/oracle/fair/once | 37.52 | 0.02 | 2 | 1 | True | 1459.9 | 2731.6 | 19.2 | 4232.7 | B:0/180:1728MB:None; C:105/75:721MB:16.42; D:178/2:22MB:7.2500000000000036 |
| butterfly/oracle/fair/fresh | 37.52 | 0.02 | 2 | 1 | True | 1459.9 | 2741.2 | 19.2 | 4232.7 | B:0/180:1728MB:None; C:105/75:721MB:16.42; D:179/1:12MB:7.2500000000000036 |
| butterfly/oracle/residual/once | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 1801.9 | 19.2 | 4871.5 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:153/27:261MB:7.2500000000000036 |
| butterfly/oracle/residual/fresh | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 1801.9 | 19.2 | 4871.5 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:153/27:261MB:7.2500000000000036 |
| butterfly/causal/fair/once | 44.66 | 0.02 | 2 | 1 | True | 952.3 | 3843.4 | 1993.6 | 5326.3 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:129/51:491MB:14.390000000000004 |
| butterfly/causal/fair/fresh | 44.66 | 0.02 | 2 | 1 | True | 952.3 | 3843.4 | 1993.6 | 5326.3 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:129/51:491MB:14.390000000000004 |
| butterfly/causal/residual/once | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2329.1 | 661.3 | 5354.8 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:158/22:213MB:7.2500000000000036 |
| butterfly/causal/residual/fresh | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2329.1 | 661.3 | 5354.8 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:158/22:213MB:7.2500000000000036 |
| adaptive/oracle/fair/once | 37.52 | 0.02 | 2 | 1 | True | 1459.9 | 2731.6 | 19.2 | 4232.7 | B:0/180:1728MB:None; C:105/75:721MB:16.42; D:178/2:22MB:7.2500000000000036 |
| adaptive/oracle/fair/fresh | 37.52 | 0.02 | 2 | 1 | True | 1459.9 | 2741.2 | 19.2 | 4232.7 | B:0/180:1728MB:None; C:105/75:721MB:16.42; D:179/1:12MB:7.2500000000000036 |
| adaptive/oracle/residual/once | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 1801.9 | 19.2 | 4871.5 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:153/27:261MB:7.2500000000000036 |
| adaptive/oracle/residual/fresh | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 1801.9 | 19.2 | 4871.5 | B:0/180:1728MB:None; C:33/147:1411MB:None; D:153/27:261MB:7.2500000000000036 |
| adaptive/causal/fair/once | 44.66 | 0.02 | 2 | 1 | True | 952.3 | 3843.4 | 1993.6 | 5326.3 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:129/51:491MB:14.390000000000004 |
| adaptive/causal/fair/fresh | 44.66 | 0.02 | 2 | 1 | True | 952.3 | 3843.4 | 1993.6 | 5326.3 | B:0/180:1728MB:None; C:64/116:1114MB:None; D:129/51:491MB:14.390000000000004 |
| adaptive/causal/residual/once | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2329.1 | 661.3 | 5354.8 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:158/22:213MB:7.2500000000000036 |
| adaptive/causal/residual/fresh | 37.52 | 0.02 | 2 | 1 | True | 2783.9 | 2329.1 | 661.3 | 5354.8 | B:0/180:1728MB:None; C:16/164:1574MB:None; D:158/22:213MB:7.2500000000000036 |

## dog_rho2

gate: {'cancellations_equal': True, 'base_send_within_15pct': True, 'remote_within_10pct': True, 'discarded_within_15pct': True, 'pass': True, 'sim_base_send_s': 17.00522500038147, 'sim_remote_s': 37.88, 'sim_discarded_mb': 1194.1}

| policy | remote s | local s | cancelled | completed | final | discarded MB | staged MB | wasted MB | total MB | migrations (valid/180, delta MB, ready s) |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 37.88 | 0.02 | 2 | 1 | True | 1194.1 | 0.0 | 0.0 | 2974.6 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:21.06 |
| floor | 24.0 | 0.02 | 0 | 1 | True | 0.0 | 0.0 | 0.0 | 120.4 | B:180/0:2MB:7.31; C:180/0:2MB:6.930000000000001; D:180/0:2MB:7.18 |
| none+retain | 37.88 | 0.02 | 2 | 1 | True | 1194.1 | 0.0 | 0.0 | 2974.6 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:21.06 |
| star/oracle/fair/once | 31.96 | 0.02 | 2 | 1 | True | 602.0 | 1150.2 | 0.0 | 2951.1 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:60/120:1153MB:15.129999999999999 |
| star/oracle/fair/fresh | 31.96 | 0.02 | 2 | 1 | True | 602.0 | 1150.2 | 0.0 | 2951.1 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:60/120:1153MB:15.129999999999999 |
| star/oracle/residual/once | 35.06 | 0.02 | 2 | 1 | True | 1194.1 | 555.9 | 0.0 | 3255.3 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:29/151:1450MB:18.23 |
| star/oracle/residual/fresh | 35.06 | 0.02 | 2 | 1 | True | 1194.1 | 555.9 | 0.0 | 3255.3 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:29/151:1450MB:18.23 |
| star/causal/fair/once | 53.3 | 0.02 | 2 | 1 | True | 408.5 | 3776.3 | 2789.1 | 5360.1 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:68/112:1076MB:36.47 |
| star/causal/fair/fresh | 53.3 | 0.02 | 2 | 1 | True | 408.5 | 3814.7 | 2827.5 | 5398.5 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:68/112:1076MB:36.47 |
| star/causal/residual/once | 35.06 | 0.02 | 2 | 1 | True | 1194.1 | 1495.2 | 1083.1 | 4208.9 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:29/151:1450MB:18.23 |
| star/causal/residual/fresh | 35.06 | 0.02 | 2 | 1 | True | 1194.1 | 1495.2 | 1083.1 | 4208.9 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:29/151:1450MB:18.23 |
| line/oracle/fair/once | 31.96 | 0.02 | 2 | 1 | True | 602.0 | 1150.2 | 0.0 | 2951.1 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:60/120:1153MB:15.129999999999999 |
| line/oracle/fair/fresh | 31.96 | 0.02 | 2 | 1 | True | 602.0 | 1150.2 | 0.0 | 2951.1 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:60/120:1153MB:15.129999999999999 |
| line/oracle/residual/once | 35.06 | 0.02 | 2 | 1 | True | 1194.1 | 555.9 | 0.0 | 3255.3 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:29/151:1450MB:18.23 |
| line/oracle/residual/fresh | 35.06 | 0.02 | 2 | 1 | True | 1194.1 | 555.9 | 0.0 | 3255.3 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:29/151:1450MB:18.23 |
| line/causal/fair/once | 35.78 | 0.02 | 2 | 1 | True | 602.0 | 3718.8 | 2338.7 | 5295.5 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:84/96:923MB:18.95 |
| line/causal/fair/fresh | 36.12 | 0.02 | 2 | 1 | True | 602.0 | 3757.2 | 2377.0 | 5334.6 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:84/96:923MB:19.290000000000003 |
| line/causal/residual/once | 28.98 | 0.02 | 2 | 1 | True | 1194.1 | 3230.0 | 2079.9 | 5318.7 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:91/89:855MB:12.149999999999999 |
| line/causal/residual/fresh | 28.98 | 0.02 | 2 | 1 | True | 1194.1 | 3201.3 | 2051.1 | 5297.4 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:91/89:855MB:12.149999999999999 |
| tree/oracle/fair/once | 28.62 | 0.02 | 2 | 1 | True | 602.0 | 1476.0 | 0.0 | 2954.0 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:94/86:827MB:11.79 |
| tree/oracle/fair/fresh | 28.62 | 0.02 | 2 | 1 | True | 602.0 | 1476.0 | 0.0 | 2954.0 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:94/86:827MB:11.79 |
| tree/oracle/residual/once | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 1025.6 | 9.6 | 3249.9 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:77/103:990MB:13.52 |
| tree/oracle/residual/fresh | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 1025.6 | 9.6 | 3249.9 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:77/103:990MB:13.52 |
| tree/causal/fair/once | 50.32 | 0.02 | 2 | 1 | True | 408.5 | 3776.3 | 2789.1 | 5353.3 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:68/112:1076MB:33.489999999999995 |
| tree/causal/fair/fresh | 50.76 | 0.02 | 2 | 1 | True | 408.5 | 3814.7 | 2827.5 | 5392.7 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:68/112:1076MB:33.92 |
| tree/causal/residual/once | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 2012.8 | 1140.6 | 4257.4 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:77/103:990MB:13.52 |
| tree/causal/residual/fresh | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 2012.8 | 1140.6 | 4257.4 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:77/103:990MB:13.52 |
| butterfly/oracle/fair/once | 28.54 | 0.02 | 2 | 1 | True | 608.7 | 1485.6 | 0.0 | 2950.6 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:95/85:817MB:11.71 |
| butterfly/oracle/fair/fresh | 28.54 | 0.02 | 2 | 1 | True | 608.7 | 1485.6 | 0.0 | 2950.6 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:95/85:817MB:11.71 |
| butterfly/oracle/residual/once | 30.68 | 0.02 | 2 | 1 | True | 1194.1 | 977.6 | 0.0 | 3240.9 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:73/107:1028MB:13.84 |
| butterfly/oracle/residual/fresh | 30.68 | 0.02 | 2 | 1 | True | 1194.1 | 977.6 | 0.0 | 3240.9 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:73/107:1028MB:13.84 |
| butterfly/causal/fair/once | 48.84 | 0.02 | 2 | 1 | True | 408.5 | 3805.1 | 2789.1 | 5349.1 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:71/109:1047MB:32.010000000000005 |
| butterfly/causal/fair/fresh | 49.3 | 0.02 | 2 | 1 | True | 408.5 | 3843.4 | 2827.5 | 5388.5 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:71/109:1047MB:32.47 |
| butterfly/causal/residual/once | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 2051.1 | 1178.9 | 4295.7 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:77/103:990MB:13.52 |
| butterfly/causal/residual/fresh | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 2051.1 | 1178.9 | 4295.7 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:77/103:990MB:13.52 |
| adaptive/oracle/fair/once | 28.54 | 0.02 | 2 | 1 | True | 608.7 | 1485.6 | 0.0 | 2950.6 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:95/85:817MB:11.71 |
| adaptive/oracle/fair/fresh | 28.54 | 0.02 | 2 | 1 | True | 608.7 | 1485.6 | 0.0 | 2950.6 | B:0/180:1728MB:None; C:60/120:1153MB:None; D:95/85:817MB:11.71 |
| adaptive/oracle/residual/once | 30.68 | 0.02 | 2 | 1 | True | 1194.1 | 977.6 | 0.0 | 3240.9 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:73/107:1028MB:13.84 |
| adaptive/oracle/residual/fresh | 30.68 | 0.02 | 2 | 1 | True | 1194.1 | 977.6 | 0.0 | 3240.9 | B:0/180:1728MB:None; C:29/151:1450MB:None; D:73/107:1028MB:13.84 |
| adaptive/causal/fair/once | 48.84 | 0.02 | 2 | 1 | True | 408.5 | 3805.1 | 2789.1 | 5349.1 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:71/109:1047MB:32.010000000000005 |
| adaptive/causal/fair/fresh | 49.3 | 0.02 | 2 | 1 | True | 408.5 | 3843.4 | 2827.5 | 5388.5 | B:0/180:1728MB:None; C:35/145:1392MB:None; D:71/109:1047MB:32.47 |
| adaptive/causal/residual/once | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 2051.1 | 1178.9 | 4295.7 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:77/103:990MB:13.52 |
| adaptive/causal/residual/fresh | 30.36 | 0.02 | 2 | 1 | True | 1194.1 | 2051.1 | 1178.9 | 4295.7 | B:0/180:1728MB:None; C:14/166:1593MB:None; D:77/103:990MB:13.52 |

## bfly_rho1

gate: {'cancellations_equal': True, 'base_send_within_15pct': True, 'remote_within_10pct': True, 'discarded_within_15pct': True, 'pass': True, 'sim_base_send_s': 20.239655799865723, 'sim_remote_s': 59.04, 'sim_discarded_mb': 3151.9}

| policy | remote s | local s | cancelled | completed | final | discarded MB | staged MB | wasted MB | total MB | migrations (valid/180, delta MB, ready s) |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 59.04 | 0.02 | 2 | 1 | True | 3151.9 | 0.0 | 0.0 | 5535.8 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:25.700000000000003 |
| floor | 30.4 | 7.8 | 0 | 3 | True | 0.0 | 0.0 | 0.0 | 719.6 | B:180/0:2MB:7.87; C:180/0:2MB:7.799999999999999; D:180/0:2MB:7.75 |
| none+retain | 59.04 | 0.02 | 2 | 1 | True | 3151.9 | 0.0 | 0.0 | 5535.8 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:25.700000000000003 |
| star/oracle/fair/once | 49.5 | 0.02 | 2 | 1 | True | 1891.8 | 1821.1 | 335.5 | 5123.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:79/101:970MB:16.17 |
| star/oracle/fair/fresh | 49.5 | 0.02 | 2 | 1 | True | 1891.8 | 1821.1 | 335.5 | 5123.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:79/101:970MB:16.17 |
| star/oracle/residual/once | 56.26 | 0.02 | 2 | 1 | True | 3151.9 | 555.9 | 143.8 | 5818.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:23/157:1507MB:22.939999999999998 |
| star/oracle/residual/fresh | 56.26 | 0.02 | 2 | 1 | True | 3151.9 | 555.9 | 143.8 | 5818.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:23/157:1507MB:22.939999999999998 |
| star/causal/fair/once | 67.86 | 0.02 | 2 | 1 | True | 1487.3 | 4035.1 | 2798.7 | 7294.6 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:34.540000000000006 |
| star/causal/fair/fresh | 71.38 | 0.02 | 2 | 1 | True | 1487.3 | 4495.2 | 3258.8 | 7837.0 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:38.05 |
| star/causal/residual/once | 56.64 | 0.02 | 2 | 1 | True | 3151.9 | 1389.8 | 1131.0 | 6701.3 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:19/161:1546MB:23.32 |
| star/causal/residual/fresh | 56.64 | 0.02 | 2 | 1 | True | 3151.9 | 1476.0 | 1217.2 | 6798.9 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:19/161:1546MB:23.32 |
| line/oracle/fair/once | 49.5 | 0.02 | 2 | 1 | True | 1891.8 | 1821.1 | 335.5 | 5123.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:79/101:970MB:16.17 |
| line/oracle/fair/fresh | 49.5 | 0.02 | 2 | 1 | True | 1891.8 | 1821.1 | 335.5 | 5123.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:79/101:970MB:16.17 |
| line/oracle/residual/once | 56.26 | 0.02 | 2 | 1 | True | 3151.9 | 555.9 | 143.8 | 5818.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:23/157:1507MB:22.939999999999998 |
| line/oracle/residual/fresh | 56.26 | 0.02 | 2 | 1 | True | 3151.9 | 555.9 | 143.8 | 5818.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:23/157:1507MB:22.939999999999998 |
| line/causal/fair/once | 45.78 | 0.02 | 2 | 1 | True | 1891.8 | 4006.4 | 2233.2 | 6931.3 | B:0/180:1728MB:None; C:76/104:999MB:None; D:109/71:683MB:12.46 |
| line/causal/fair/fresh | 55.84 | 0.02 | 2 | 1 | True | 1775.9 | 5060.7 | 3354.6 | 8099.6 | B:0/180:1728MB:None; C:68/112:1076MB:None; D:110/70:673MB:22.520000000000003 |
| line/causal/residual/once | 42.72 | 0.02 | 2 | 1 | True | 3151.9 | 3028.7 | 1543.1 | 6895.0 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:135/45:434MB:9.399999999999999 |
| line/causal/residual/fresh | 43.02 | 0.02 | 2 | 1 | True | 3151.9 | 3325.9 | 1878.6 | 7239.8 | B:0/180:1728MB:None; C:19/161:1546MB:None; D:132/48:462MB:9.700000000000003 |
| tree/oracle/fair/once | 42.0 | 0.02 | 2 | 1 | True | 1891.8 | 2530.3 | 450.5 | 5061.0 | B:0/180:1728MB:None; C:76/104:999MB:None; D:141/39:376MB:8.670000000000002 |
| tree/oracle/fair/fresh | 42.0 | 0.02 | 2 | 1 | True | 1891.8 | 2530.3 | 450.5 | 5061.0 | B:0/180:1728MB:None; C:76/104:999MB:None; D:141/39:376MB:8.670000000000002 |
| tree/oracle/residual/once | 44.06 | 0.02 | 2 | 1 | True | 3151.9 | 1792.3 | 412.1 | 5799.3 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:124/56:539MB:10.740000000000002 |
| tree/oracle/residual/fresh | 44.06 | 0.02 | 2 | 1 | True | 3151.9 | 1792.3 | 412.1 | 5799.3 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:124/56:539MB:10.740000000000002 |
| tree/causal/fair/once | 62.34 | 0.02 | 2 | 1 | True | 1487.3 | 4035.1 | 2798.7 | 7165.5 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:29.009999999999998 |
| tree/causal/fair/fresh | 71.28 | 0.02 | 2 | 1 | True | 1487.3 | 4763.6 | 3527.1 | 8103.0 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:37.95 |
| tree/causal/residual/once | 44.24 | 0.02 | 2 | 1 | True | 3151.9 | 2865.8 | 1619.8 | 6900.1 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:122/58:558MB:10.920000000000002 |
| tree/causal/residual/fresh | 44.24 | 0.02 | 2 | 1 | True | 3151.9 | 3095.8 | 1849.8 | 7141.8 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:122/58:558MB:10.920000000000002 |
| butterfly/oracle/fair/once | 42.3 | 0.02 | 2 | 1 | True | 1891.8 | 2463.3 | 412.1 | 5035.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:138/42:405MB:8.969999999999999 |
| butterfly/oracle/fair/fresh | 42.3 | 0.02 | 2 | 1 | True | 1891.8 | 2463.3 | 412.1 | 5035.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:138/42:405MB:8.969999999999999 |
| butterfly/oracle/residual/once | 45.28 | 0.02 | 2 | 1 | True | 3151.9 | 1591.1 | 306.7 | 5722.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:114/66:635MB:11.96 |
| butterfly/oracle/residual/fresh | 45.28 | 0.02 | 2 | 1 | True | 3151.9 | 1591.1 | 306.7 | 5722.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:114/66:635MB:11.96 |
| butterfly/causal/fair/once | 61.92 | 0.02 | 2 | 1 | True | 1487.3 | 4035.1 | 2798.7 | 7155.7 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:28.590000000000003 |
| butterfly/causal/fair/fresh | 70.64 | 0.02 | 2 | 1 | True | 1487.3 | 4754.0 | 3517.6 | 8078.5 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:37.3 |
| butterfly/causal/residual/once | 43.74 | 0.02 | 2 | 1 | True | 3151.9 | 2808.3 | 1524.0 | 6792.5 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:126/54:520MB:10.420000000000002 |
| butterfly/causal/residual/fresh | 43.74 | 0.02 | 2 | 1 | True | 3151.9 | 3067.1 | 1782.7 | 7061.0 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:126/54:520MB:10.420000000000002 |
| adaptive/oracle/fair/once | 42.3 | 0.02 | 2 | 1 | True | 1891.8 | 2463.3 | 412.1 | 5035.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:138/42:405MB:8.969999999999999 |
| adaptive/oracle/fair/fresh | 42.3 | 0.02 | 2 | 1 | True | 1891.8 | 2463.3 | 412.1 | 5035.6 | B:0/180:1728MB:None; C:76/104:999MB:None; D:138/42:405MB:8.969999999999999 |
| adaptive/oracle/residual/once | 45.28 | 0.02 | 2 | 1 | True | 3151.9 | 1591.1 | 306.7 | 5722.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:114/66:635MB:11.96 |
| adaptive/oracle/residual/fresh | 45.28 | 0.02 | 2 | 1 | True | 3151.9 | 1591.1 | 306.7 | 5722.4 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:114/66:635MB:11.96 |
| adaptive/causal/fair/once | 61.92 | 0.02 | 2 | 1 | True | 1487.3 | 4035.1 | 2798.7 | 7155.7 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:28.590000000000003 |
| adaptive/causal/fair/fresh | 70.64 | 0.02 | 2 | 1 | True | 1487.3 | 4754.0 | 3517.6 | 8078.5 | B:0/180:1728MB:None; C:43/137:1315MB:None; D:86/94:903MB:37.3 |
| adaptive/causal/residual/once | 43.74 | 0.02 | 2 | 1 | True | 3151.9 | 2808.3 | 1524.0 | 6792.5 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:126/54:520MB:10.420000000000002 |
| adaptive/causal/residual/fresh | 43.74 | 0.02 | 2 | 1 | True | 3151.9 | 3067.1 | 1782.7 | 7061.0 | B:0/180:1728MB:None; C:8/172:1651MB:None; D:126/54:520MB:10.420000000000002 |

## bfly_rho2

gate: {'cancellations_equal': True, 'base_send_within_15pct': True, 'remote_within_10pct': False, 'discarded_within_15pct': False, 'pass': False, 'sim_base_send_s': 20.284333095550537, 'sim_remote_s': 42.7, 'sim_discarded_mb': 1372.3}

| policy | remote s | local s | cancelled | completed | final | discarded MB | staged MB | wasted MB | total MB | migrations (valid/180, delta MB, ready s) |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 42.7 | 0.02 | 2 | 1 | True | 1372.3 | 0.0 | 0.0 | 3749.5 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:25.15 |
| floor | 24.66 | 0.02 | 0 | 1 | True | 0.0 | 0.0 | 0.0 | 1202.5 | B:180/0:2MB:7.31; C:180/0:2MB:6.85; D:180/0:2MB:7.100000000000001 |
| none+retain | 42.7 | 0.02 | 2 | 1 | True | 1372.3 | 0.0 | 0.0 | 3749.5 | B:0/180:1728MB:None; C:0/180:1728MB:None; D:0/180:1728MB:25.15 |
| star/oracle/fair/once | 37.18 | 0.02 | 2 | 1 | True | 847.5 | 977.6 | 115.0 | 3643.8 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:46/134:1287MB:19.619999999999997 |
| star/oracle/fair/fresh | 37.18 | 0.02 | 2 | 1 | True | 847.5 | 977.6 | 115.0 | 3643.8 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:46/134:1287MB:19.619999999999997 |
| star/oracle/residual/once | 40.02 | 0.02 | 2 | 1 | True | 1372.3 | 460.1 | 47.9 | 3941.2 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:22/158:1517MB:22.479999999999997 |
| star/oracle/residual/fresh | 40.02 | 0.02 | 2 | 1 | True | 1372.3 | 460.1 | 47.9 | 3941.2 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:22/158:1517MB:22.479999999999997 |
| star/causal/fair/once | 67.18 | 0.02 | 2 | 1 | True | 679.3 | 3776.3 | 3067.1 | 6973.2 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:49.62 |
| star/causal/fair/fresh | 69.18 | 0.02 | 2 | 1 | True | 679.3 | 4476.0 | 3766.8 | 7720.3 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:51.62 |
| star/causal/residual/once | 40.22 | 0.02 | 2 | 1 | True | 1372.3 | 1322.7 | 1044.7 | 4827.9 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:20/160:1536MB:22.68 |
| star/causal/residual/fresh | 40.22 | 0.02 | 2 | 1 | True | 1372.3 | 1322.7 | 1044.7 | 4827.9 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:20/160:1536MB:22.68 |
| line/oracle/fair/once | 37.18 | 0.02 | 2 | 1 | True | 847.5 | 977.6 | 115.0 | 3643.8 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:46/134:1287MB:19.619999999999997 |
| line/oracle/fair/fresh | 37.18 | 0.02 | 2 | 1 | True | 847.5 | 977.6 | 115.0 | 3643.8 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:46/134:1287MB:19.619999999999997 |
| line/oracle/residual/once | 40.02 | 0.02 | 2 | 1 | True | 1372.3 | 460.1 | 47.9 | 3941.2 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:22/158:1517MB:22.479999999999997 |
| line/oracle/residual/fresh | 40.02 | 0.02 | 2 | 1 | True | 1372.3 | 460.1 | 47.9 | 3941.2 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:22/158:1517MB:22.479999999999997 |
| line/causal/fair/once | 45.88 | 0.02 | 2 | 1 | True | 847.5 | 3795.5 | 2846.6 | 6575.6 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:55/125:1200MB:28.32 |
| line/causal/fair/fresh | 52.92 | 0.02 | 2 | 1 | True | 788.2 | 4792.3 | 3833.9 | 7638.2 | B:0/180:1728MB:None; C:41/139:1335MB:None; D:59/121:1162MB:35.37 |
| line/causal/residual/once | 38.08 | 0.02 | 2 | 1 | True | 1372.3 | 2817.9 | 2252.4 | 6119.5 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:38/142:1363MB:20.520000000000003 |
| line/causal/residual/fresh | 37.98 | 0.02 | 2 | 1 | True | 1372.3 | 2492.0 | 1926.5 | 5779.7 | B:0/180:1728MB:None; C:20/160:1536MB:None; D:39/141:1354MB:20.42 |
| tree/oracle/fair/once | 33.46 | 0.02 | 2 | 1 | True | 847.5 | 1341.8 | 191.7 | 3630.8 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:76/104:999MB:15.91 |
| tree/oracle/fair/fresh | 33.46 | 0.02 | 2 | 1 | True | 847.5 | 1341.8 | 191.7 | 3630.8 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:76/104:999MB:15.91 |
| tree/oracle/residual/once | 39.72 | 0.02 | 2 | 1 | True | 1372.3 | 517.6 | 76.7 | 3962.7 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:25/155:1488MB:22.18 |
| tree/oracle/residual/fresh | 39.72 | 0.02 | 2 | 1 | True | 1372.3 | 517.6 | 76.7 | 3962.7 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:25/155:1488MB:22.18 |
| tree/causal/fair/once | 63.78 | 0.02 | 2 | 1 | True | 679.3 | 3776.3 | 3067.1 | 6892.6 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:46.23 |
| tree/causal/fair/fresh | 69.18 | 0.02 | 2 | 1 | True | 679.3 | 4581.5 | 3872.2 | 7825.7 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:51.62 |
| tree/causal/residual/once | 38.4 | 0.02 | 2 | 1 | True | 1372.3 | 1859.4 | 1428.1 | 5173.6 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:36/144:1383MB:20.839999999999996 |
| tree/causal/residual/fresh | 38.4 | 0.02 | 2 | 1 | True | 1372.3 | 1974.4 | 1543.1 | 5304.1 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:36/144:1383MB:20.839999999999996 |
| butterfly/oracle/fair/once | 33.46 | 0.02 | 2 | 1 | True | 847.5 | 1303.5 | 153.4 | 3591.2 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:76/104:999MB:15.91 |
| butterfly/oracle/fair/fresh | 33.46 | 0.02 | 2 | 1 | True | 847.5 | 1303.5 | 153.4 | 3591.2 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:76/104:999MB:15.91 |
| butterfly/oracle/residual/once | 39.82 | 0.02 | 2 | 1 | True | 1372.3 | 517.6 | 86.3 | 3974.5 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:24/156:1498MB:22.28 |
| butterfly/oracle/residual/fresh | 39.82 | 0.02 | 2 | 1 | True | 1372.3 | 517.6 | 86.3 | 3974.5 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:24/156:1498MB:22.28 |
| butterfly/causal/fair/once | 63.64 | 0.02 | 2 | 1 | True | 679.3 | 3776.3 | 3067.1 | 6894.8 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:46.089999999999996 |
| butterfly/causal/fair/fresh | 69.18 | 0.02 | 2 | 1 | True | 679.3 | 4571.9 | 3862.6 | 7821.7 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:51.62 |
| butterfly/causal/residual/once | 38.8 | 0.02 | 2 | 1 | True | 1372.3 | 2003.2 | 1610.2 | 5377.2 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:32/148:1421MB:21.240000000000002 |
| butterfly/causal/residual/fresh | 38.8 | 0.02 | 2 | 1 | True | 1372.3 | 2214.1 | 1821.1 | 5603.7 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:32/148:1421MB:21.240000000000002 |
| adaptive/oracle/fair/once | 33.46 | 0.02 | 2 | 1 | True | 847.5 | 1303.5 | 153.4 | 3591.2 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:76/104:999MB:15.91 |
| adaptive/oracle/fair/fresh | 33.46 | 0.02 | 2 | 1 | True | 847.5 | 1303.5 | 153.4 | 3591.2 | B:0/180:1728MB:None; C:44/136:1306MB:None; D:76/104:999MB:15.91 |
| adaptive/oracle/residual/once | 39.82 | 0.02 | 2 | 1 | True | 1372.3 | 517.6 | 86.3 | 3974.5 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:24/156:1498MB:22.28 |
| adaptive/oracle/residual/fresh | 39.82 | 0.02 | 2 | 1 | True | 1372.3 | 517.6 | 86.3 | 3974.5 | B:0/180:1728MB:None; C:21/159:1526MB:None; D:24/156:1498MB:22.28 |
| adaptive/causal/fair/once | 63.64 | 0.02 | 2 | 1 | True | 679.3 | 3776.3 | 3067.1 | 6894.8 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:46.089999999999996 |
| adaptive/causal/fair/fresh | 69.18 | 0.02 | 2 | 1 | True | 679.3 | 4571.9 | 3862.6 | 7821.7 | B:0/180:1728MB:None; C:27/153:1469MB:None; D:47/133:1277MB:51.62 |
| adaptive/causal/residual/once | 38.8 | 0.02 | 2 | 1 | True | 1372.3 | 2003.2 | 1610.2 | 5377.2 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:32/148:1421MB:21.240000000000002 |
| adaptive/causal/residual/fresh | 38.8 | 0.02 | 2 | 1 | True | 1372.3 | 2214.1 | 1821.1 | 5603.7 | B:0/180:1728MB:None; C:9/171:1641MB:None; D:32/148:1421MB:21.240000000000002 |

## Rules

```
{
 "gate": {
  "dog_rho1": true,
  "dog_rho2": true,
  "bfly_rho1": true,
  "bfly_rho2": false
 },
 "topology": {
  "dog_rho1": {
   "best_fixed": "line",
   "best_fixed_remote_s": 37.52,
   "adaptive_remote_s": 44.66,
   "adaptive_within_10pct_of_best_fixed": false,
   "fixed_beats_adaptive_by_10pct": true
  },
  "dog_rho2": {
   "best_fixed": "line",
   "best_fixed_remote_s": 35.78,
   "adaptive_remote_s": 48.84,
   "adaptive_within_10pct_of_best_fixed": false,
   "fixed_beats_adaptive_by_10pct": true
  },
  "bfly_rho1": {
   "best_fixed": "line",
   "best_fixed_remote_s": 45.78,
   "adaptive_remote_s": 61.92,
   "adaptive_within_10pct_of_best_fixed": false,
   "fixed_beats_adaptive_by_10pct": true
  },
  "bfly_rho2": {
   "best_fixed": "line",
   "best_fixed_remote_s": 45.88,
   "adaptive_remote_s": 63.64,
   "adaptive_within_10pct_of_best_fixed": false,
   "fixed_beats_adaptive_by_10pct": true
  }
 },
 "no_verdict_configs": [
  "bfly_rho2"
 ],
 "verdict": "CONDITIONAL (feasible, end-to-end gain below the preregistered bounds under the causal policy)"
}
```
