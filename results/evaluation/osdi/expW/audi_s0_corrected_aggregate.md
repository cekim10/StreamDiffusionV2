# W / R / N aggregate: frozen vs provenance-corrected (audi-snow-trail seed-0 OTTER run = verified reproduction)

Frozen outputs (`wrn_results.*`, `w2_table.csv`) are unchanged; the corrected set is `corrected_wrn_results.*`, `corrected_w2_table.csv` (`aggregate_wrn.py --corrected`). No figure script reads W / R / N outputs.

- Verdicts compared: 82 (W, R, N, V, A); **changed: none**
- Differing result fields: 1
  - `/W/W-H1 per workload TTFO/audi-snow-trail`: 0.6774104833602905 -> 0.6819372177124023

## Changed W2 unit rows

- audi-snow-trail seed 0: ttfo_s 0.6815676689147949 -> 0.6906211376190186; bind_call 59 -> 58; rejoin_calls 40 -> 26; rejoin_delay_s 24.129709005355835 -> 15.733651638031006; psnr_final_call 29.6853 -> 34.9024; psnr_median_last10 31.8545 -> 34.2087; min_psnr_after_crossing 29.6853 -> 25.5866; cuts_between [62, 94] -> [62]; RVC events 11 -> 6

## Counts cited in the paper (computed the same way on both sets)

| count | frozen | corrected |
|---|---|---|
| units | 40 | 40 |
| crossing | 39 | 39 |
| sustained | 31 | 31 |
| crossing_never_sustained | 8 | 8 |
| last10_median_below_35 | 10 | 10 |
| crossing_and_last10_below_35 (the paper's '9 units') | 9 | 9 |

**Aggregate conclusions changed: no.**
