# R37 -- flood governed-vs-ungoverned at n=10

Source: `r37_flood_n10_update.py`. Every number below is read live from the `rows` list this script writes to the paired CSV.

> **Corpus: defaults.** sampling: none sent, modelfile defaults temperature 1 / top_p 0.95 / top_k 64. All 10 seeds come from ONE flat directory pair (no code-vintage split -- see the Corpus vintage mix table below, which will show a single vintage label once seeds land).

## Corpus vintage mix

| vintage | git_commit (short) | seeds landed |
|---|---|---|
| defaults | 83fa97e1... | 42, 43, 44, 45, 46, 47, 48, 49, 50, 51 |

All 10 seeds are commit 83fa97e1... in one directory (vintage=defaults) -- no code-vintage mix to flag for this corpus.

## Part 1 -- per (arm, seed) metrics

| arm | seed | vintage | n_rows | IBR unconditional (%) | IBR tp_not_medium (%) | IBR tp_high (%) | EHE pooled simlog | Rejection rate (%) | Retry rate (%) |
|---|---|---|---|---|---|---|---|---|---|
| strict | 42 | defaults | 874 | 0.686 | 1.376 | 2.034 | 0.878 | 0.686 | 9.611 |
| strict | 43 | defaults | 904 | 0.664 | 1.425 | 1.974 | 0.846 | 0.664 | 10.177 |
| strict | 44 | defaults | 867 | 0.115 | 0.259 | 0.333 | 0.859 | 0.346 | 6.228 |
| strict | 45 | defaults | 900 | 0.444 | 0.922 | 1.278 | 0.842 | 0.556 | 7.333 |
| strict | 46 | defaults | 886 | 0.113 | 0.239 | 0.317 | 0.840 | 0.113 | 7.223 |
| strict | 47 | defaults | 893 | 0.672 | 1.345 | 1.899 | 0.871 | 0.784 | 9.294 |
| strict | 48 | defaults | 895 | 0.559 | 1.155 | 1.471 | 0.847 | 0.559 | 8.268 |
| strict | 49 | defaults | 910 | 0.330 | 0.680 | 1.007 | 0.841 | 0.440 | 8.571 |
| strict | 50 | defaults | 808 | 1.980 | 4.092 | 5.195 | 0.896 | 2.228 | 11.881 |
| strict | 51 | defaults | 849 | 0.942 | 1.900 | 2.395 | 0.871 | 1.649 | 11.661 |
| disabled | 42 | defaults | 943 | 10.286 | 19.877 | 27.327 | 0.818 | 0.000 | 0.000 |
| disabled | 43 | defaults | 951 | 11.987 | 22.222 | 28.649 | 0.804 | 0.000 | 0.000 |
| disabled | 44 | defaults | 873 | 10.538 | 20.536 | 23.955 | 0.885 | 0.000 | 0.000 |
| disabled | 45 | defaults | 915 | 9.290 | 18.559 | 23.582 | 0.852 | 0.000 | 0.000 |
| disabled | 46 | defaults | 898 | 8.686 | 16.847 | 20.290 | 0.867 | 0.000 | 0.000 |
| disabled | 47 | defaults | 905 | 8.729 | 17.673 | 20.795 | 0.860 | 0.000 | 0.000 |
| disabled | 48 | defaults | 879 | 9.556 | 20.048 | 22.353 | 0.881 | 0.000 | 0.000 |
| disabled | 49 | defaults | 972 | 9.979 | 20.041 | 27.439 | 0.766 | 0.000 | 0.000 |
| disabled | 50 | defaults | 817 | 10.404 | 18.973 | 21.351 | 0.907 | 0.000 | 0.000 |
| disabled | 51 | defaults | 917 | 10.469 | 19.048 | 23.636 | 0.841 | 0.000 | 0.000 |

## Contrast: strict - disabled, n=10 (full corpus)

