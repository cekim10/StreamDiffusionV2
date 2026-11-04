# Fig. 12 caption (user draft 2026-11-03; every number checked against fig12_results.json, medians of 3 valid runs per cell)

Additions to the user's draft are marked [added]; drop them if not wanted.

```latex
\begin{figure*}[t]
  \centering
  \begin{subfigure}[b]{0.3\textwidth}
    \centering
    \includegraphics[width=\textwidth]{figures/eval/fig12a_gap_bfly.pdf}
    \caption{Maximum output gap.}
    \label{fig:fig12a_gap_bfly}
  \end{subfigure}
  \hfill
  \begin{subfigure}[b]{0.3\textwidth}
    \centering
    \includegraphics[width=\textwidth]{figures/eval/fig12a_ttfo_bfly.pdf}
    \caption{Time to first local output.}
    \label{fig:fig12a_ttfo_bfly}
  \end{subfigure}
  \hfill
  \begin{subfigure}[b]{0.3\textwidth}
    \centering
    \includegraphics[width=\textwidth]{figures/eval/fig12a_ready_cmp_bw250.pdf}
    \caption{OTTER readiness breakdown at 0.25\,Gbps.}
    \label{fig:fig12a_ready_cmp_bw250}
  \end{subfigure}
  \vspace{-0.1in}
  \caption{
    \textbf{Sensitivity to network bandwidth and input refresh rate.}
    (a--b) Under the high-refresh workload, OTTER maintains a
    maximum output gap of 1.6--1.8\,s across bandwidth settings,
    despite substantial variation in time to first local output.
    OTTER achieves the smallest output gap among all methods at
    every tested bandwidth.
    Full (unshaped link) and SLLM (0.25 and 0.5\,Gbps) reach local
    output sooner, with 4.5--12$\times$ larger maximum output gaps.   % [added]
    The bandwidth axis is logarithmic; Native (unshaped) is drawn at
    the measured 9.4\,Gbps NIC capacity.                                % [added]
    (c) At 0.25\,Gbps, the high-refresh workload increases OTTER's
    time to first local output from 76\,s to 155\,s.
    While Sink transfer times are comparable (59 vs.\ 70\,s),
    catch-up time increases from 15 to 83\,s, alongside an increase
    in transferred data from 1.82 to 4.67\,GB.
    Results show medians across three repetitions per condition.
  }
  \label{fig:fig12a}
\end{figure*}
```

Check (butterfly unless noted):
- Max. output gap OTTER 1.66 / 1.68 / 1.79 / 1.73 / 1.63 s (0.25 / 0.5 / 1 / 2.5 Gbps / native); smallest of the four
  methods in all 10 (workload, bandwidth) cells.
- TTFO-local fastest: SLLM at 0.25 (38.4 vs OTTER 154.9 s) and 0.5 Gbps (38.0 vs 49.0 s), OTTER at 1 and 2.5 Gbps,
  Full at native (7.3 vs 11.6 s). Gap ratios there: SLLM 19.59 / 1.66 = 11.8 x, 19.11 / 1.68 = 11.4 x; Full
  7.33 / 1.63 = 4.5 x.
- (c): Sink 59.3 / 70.2 s, catch-up 14.9 / 83.3 s (5.6 x), switch 1.4 / 1.4 s, total 75.6 / 154.9 s, OTTER bytes
  1.82 / 4.67 GB (dog / butterfly).

Text (user): "At native bandwidth, full-state transfer achieves faster local readiness, whereas OTTER continues to
provide a substantially smaller output gap." "At 0.25 Gbps, high-refresh input increases catch-up time by 5.6x,
while OTTER's maximum output gap remains nearly unchanged."

Figure changes (2026-11-03): x label of (a), (b) "Bandwidth (Gbps; Native = unshaped)"; (c) "Catch-up 5.6x longer"
inside High-refresh's catch-up segment. Fonts unchanged.