| metric | n_pairs | complete | mean diff | sd | min | max | t | df | p (paired t) | p (exact perm) | perm floor | sign flips | all same sign |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IBR unconditional (%) | 10/10 | True | -9.342 | 0.986 | -11.324 | -8.057 | -29.977 | 9 | 0.0000 | 0.00200 | 0.00200 | 0 | True |
| IBR tp_not_medium (%) | 10/10 | True | -18.043 | 1.862 | -20.797 | -14.881 | -30.641 | 9 | 0.0000 | 0.00200 | 0.00200 | 0 | True |
| IBR tp_high (%) | 10/10 | True | -22.148 | 3.409 | -26.675 | -16.157 | -20.547 | 9 | 0.0000 | 0.00200 | 0.00200 | 0 | True |
| EHE pooled simlog | 10/10 | True | 0.011 | 0.039 | -0.035 | 0.075 | 0.888 | 9 | 0.3976 | 0.39060 | 0.00200 | 5 | False |
| Rejection rate (%) | 10/10 | True | 0.802 | 0.643 | 0.113 | 2.228 | 3.948 | 9 | 0.0034 | 0.00200 | 0.00200 | 0 | True |
| Retry rate (%) | 10/10 | True | 9.025 | 1.873 | 6.228 | 11.881 | 15.242 | 9 | 0.0000 | 0.00200 | 0.00200 | 0 | True |

## Contrast: strict - disabled, n=5 (seeds 42-46 only)

| metric | n_pairs | complete | mean diff | sd | min | max | t | df | p (paired t) | p (exact perm) | perm floor | sign flips | all same sign |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| IBR unconditional (%) | 5/5 | True | -9.753 | 1.135 | -11.324 | -8.573 | -19.209 | 4 | 0.0000 | 0.06250 | 0.06250 | 0 | True |
| IBR tp_not_medium (%) | 5/5 | True | -18.764 | 1.761 | -20.797 | -16.608 | -23.822 | 4 | 0.0000 | 0.06250 | 0.06250 | 0 | True |
| IBR tp_high (%) | 5/5 | True | -23.574 | 2.605 | -26.675 | -19.973 | -20.232 | 4 | 0.0000 | 0.06250 | 0.06250 | 0 | True |
| EHE pooled simlog | 5/5 | True | 0.008 | 0.041 | -0.026 | 0.060 | 0.446 | 4 | 0.6785 | 0.68750 | 0.06250 | 3 | False |
| Rejection rate (%) | 5/5 | True | 0.473 | 0.242 | 0.113 | 0.686 | 4.367 | 4 | 0.0120 | 0.06250 | 0.06250 | 0 | True |
| Retry rate (%) | 5/5 | True | 8.115 | 1.692 | 6.228 | 10.177 | 10.722 | 4 | 0.0004 | 0.06250 | 0.06250 | 0 | True |

## Plain read

All 10 seeds (42-51) landed in one corpus at model-default sampling; no vintage mix.

At n=10, 5/6 of the 6 metrics show all 10 seeds agreeing in sign on the strict-minus-disabled difference; the exact permutation floor at n=10 is 0.00200 (2/1024, computed directly by `_sign_stats`, not the task brief's stated 0.00098 -- see the FLOOR NOTE in this script's docstring for the discrepancy).

At n=5 (seeds 42-46 only), 5/6 metrics show all 5 seeds agreeing in sign, at the n=5 exact-permutation floor of 0.0625 (2/32) -- this is the same corpus's n=5 subset, reproduced here from the same runs for direct comparison, not pulled from another script's CSV.

Every t/permutation statistic above is computed by `R28._sign_stats()`, imported unmodified from `r28_trajectory_vs_traditional.py` -- this script does not reimplement or hand-adjust any part of the paired-t or exact-permutation calculation.

## Method

The 6 collapsed flood metrics are `r23_flood_strict_regen.py::_metrics_for()` (3 IBR conditionings at the final action level, EHE pooled simlog, rejection rate, retry rate), imported, not re-derived -- the same definitions r34 reuses. Per-seed manifest census value-enforces model=="gemma3:4b" and git_commit starting with "83fa97e1" for every seed in the defaults corpus (all 10 are newly ingested here, nothing pre-enforced). The strict-minus-disabled contrast (paired t at df=n-1, exact sign-flip permutation p, sign-flip count, mean/sd/min/max diff) is `r28_trajectory_vs_traditional.py::_sign_stats()`, imported unmodified, computed once over the full n=10 corpus and once over the n=5 seeds-42-46 subset for direct comparison. The exact-permutation floor is always `2.0 / (1 << n)` (two sign-assignments tie the observed |mean| exactly: the observed assignment itself and its total complement) -- 2/1024 = 0.001953125 at n=10, 2/32 = 0.0625 at n=5, both taken directly from `_sign_stats`'s own return value, never hand-typed.
